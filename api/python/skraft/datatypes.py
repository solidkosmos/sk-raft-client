# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024-2026 SOLIDKOSMOS S.A.

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
class TargetMemory(IntFlag):
    """The memories that you can select for fault injection.

    This class is an ``IntFlag``, so you can combine memories, for example::

        target = TargetMemory.FF | TargetMemory.BRAM

    The wire protocol supports combined memories for *random* and
    *exhaustive* injection. ``FpgaInjectionOptions`` holds the independent
    booleans ``essentials``, ``include_flip_flops``, ``include_lutrams`` and
    ``include_brams``. ``CRAM`` means that no flag limits the target (the
    full CRAM).

    A *specific* injection (``FpgaInjectionTarget``) holds a single
    ``FpgaTargetKind`` enum. Thus, a specific injection can have a maximum
    of one storage-element flag.
    """

    CRAM = 1 << 0
    ESSENTIAL_CRAM = 1 << 1
    FF = 1 << 2
    LUTRAM = 1 << 3
    BRAM = 1 << 4

    @property
    def required_design_files(self) -> tuple[str, ...]:
        """The :class:`Design` fields that this target depends on."""
        files: list[str] = []
        if self & TargetMemory.ESSENTIAL_CRAM:
            files.append("ebd")
        if self & (TargetMemory.FF | TargetMemory.LUTRAM | TargetMemory.BRAM):
            files.append("ll")
        return tuple(files)

class ReadbackOption(int, Enum):
    """The readback options."""
    READBACK = 0
    READBACK_CAPTURE = 1

class ScrubbingType(int, Enum):
    """The scrubbing mode."""

    READBACK = 0
    ESSENTIAL = 1


class FaultType(int, Enum):
    """The fault model of a fault injection campaign.

    This enum is a copy of the wire ``FpgaFaultType`` enum. ``FpgaFaultType``
    replaced the opaque ``uint32 type`` field (and the old ``InjectionType``
    in the Python client).
    """
    RANDOM = skraft_client_pb2.FPGA_FAULT_TYPE_RANDOM
    EXHAUSTIVE = skraft_client_pb2.FPGA_FAULT_TYPE_EXHAUSTIVE

# --------------------------------------------------------------------------- #
# Design-file configuration
# --------------------------------------------------------------------------- #
class ServerPath(str):
    """A file system path that the SK-RAFT *server* resolves, not the client.

    This class is a subclass of ``str``. Thus, the path stays compatible with
    the wire format, and the call sites show clearly that the path is
    relative to the server.
    """

    __slots__ = ()

    def __new__(cls, path: str) -> "ServerPath":
        return super().__new__(cls, str(PurePosixPath(path)))


@dataclass(frozen=True)
class Design:
    """The files of a design, as paths on the *client* computer.

    :meth:`FpgaDevice.uploadDesignToServer` uploads each file that you give.
    All fields are optional. If an operation must have a file that is not
    set, the operation raises :class:`DesignFileError` with the name of the
    field.
    """

    bit: Optional[str] = None   # bitstream, to program the device
    ebd: Optional[str] = None   # essential bits
    ll: Optional[str] = None    # logic location (flip-flop, LUTRAM, BRAM bits)
    xdc: Optional[str] = None   # constraints (pblocks)
    rbd: Optional[str] = None   # readback data (self-test)
    msd: Optional[str] = None   # readback mask (self-test)

    def require(self, *fields: str) -> None:
        """Raise :class:`DesignFileError` if a named field is not set."""
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
# Pblocks
# --------------------------------------------------------------------------- #
class FpgaPblockRange:
    """An inclusive ``from``..``to`` index range (wire ``FpgaPblockRange``).
    """

    def __init__(self, start: int, end: int) -> None:
        self.__start = start
        self.__end = end

    @property
    def start(self) -> int:
        """The first index of the range."""
        return self.__start

    @property
    def end(self) -> int:
        """The last index of the range."""
        return self.__end


