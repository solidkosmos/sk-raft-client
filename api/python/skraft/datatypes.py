#   Copyright(C) 2024 SOLIDKOSMOS S.A.
#   All rights reserved.
#
#   This software ("Software") is supplied by SOLIDKOSMOS S.A. ("SolidKosmos").
#   SolidKosmos grants you a personal, non-exclusive, non-transferable, revocable,
#   non-sub-licensable right and license to use the Software. You may make copies of
#   this Software, provided this copyright notice and disclaimer ("Notice") is included
#   in all such copies. SolidKosmos reserves the right to change or discontinue the
#   Software at any time without notice.
#
#   THE SOFTWARE IS PROVIDED "AS IS". SOLIDKOSMOS DISCLAIMS ALL WARRANTIES OF ANY KIND,
#   WHETHER EXPRESS, IMPLIED, OR STATUTORY, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#   OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. TO THE
#   MAXIMUM EXTENT PERMITTED UNDER LAW, IN NO EVENT SHALL SOLIDKOSMOS BE LIABLE FOR ANY DIRECT,
#   INDIRECT, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING FROM, OUT OF OR IN
#   CONNECTION WITH THE SOFTWARE, EVEN IF SOLIDKOSMOS HAS BEEN ADVISED OF THE POSSIBILITY OF
#   SUCH DAMAGES. USE OF THIS SOFTWARE MAY BE SUBJECT TO TERMS AND CONDITIONS CONTAINED IN
#   AN ADDITIONAL AGREEMENT BETWEEN YOU AND SOLIDKOSMOS. IN CASE OF CONFLICT BETWEEN THE TERMS
#   OF THIS NOTICE AND ANY SUCH ADDITIONAL LICENSE AGREEMENT, THE TERMS OF THE AGREEMENT
#   SHALL TAKE PRECEDENCE. BY CONTINUING TO USE THIS SOFTWARE, YOU AGREE TO THE TERMS OF
#   THIS NOTICE. IF YOU DO NOT AGREE TO THESE TERMS, YOU ARE NOT PERMITTED TO USE THIS
#   SOFTWARE