class FpgaPblockAreaRange:
    def __init__(self, bit_range: FpgaPblockRange,
                 word_range: FpgaPblockRange) -> None:
        self.__bit_range = bit_range
        self.__word_range = word_range

    @property
    def bit_range(self) -> FpgaPblockRange:
        """The bit indexes that the area occupies in each word of
        :attr:`word_range`."""
        return self.__bit_range

    @property
    def word_range(self) -> FpgaPblockRange:
        """The word indexes that the area occupies in the frame."""
        return self.__word_range


class FpgaPblockFar:
    """One frame address that a pblock covers.
    """

    def __init__(self, far: int,
                 occupied_area: list[FpgaPblockAreaRange]) -> None:
        self.__far = far
        self.__occupied_area = occupied_area

    @property
    def far(self) -> int:
        """The frame address (FAR)."""
        return self.__far

    @property
    def occupied_area(self) -> list[FpgaPblockAreaRange]:
        """The areas of this frame that the pblock occupies."""
        return self.__occupied_area


class FpgaPblock:
    """A pblock that the constraints file declares (wire ``FpgaPblock``).

    ``clauses`` are the range expressions of the pblock, for example
    ``"SLICE_X0Y0:SLICE_X7Y49"``. The wire format sends the clauses as
    ``FpgaPblockClause`` messages. The client unwraps them to plain strings.
    Thus, you can give a clause directly to
    :meth:`FpgaDevice.pblock_by_clause`.
    """

    def __init__(self, name: str, clauses: list[str]) -> None:
        self.__name = name
        self.__clauses = clauses

    @property
    def name(self) -> str:
        """The name of the pblock, as written in the constraints."""
        return self.__name

    @property
    def clauses(self) -> list[str]:
        """The range expressions of the pblock."""
        return self.__clauses


# --------------------------------------------------------------------------- #
# Configuration-memory primitives
# --------------------------------------------------------------------------- #
class FpgaWord:
    """An FPGA word: a single 32-bit value.

    Note: The wire format does not have an ``FpgaWord`` message any more.
    The frames hold a flat ``repeated uint32``. The client keeps this class
    as a convenience wrapper.
    """

    def __init__(self, value: int):
        self.__value = value

    @property
    def value(self) -> int:
        """The 32-bit value of the word."""
        return self.__value


class FpgaFrame:
    """An FPGA frame: a frame address (FAR) and a list of words."""

    def __init__(self, far: int, words: list[FpgaWord]):
        self.__far = far
        self.__words = words

    @property
    def far(self) -> int:
        """The frame address (FAR) of the frame."""
        return self.__far

    @property
    def words(self) -> list[FpgaWord]:
        """The words of the frame. The number of words depends on the device
        family."""
        return self.__words


# --------------------------------------------------------------------------- #
# Boundary scan
# --------------------------------------------------------------------------- #
class BscanPrimitive:
    """A BSCAN USER register (``USER N``, with ``1 <= N <= 4``).

    The constructor validates the range. An id that is out of range raises
    ``ValueError`` immediately, not as a failure deep inside a write.
    """

    MIN_REGISTER = 1
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
        """Return the output of the register after ``value`` shifts through it.

        If ``readonly`` is set, the method uses ``FpgaReadBscan``, and the
        register contents do not change. If not, the method uses
        ``FpgaWriteBscan``.
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


class Bscan:
    """A BSCAN USER register of an attached device. You read and write the
    register as an integer::

        data = Bscan(dev, 4, 32)   # USER4, 32 bits wide
        data.write(0xA5A5A5A5)
        value = data.read()
    """

    def __init__(self, dev, user_register_id: int, size_in_bits: int):
        self.__dev = dev
        self.__primitive = BscanPrimitive(user_register_id, size_in_bits)

    @property
    def primitive(self) -> BscanPrimitive:
        """The USER register that this object uses."""
        return self.__primitive

    def write(self, value: int) -> None:
        """Shift ``value`` into the register."""
        self.__dev.write_bscan(self.__primitive, value)

    def read(self) -> int:
        """Read the register value, masked to the register size."""
        data = self.__dev.read_bscan(self.__primitive)
        mask = (1 << self.__primitive.size_in_bits) - 1
        return int.from_bytes(data, "big") & mask


# --------------------------------------------------------------------------- #
# Injection reports
# --------------------------------------------------------------------------- #
class FpgaInjectionReport:
    """The result of an injection at one location.

    :meth:`FpgaDevice.inject_at` returns one report. Also,
    :meth:`FpgaDevice.inject_exhaustive` returns one report for each location.
    For :meth:`FpgaDevice.inject_at`, the wire ``FpgaBitFlip`` RPC returns
    nothing. Thus, the report echoes the requested location, and ``net_name``
    is always ``None``.
    """

    def __init__(self, far: int, word_index: int, bit_index: int,
                 target: TargetMemory, net_name: Optional[str] = None):
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
    def target(self) -> TargetMemory:
        return self.__target

    @property
    def net_name(self) -> Optional[str]:
        return self.__net_name


class FpgaRandomInjectionReport:
    """The result of a single *random* injection
    (:meth:`FpgaDevice.inject_random`)."""

    def __init__(self, far: int, word_index: int, bit_index: int,
                 target: TargetMemory, net_name: Optional[str] = None):
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__target = target
        self.__net_name = net_name

    @property
    def far(self) -> int:
        """The frame address (FAR) where the injection occurred."""
        return self.__far

    @property
    def word_index(self) -> int:
        """The word index where the injection occurred."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """The bit index where the injection occurred."""
        return self.__bit_index

    @property
    def target(self) -> TargetMemory:
        """The area that received the injection."""
        return self.__target

    @property
    def net_name(self) -> Optional[str]:
        """The net name at the injection site if the upset hit a flip-flop.
        If not, ``None``."""
        return self.__net_name


# --------------------------------------------------------------------------- #
# Scrubbing
# --------------------------------------------------------------------------- #
class FpgaScrubWordSummary:
    """The details of one word that a scrubbing session affected."""

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
        """The frame address (FAR) of the affected frame."""
        return self.__far

    @property
    def word_index(self) -> int:
        """The index of the affected word."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """The index of the affected bit."""
        return self.__bit_index

    @property
    def golden_word_value(self) -> int:
        """The expected (golden) value of the word."""
        return self.__golden_word_value

    @property
    def erroneous_word_value(self) -> int:
        """The observed value of the word before the correction."""
        return self.__erroneous_word_value

    @property
    def ebd_word_value(self) -> int:
        """The word at the same location in the essential bits (EBD) file."""
        return self.__ebd_word_value

    @property
    def msd_word_value(self) -> int:
        """The word at the same location in the readback mask (MSD) file."""
        return self.__msd_word_value

    @property
    def is_essential(self) -> bool:
        """True if the affected bit was essential."""
        return self.__is_essential


class FpgaScrubSummary:
    """The result of one scrub cycle in a scrubbing session."""

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
        """The scrub cycle of this summary."""
        return self.__scrub_cycle

    @property
    def correction_time_ms(self) -> int:
        """The time used to correct upsets, in milliseconds."""
        return self.__correction_time_ms

    @property
    def idle_time_ms(self) -> int:
        """The idle time in the cycle, in milliseconds."""
        return self.__idle_time_ms

    @property
    def scrub_cycle_actual_duration_ms(self) -> int:
        """The measured duration of the scrub cycle, in milliseconds."""
        return self.__scrub_cycle_actual_duration_ms

    @property
    def word_summaries(self) -> list[FpgaScrubWordSummary]:
        """The details of each word that the cycle affected."""
        return self.__word_summaries


class FpgaScrubReport:
    """The result of a completed scrubbing session (RPC: ``FpgaScrubbing``).

    The wire reply holds one :class:`FpgaScrubSummary` for each scrub cycle.
    """

    def __init__(self, scrub_summaries: list[FpgaScrubSummary]):
        self.__scrub_summaries = scrub_summaries

    @property
    def scrub_summaries(self) -> list[FpgaScrubSummary]:
        """The summaries of each cycle of the session."""
        return self.__scrub_summaries


# --------------------------------------------------------------------------- #
# Fault-injection campaign
# --------------------------------------------------------------------------- #
@dataclass
class FpgaFiSession:
    """The user-defined options for a fault injection campaign.

    The upset-type shares (``sbu``/``mbu``/``mcu``) are percentages in
    ``[0, 100]``. Their sum must be ``100``. The constructor validates the
    sum.

    ``target`` selects the area. The campaign wire message only knows the
    difference between *full CRAM* and *essential CRAM*. Thus, ``target``
    must be ``TargetMemory.CRAM`` or ``TargetMemory.ESSENTIAL_CRAM``. The
    constructor rejects storage-element targets.
    """

    fault_type: FaultType
    duration_ms: int
    correction_time_ms: int
    time_between_faults_ms: int
    sbu_percent: float
    mbu_percent: float
    mcu_percent: float
    target: TargetMemory = TargetMemory.CRAM
    correct: bool = False

    def __post_init__(self) -> None:
        total = self.sbu_percent + self.mbu_percent + self.mcu_percent
        if abs(total - 100.0) > 1e-6:
            raise ValueError(
                f"sbu/mbu/mcu percentages must sum to 100, got {total}"
            )
        if self.target not in (TargetMemory.CRAM,
                               TargetMemory.ESSENTIAL_CRAM):
            raise ValueError(
                "campaign target must be TargetMemory.CRAM or "
                "TargetMemory.ESSENTIAL_CRAM (storage-element targeting is "
                "not supported for campaigns)"
            )

    @property
    def essential(self) -> bool:
        """True if the campaign targets only essential bits. The value comes
        from ``target``."""
        return bool(self.target & TargetMemory.ESSENTIAL_CRAM)


class FpgaFiWordSummary:
    """The details of one word that a campaign affected."""

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
        """The frame address (FAR) of the injected frame."""
        return self.__far

    @property
    def word_index(self) -> int:
        """The index of the injected word."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """The index of the injected bit."""
        return self.__bit_index

    @property
    def golden_word_value(self) -> int:
        """The word value before the injection."""
        return self.__golden_word_value

    @property
    def injected_word_value(self) -> int:
        """The word value after the injection."""
        return self.__injected_word_value

    @property
    def is_essential(self) -> bool:
        """True if the injected bit was essential."""
        return self.__is_essential


class FpgaFiSummary:
    """The result of a completed fault injection campaign.

    Note: The wire reply holds only the list of words (and the echoed
    session parameters). Thus, the client calculates ``faults_injected`` and
    ``corrected`` from ``affected_words`` and the ``correct`` flag of the
    session.

    If the server reports explicit counts in the future, set these values
    directly from the server counts.
    """

    def __init__(self, session: FpgaFiSession, faults_injected: int,
                 corrected: int, affected_words: list[FpgaFiWordSummary]):
        self.__session = session
        self.__faults_injected = faults_injected
        self.__corrected = corrected
        self.__affected_words = affected_words

    @property
    def session(self) -> FpgaFiSession:
        """The session that the campaign used."""
        return self.__session

    @property
    def faults_injected(self) -> int:
        """The total number of injected faults."""
        return self.__faults_injected

    @property
    def corrected(self) -> int:
        """The number of injected faults that were corrected."""
        return self.__corrected

    @property
    def affected_words(self) -> list[FpgaFiWordSummary]:
        """The details of each affected word."""
        return self.__affected_words