"""Data structures exchanged with the SK-RAFT API.

This module matches the redesigned proto definition:
- ``InjectionArea`` is an ``IntFlag`` (combinable) used for random injection;
  a specific injection is narrowed to a single wire ``FpgaTargetKind``.
- ``FaultType`` mirrors the wire ``FpgaFaultType`` enum (SBU/MBU/MCU/MIXED),
  replacing the opaque integer fault type.
- ``DesignFiles`` groups the per-design paths into one validated object; all
  of them are pushed through the single ``FpgaSetDesignFilePath`` RPC.
- ``FpgaFiSession`` carries millisecond-suffixed timings matching the wire
  field names; ``FpgaFiSummary`` reports outcomes instead of echoing inputs.
- ``FpgaScrubReport`` wraps per-cycle ``FpgaScrubSummary`` entries (each with
  its ``FpgaScrubWordSummary`` list), mirroring the ``FpgaScrubbing`` RPC
  reply.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from pathlib import PurePosixPath
from typing import Optional

from . import skraft_client_pb2
from .exceptions import DesignFileError


# --------------------------------------------------------------------------- #
# Injection selection
# --------------------------------------------------------------------------- #
class InjectionArea(IntFlag):
    """Areas that can be selected for fault injection.

    Modelled as an ``IntFlag`` so areas can be combined, e.g.::

        target = InjectionArea.FLIP_FLOP | InjectionArea.BRAM

    The wire protocol supports this for *random* injection:
    ``FpgaRandomInjectionOptions`` carries independent ``include_flip_flops``
    / ``include_lutrams`` / ``include_brams`` booleans. ``CRAM`` is the
    absence of any narrowing flag (whole CRAM).

    A *specific* injection (``FpgaInjectionTarget``) carries a single
    ``FpgaTargetKind`` enum, so only one storage-element flag may be set
    there.
    """

    CRAM = 1 << 0
    ESSENTIAL_CRAM = 1 << 1
    FLIP_FLOP = 1 << 2
    LUTRAM = 1 << 3
    BRAM = 1 << 4

    @property
    def required_design_files(self) -> tuple[str, ...]:
        """The :class:`DesignFiles` fields this target depends on."""
        files: list[str] = []
        if self & InjectionArea.ESSENTIAL_CRAM:
            files.append("ebd")
        if self & (InjectionArea.FLIP_FLOP
                   | InjectionArea.LUTRAM
                   | InjectionArea.BRAM):
            files.append("ll")
        return tuple(files)

class ReadbackOption(int, Enum):
    """Readkback options."""
    READBACK = 0
    READBACK_CAPTURE = 1

class ScrubbingType(int, Enum):
    """Scrubbing mode."""

    READBACK = 0
    ESSENTIAL = 1


class FaultType(int, Enum):
    """Fault model used by a fault-injection campaign.

    Mirrors the wire ``FpgaFaultType`` enum, which replaced the opaque
    ``uint32 type`` field (and the former ``InjectionType`` on the Python
    side).
    """
    RANDOM = skraft_client_pb2.FPGA_FAULT_TYPE_RANDOM
    EXHAUSTIVE = skraft_client_pb2.FPGA_FAULT_TYPE_EXHAUSTIVE

# --------------------------------------------------------------------------- #
# Design-file configuration
# --------------------------------------------------------------------------- #
class ServerPath(str):
    """A filesystem path resolved on the SK-RAFT *server*, not the client.

    Subclasses ``str`` so it stays wire-compatible while making the
    server-relative semantics explicit at call sites.
    """

    __slots__ = ()

    def __new__(cls, path: str) -> "ServerPath":
        return super().__new__(cls, str(PurePosixPath(path)))


@dataclass(frozen=True)
class DesignFiles:
    """The set of design files associated with a programmed design.

    All paths are relative to the SK-RAFT server's filesystem. Every field is
    optional; an operation that needs a missing file raises
    :class:`DesignFileError` naming the field.
    """

    bitstream: Optional[ServerPath] = None   # programming
    ebd: Optional[ServerPath] = None         # essential bits
    ll: Optional[ServerPath] = None          # logic location
    rbd: Optional[ServerPath] = None         # readback data (self-test)
    msd: Optional[ServerPath] = None         # mask (self-test)

    def require(self, *fields: str) -> None:
        """Raise :class:`DesignFileError` if any named field is unset."""
        missing = [f for f in fields if getattr(self, f) is None]
        if missing:
            raise DesignFileError(
                f"operation requires design file(s): {', '.join(missing)}"
            )


class FpgaFar:
    def __init__(self, raw: int, blocktype: int, topbottom: int,
                 row_address: int, column_address: int, 
                 minor_address: int) -> None:
        self.__raw = raw
        self.__blocktype      = blocktype
        self.__topbottom      = topbottom
        self.__row_address    = row_address
        self.__column_address = column_address
        self.__minor_address  = minor_address

    @property
    def raw(self) -> int:
        return self.__raw
    
    @property
    def blocktype(self) -> int:
        return self.__blocktype
    
    @property
    def topbottom(self) -> int:
        return self.__topbottom

    @property
    def row_address(self) -> int:
        return self.__row_address

    @property
    def column_address(self) -> int:
        return self.__column_address

    @property
    def minor_address(self) -> int:
        return self.__minor_address


# --------------------------------------------------------------------------- #
# Configuration-memory primitives
# --------------------------------------------------------------------------- #
class FpgaWord:
    """An FPGA word: a single 32-bit value.

    Note: the wire format no longer has an ``FpgaWord`` message (frames carry
    a flat ``repeated uint32``); this class is kept as a client-side
    convenience wrapper.
    """

    def __init__(self, value: int):
        self.__value = value

    @property
    def value(self) -> int:
        """The 32-bit value of the word."""
        return self.__value


class FpgaFrame:
    """An FPGA frame: a Frame Address (FAR) and a list of words."""

    def __init__(self, far: int, words: list[FpgaWord]):
        self.__far = far
        self.__words = words

    @property
    def far(self) -> int:
        """The Frame Address (FAR) of the frame."""
        return self.__far

    @property
    def words(self) -> list[FpgaWord]:
        """The words of the frame; length is family-dependent."""
        return self.__words


# --------------------------------------------------------------------------- #
# Boundary scan
# --------------------------------------------------------------------------- #
class BscanPrimitive:
    """A BSCAN USER register (``USER N``, with ``0 <= N <= 4``).

    The range is validated in the constructor; an out-of-range id raises
    ``ValueError`` rather than failing deep inside a write.
    """

    MIN_REGISTER = 0
    MAX_REGISTER = 4

    def __init__(self, user_register_id: int, size_in_bits: int):
        if not (self.MIN_REGISTER <= user_register_id <= self.MAX_REGISTER):
            raise ValueError(
                f"user_register_id must be in "
                f"[{self.MIN_REGISTER}, {self.MAX_REGISTER}], "
                f"got {user_register_id}"
            )
        self.__user_register_id = user_register_id
        self.__size_in_bits = size_in_bits

    @property
    def user_register_id(self) -> int:
        return self.__user_register_id

    @property
    def size_in_bits(self) -> int:
        return self.__size_in_bits

    def shift_in(self, grpc_client, value: bytes,
                 readonly: bool = False) -> bytes:
        """Shift ``value`` through the register and return what comes out.

        Uses ``FpgaReadBscan`` when ``readonly`` is set (leaving the register
        contents untouched) and ``FpgaWriteBscan`` otherwise.
        """
        request = skraft_client_pb2.FpgaBscanTarget(
            user_register_id=self.__user_register_id,
            value=value,
            useful_bits=self.__size_in_bits,
        )
        if readonly:
            reply = grpc_client.FpgaReadBscan(request)
        else:
            reply = grpc_client.FpgaWriteBscan(request)
        return bytes(reply.value)


# --------------------------------------------------------------------------- #
# Injection reports
# --------------------------------------------------------------------------- #
class FpgaInjectionReport:
    """Result of a single *specific* injection (:meth:`FpgaDevice.inject_at`).

    The wire ``FpgaBitFlip`` RPC returns nothing, so the report echoes the
    requested location; ``net_name`` is therefore always ``None`` here.
    """

    def __init__(self, far: int, word_index: int, bit_index: int,
                 target: InjectionArea, net_name: Optional[str] = None):
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__target = target
        self.__net_name = net_name

    @property
    def far(self) -> int:
        return self.__far

    @property
    def word_index(self) -> int:
        return self.__word_index

    @property
    def bit_index(self) -> int:
        return self.__bit_index

    @property
    def target(self) -> InjectionArea:
        return self.__target

    @property
    def net_name(self) -> Optional[str]:
        return self.__net_name


class FpgaRandomInjectionReport:
    """Result of a single *random* injection
    (:meth:`FpgaDevice.inject_random`)."""

    def __init__(self, far: int, word_index: int, bit_index: int,
                 target: InjectionArea, net_name: Optional[str] = None):
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__target = target
        self.__net_name = net_name

    @property
    def far(self) -> int:
        """Frame Address (FAR) where the injection took place."""
        return self.__far

    @property
    def word_index(self) -> int:
        """Word index where the injection took place."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """Bit index where the injection took place."""
        return self.__bit_index

    @property
    def target(self) -> InjectionArea:
        """The area that was injected."""
        return self.__target

    @property
    def net_name(self) -> Optional[str]:
        """Net name at the injection site if the upset hit a flip-flop, else
        ``None``."""
        return self.__net_name


# --------------------------------------------------------------------------- #
# Scrubbing
# --------------------------------------------------------------------------- #
class FpgaScrubWordSummary:
    """Per-word detail for a word touched during a scrubbing session."""

    def __init__(self, far: int, word_index: int, bit_index: int,
                 golden_word_value: int, erroneous_word_value: int,
                 ebd_word_value: int, msd_word_value: int,
                 is_essential: bool):
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__golden_word_value = golden_word_value
        self.__erroneous_word_value = erroneous_word_value
        self.__ebd_word_value = ebd_word_value
        self.__msd_word_value = msd_word_value
        self.__is_essential = is_essential

    @property
    def far(self) -> int:
        """Frame Address (FAR) of the affected frame."""
        return self.__far

    @property
    def word_index(self) -> int:
        """Index of the affected word."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """Index of the affected bit."""
        return self.__bit_index

    @property
    def golden_word_value(self) -> int:
        """Expected (golden) word value."""
        return self.__golden_word_value

    @property
    def erroneous_word_value(self) -> int:
        """Word value observed before correction."""
        return self.__erroneous_word_value

    @property
    def ebd_word_value(self) -> int:
        """Matching word from the essential-bits (EBD) file."""
        return self.__ebd_word_value

    @property
    def msd_word_value(self) -> int:
        """Matching word from the readback-mask (MSD) file."""
        return self.__msd_word_value

    @property
    def is_essential(self) -> bool:
        """Whether the affected bit was essential."""
        return self.__is_essential


class FpgaScrubSummary:
    """Outcome of one scrub cycle within a scrubbing session."""

    def __init__(self, scrub_cycle: int, correction_time_ms: int,
                 idle_time_ms: int, scrub_cycle_actual_duration_ms: int,
                 word_summaries: list[FpgaScrubWordSummary]):
        self.__scrub_cycle = scrub_cycle
        self.__correction_time_ms = correction_time_ms
        self.__idle_time_ms = idle_time_ms
        self.__scrub_cycle_actual_duration_ms = scrub_cycle_actual_duration_ms
        self.__word_summaries = word_summaries

    @property
    def scrub_cycle(self) -> int:
        """The scrub cycle this summary belongs to."""
        return self.__scrub_cycle

    @property
    def correction_time_ms(self) -> int:
        """Time spent correcting upsets, in milliseconds."""
        return self.__correction_time_ms

    @property
    def idle_time_ms(self) -> int:
        """Idle time within the cycle, in milliseconds."""
        return self.__idle_time_ms

    @property
    def scrub_cycle_actual_duration_ms(self) -> int:
        """Measured duration of the scrub cycle, in milliseconds."""
        return self.__scrub_cycle_actual_duration_ms

    @property
    def word_summaries(self) -> list[FpgaScrubWordSummary]:
        """Per-word detail for the words touched during the cycle."""
        return self.__word_summaries


class FpgaScrubReport:
    """Outcome of a completed scrubbing session (RPC: ``FpgaScrubbing``).

    The wire reply carries one :class:`FpgaScrubSummary` per scrub cycle.
    """

    def __init__(self, scrub_summaries: list[FpgaScrubSummary]):
        self.__scrub_summaries = scrub_summaries

    @property
    def scrub_summaries(self) -> list[FpgaScrubSummary]:
        """Per-cycle summaries for the session."""
        return self.__scrub_summaries


# --------------------------------------------------------------------------- #
# Fault-injection campaign
# --------------------------------------------------------------------------- #
@dataclass
class FpgaFiSession:
    """User-defined options for a fault-injection campaign.

    The upset-type shares (``sbu``/``mbu``/``mcu``) are percentages in
    ``[0, 100]`` and must sum to ``100``; this is validated on construction.

    ``target`` selects the area. The campaign wire message only distinguishes
    *whole CRAM* from *essential CRAM*, so ``target`` must be either
    ``InjectionArea.CRAM`` or ``InjectionArea.ESSENTIAL_CRAM``; storage-element
    targets are rejected.
    """

    fault_type: FaultType
    duration_ms: int
    correction_time_ms: int
    time_between_faults_ms: int
    sbu_percent: float
    mbu_percent: float
    mcu_percent: float
    target: InjectionArea = InjectionArea.CRAM
    correct: bool = False

    def __post_init__(self) -> None:
        total = self.sbu_percent + self.mbu_percent + self.mcu_percent
        if abs(total - 100.0) > 1e-6:
            raise ValueError(
                f"sbu/mbu/mcu percentages must sum to 100, got {total}"
            )
        if self.target not in (InjectionArea.CRAM,
                               InjectionArea.ESSENTIAL_CRAM):
            raise ValueError(
                "campaign target must be InjectionArea.CRAM or "
                "InjectionArea.ESSENTIAL_CRAM (storage-element targeting is "
                "not supported for campaigns)"
            )

    @property
    def essential(self) -> bool:
        """Whether the campaign targets only essential bits (derived from
        ``target``)."""
        return bool(self.target & InjectionArea.ESSENTIAL_CRAM)


class FpgaFiWordSummary:
    """Per-word detail for a word affected during a campaign."""

    def __init__(self, far: int, word_index: int, bit_index: int,
                 golden_word_value: int, injected_word_value: int,
                 is_essential: bool):
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__golden_word_value = golden_word_value
        self.__injected_word_value = injected_word_value
        self.__is_essential = is_essential

    @property
    def far(self) -> int:
        """Frame Address (FAR) of the injected frame."""
        return self.__far

    @property
    def word_index(self) -> int:
        """Index of the injected word."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """Index of the injected bit."""
        return self.__bit_index

    @property
    def golden_word_value(self) -> int:
        """Word value before injection."""
        return self.__golden_word_value

    @property
    def injected_word_value(self) -> int:
        """Word value after injection."""
        return self.__injected_word_value

    @property
    def is_essential(self) -> bool:
        """Whether the injected bit was essential."""
        return self.__is_essential


class FpgaFiSummary:
    """Outcome of a completed fault-injection campaign.

    Note: the wire reply only carries the per-word list (plus echoed session
    parameters). ``faults_injected`` / ``corrected`` are therefore derived
    client-side from ``affected_words`` and the session's ``correct`` flag.
    If the server later reports explicit counts, populate them directly
    instead.
    """

    def __init__(self, session: FpgaFiSession, faults_injected: int,
                 corrected: int, affected_words: list[FpgaFiWordSummary]):
        self.__session = session
        self.__faults_injected = faults_injected
        self.__corrected = corrected
        self.__affected_words = affected_words

    @property
    def session(self) -> FpgaFiSession:
        """The session the campaign was run with."""
        return self.__session

    @property
    def faults_injected(self) -> int:
        """Total number of faults injected."""
        return self.__faults_injected

    @property
    def corrected(self) -> int:
        """Number of injected faults that were corrected."""
        return self.__corrected

    @property
    def affected_words(self) -> list[FpgaFiWordSummary]:
        """Per-word detail for the affected words."""
        return self.__affected_words
