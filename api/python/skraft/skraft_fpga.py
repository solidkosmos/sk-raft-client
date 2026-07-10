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

"""SK-RAFT FPGA control client, matching the redesigned proto definition.

``SkraftFpga`` owns the server connection and hands out ``FpgaDevice`` handles.
``FpgaDevice`` carries everything tied to a reserved device: design files,
queries, programming/readback, scrubbing and fault injection. Both are context
managers.

Both classes wrap the gRPC stub generated from the redesigned
``SKRaftFpga`` service; the mapping from each method to its RPC is noted
inline. Note that the redesigned proto uses PascalCase RPC names
(``FpgaConnect``, ``FpgaSetDesignFilePath``, ...) and snake_case field names,
and
the generated Python code follows suit.
"""

from __future__ import annotations

from typing import Optional

import grpc
from google.protobuf import empty_pb2

from . import datatypes
from . import skraft_client_pb2
from . import skraft_client_pb2_grpc
from .datatypes import (
    BscanPrimitive,
    DesignFiles,
    FpgaFiSession,
    FpgaFiSummary,
    FpgaFrame,
    FpgaInjectionReport,
    FpgaRandomInjectionReport,
    FpgaScrubReport,
    FpgaScrubSummary,
    FpgaScrubWordSummary,
    FpgaWord,
    FpgaFiWordSummary,
    InjectionArea,
    ServerPath,
    ScrubbingType,
    ReadbackOption,
)
from .exceptions import (
    BscanError,
    ConnectionFailedError,
    DeviceReservationError,
    FrameAddressError,
)


def _rpc_detail(error: grpc.RpcError) -> str:
    """Best-effort extraction of a gRPC error detail string."""
    try:
        return error.details()  # type: ignore[attr-defined]
    except Exception:
        return str(error)


def _kind_from_area(target: InjectionArea) -> int:
    """Map an :class:`InjectionArea` to the wire ``FpgaTargetKind`` enum.

    ``FpgaInjectionTarget`` carries a single ``kind``, so at most one
    storage-element flag may be set for a specific injection.
    """
    storage_flags = [
        (InjectionArea.FLIP_FLOP,
         skraft_client_pb2.FPGA_TARGET_KIND_FLIP_FLOP),
        (InjectionArea.LUTRAM, skraft_client_pb2.FPGA_TARGET_KIND_LUTRAM),
        (InjectionArea.BRAM, skraft_client_pb2.FPGA_TARGET_KIND_BRAM),
    ]
    selected = [kind for flag, kind in storage_flags if target & flag]
    if len(selected) > 1:
        raise ValueError(
            "a specific injection targets exactly one memory kind; got a "
            f"combined InjectionArea: {target!r}"
        )
    if selected:
        return selected[0]
    return skraft_client_pb2.FPGA_TARGET_KIND_CRAM


# --------------------------------------------------------------------------- #
# FpgaDevice
# --------------------------------------------------------------------------- #
class FpgaDevice:
    """A reserved FPGA device. Obtain via :meth:`SkraftFpga.attach`.

    Usable as a context manager so the reservation is always released::

        with client.attach("xcku040") as dev:
            dev.load(DesignFiles(bitstream=ServerPath("top.bit")))
            dev.program()
    """

    # Maps a DesignFiles field to the FpgaFileType enum value sent through
    # the single FpgaSetDesignFilePath RPC (which replaced the five per-type
    # RPCs).
    _FILE_TYPES = {
        "bitstream": skraft_client_pb2.FPGA_FILE_TYPE_BIT,
        "ebd": skraft_client_pb2.FPGA_FILE_TYPE_EBD,
        "ll": skraft_client_pb2.FPGA_FILE_TYPE_LL,
        "rbd": skraft_client_pb2.FPGA_FILE_TYPE_RBD,
        "msd": skraft_client_pb2.FPGA_FILE_TYPE_MSD,
    }

    # Maps a bit-statistics label to the FpgaBitCategory enum value used by
    # the FpgaGetBitCount RPC (which replaced the five per-category RPCs).
    _BIT_CATEGORIES = {
        "CRAM": skraft_client_pb2.FPGA_BIT_CATEGORY_CRAM,
        "essential CRAM": skraft_client_pb2.FPGA_BIT_CATEGORY_ESSENTIAL_CRAM,
        "BRAM": skraft_client_pb2.FPGA_BIT_CATEGORY_BRAM,
        "flip-flop": skraft_client_pb2.FPGA_BIT_CATEGORY_FLIP_FLOP,
        "LUTRAM": skraft_client_pb2.FPGA_BIT_CATEGORY_LUTRAM,
    }

    def __init__(self, stub, part_number: Optional[str]):
        self._stub = stub
        self.part_number = part_number
        self._files = DesignFiles()

    # -- lifecycle --------------------------------------------------------- #
    def __enter__(self) -> "FpgaDevice":
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()

    def release(self) -> None:
        """Free the device's reserved resources (RPC: ``FpgaClose``)."""
        try:
            self._stub.FpgaClose(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to release device: {_rpc_detail(e)}"
            ) from e

    # -- design files ------------------------------------------------------ #
    def load(self, files: DesignFiles) -> None:
        """Associate design files with the device and push each provided path
        to the server (RPC: ``FpgaSetDesignFilePath`` with the matching
        ``FpgaFileType``). Stores paths only; the server does not read file
        contents until an operation needs them.
        """
        try:
            for field_name, file_type in self._FILE_TYPES.items():
                path = getattr(files, field_name)
                if path is not None:
                    request = skraft_client_pb2.FpgaDesignFilePathRequest(
                        type=file_type,
                        path=str(path),
                    )
                    self._stub.FpgaSetDesignFilePath(request)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to configure design file paths: {_rpc_detail(e)}"
            ) from e
        self._files = files

    @property
    def files(self) -> DesignFiles:
        """The currently loaded design files."""
        return self._files

    # -- programming & readback ------------------------------------------- #
    def program(self) -> None:
        """Upload the loaded bitstream to the device (RPC: ``FpgaProgram``)."""
        self._files.require("bitstream")
        try:
            self._stub.FpgaProgram(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to program the target FPGA device: {_rpc_detail(e)}"
            ) from e

    def readback_range(self, start_far: int,
                       end_far: int) -> list[FpgaFrame]:
        """Read back the frames in ``[start_far, end_far]``
        (RPC: ``FpgaReadBackRange``).
        """
        if start_far > end_far:
            raise FrameAddressError(
                f"start_far ({start_far}) must be <= end_far ({end_far})"
            )
        try:
            request = skraft_client_pb2.FpgaReadbackTarget(
                start_frame_address=start_far,
                end_frame_address=end_far,
                capture=False, 
            )
            reply = self._stub.FpgaReadBackRange(request)
            return self._frames_from_reply(reply)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to read frames [{start_far}, {end_far}]: "
                f"{_rpc_detail(e)}"
            ) from e

    def shutdown(self): 
        """Shutdowns the FPGA device."""
        try:
            self._stub.FpgaShutdown(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to shutdown the device: {_rpc_detail(e)}"
            ) from e

    def startup_sequence(self):
        try:
            self._stub.FpgaStartupSequence(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"Startup sequence failed: {_rpc_detail(e)}"
            ) from e

    def restore_application_layer(self):
        try:
            self._stub.FpgaRestoreApplication(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"Failed to restore application layer: {_rpc_detail(e)}"
            ) from e

    def readback(self, option: ReadbackOption) -> list[FpgaFrame]:
        """Read back every configuration frame of the device
        (RPC: ``FpgaReadBack``).
        """
        try:
            capture = True if option == ReadbackOption.READBACK_CAPTURE else False
                
            request = skraft_client_pb2.FpgaReadbackTarget(
                start_frame_address=0, # Ignored.
                end_frame_address=0,   # Ignored.
                capture=capture
            )

            reply = self._stub.FpgaReadBack(request)
            return self._frames_from_reply(reply)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to read back the device: {_rpc_detail(e)}"
            ) from e

    @staticmethod
    def _frames_from_reply(reply) -> list[FpgaFrame]:
        # FpgaFrame.words is now a flat repeated uint32 (the FpgaWord
        # wrapper message was removed from the wire format).
        frames: list[FpgaFrame] = []
        for frame in reply.frames:
            words = [FpgaWord(value) for value in frame.words]
            frames.append(FpgaFrame(frame.frame_address, words))
        return frames

    # -- device queries (properties) -------------------------------------- #
    @property
    def cram_bits(self) -> int:
        """Total CRAM bits in the active device
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_CRAM``)."""
        return self._count("CRAM")

    @property
    def essential_cram_bits(self) -> int:
        """Essential CRAM bits for the loaded design
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_ESSENTIAL_CRAM``;
        requires the EBD file)."""
        self._files.require("ebd")
        return self._count("essential CRAM")

    @property
    def ff_bits(self) -> int:
        """Flip-flop bits used by the loaded design
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_FLIP_FLOP``;
        requires the LL file)."""
        self._files.require("ll")
        return self._count("flip-flop")

    @property
    def bram_bits(self) -> int:
        """BRAM bits used by the loaded design
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_BRAM``;
        requires the LL file)."""
        self._files.require("ll")
        return self._count("BRAM")

    @property
    def lutram_bits(self) -> int:
        """LUTRAM bits used by the loaded design
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_LUTRAM``;
        requires the LL file)."""
        self._files.require("ll")
        return self._count("LUTRAM")

    @property
    def all_bit_counts(self) -> dict[str, int]:
        """Every bit statistic in a single round trip
        (RPC: ``FpgaGetAllBitCounts``; requires the EBD and LL files, since
        the reply covers essential-CRAM and storage-element counts).
        """
        self._files.require("ebd", "ll")
        try:
            reply = self._stub.FpgaGetAllBitCounts(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the bit counts: {_rpc_detail(e)}"
            ) from e
        return {
            "cram_bits": reply.cram_bits,
            "essential_cram_bits": reply.essential_cram_bits,
            "bram_bits": reply.bram_bits,
            "flip_flop_bits": reply.flip_flop_bits,
            "lutram_bits": reply.lutram_bits,
        }

    def _count(self, label: str) -> int:
        try:
            request = skraft_client_pb2.FpgaBitCountRequest(
                category=self._BIT_CATEGORIES[label],
            )
            return self._stub.FpgaGetBitCount(request).value
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the {label} bits: {_rpc_detail(e)}"
            ) from e

    # -- fault injection --------------------------------------------------- #
    def inject_random(
        self, target: InjectionArea
    ) -> FpgaRandomInjectionReport:
        """Inject a single random SEU into ``target``
        (RPC: ``FpgaRandomBitFlip``).
        """
        self._files.require(*target.required_design_files)
        try:
            request = skraft_client_pb2.FpgaRandomInjectionOptions(
                include_essential=bool(target & InjectionArea.ESSENTIAL_CRAM),
                include_flip_flops=bool(target & InjectionArea.FLIP_FLOP),
                include_lutrams=bool(target & InjectionArea.LUTRAM),
                include_brams=bool(target & InjectionArea.BRAM),
            )
            reply = self._stub.FpgaRandomBitFlip(request)
            return FpgaRandomInjectionReport(
                reply.target.frame_address,
                reply.target.word_index,
                reply.target.bit_index,
                target,
                reply.target.net_name or None,
            )
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform random bit flip: {_rpc_detail(e)}"
            ) from e

    def inject_at(self, far: int, word_index: int, bit_index: int,
                  target: InjectionArea) -> FpgaInjectionReport:
        """Inject an upset at a specific ``(far, word_index, bit_index)``
        location, constrained to ``target`` (RPC: ``FpgaBitFlip``).

        The wire message now carries a single ``FpgaTargetKind`` enum instead
        of three booleans, so ``target`` must name at most one storage-element
        area (``FLIP_FLOP``, ``LUTRAM`` or ``BRAM``); anything else is treated
        as CRAM.
        """
        self._files.require(*target.required_design_files)
        try:
            request = skraft_client_pb2.FpgaInjectionTarget(
                frame_address=far,
                word_index=word_index,
                bit_index=bit_index,
                kind=_kind_from_area(target),
            )
            self._stub.FpgaBitFlip(request)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform bit flip: {_rpc_detail(e)}"
            ) from e
        # FpgaBitFlip returns nothing; echo the requested location.
        return FpgaInjectionReport(far, word_index, bit_index, target)

    def scrub(self, option: ScrubbingType, scrub_cycle: int,
              duration_ms: int, session_id: str = "") -> FpgaScrubReport:
        """Run a scrubbing session (RPC: ``FpgaScrubbing``).

        ``ESSENTIAL`` scrubbing needs the EBD file so the server can tell
        essential from non-essential upsets.
        """
        if option == ScrubbingType.ESSENTIAL:
            self._files.require("ebd")
        try:
            essential = False 
            if option == ScrubbingType.ESSENTIAL:
                essential = True

            request = skraft_client_pb2.FpgaScrubSession(
                scrub_cycle=scrub_cycle,
                duration_ms=duration_ms,
                essential=essential,
                id=session_id,
            )
            reply = self._stub.FpgaScrubbing(request)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform scrubbing: {_rpc_detail(e)}"
            ) from e

        summaries: list[FpgaScrubSummary] = []
        for summary in reply.scrub_summaries:
            words = [
                FpgaScrubWordSummary(
                    ws.far,
                    ws.word_index,
                    ws.bit_index,
                    ws.golden_word_value,
                    ws.erroneous_word_value,
                    ws.ebd_word_value,
                    ws.msd_word_value,
                    ws.is_essential,
                )
                for ws in summary.word_summaries
            ]
            summaries.append(
                FpgaScrubSummary(
                    summary.scrub_cycle,
                    summary.correction_time_ms,
                    summary.idle_time_ms,
                    summary.scrub_cycle_actual_duration_ms,
                    words,
                )
            )
        return FpgaScrubReport(summaries)

    def run_campaign(self, session: FpgaFiSession) -> FpgaFiSummary:
        """Run a user-defined fault-injection campaign
        (RPC: ``FpgaFaultInjection``).
        """
        if session.essential:
            self._files.require("ebd")
        try:
            request = skraft_client_pb2.FpgaFiSession(
                type=session.fault_type.value,
                duration_ms=session.duration_ms,
                correction_time_ms=session.correction_time_ms,
                time_between_faults_ms=session.time_between_faults_ms,
                sbu_percent=session.sbu_percent,
                mbu_percent=session.mbu_percent,
                mcu_percent=session.mcu_percent,
                essential=session.essential,
                correct=session.correct,
            )
            reply = self._stub.FpgaFaultInjection(request)

            words = [
                FpgaFiWordSummary(
                    ws.far,
                    ws.word_index,
                    ws.bit_index,
                    ws.golden_word_value,
                    ws.injected_word_value,
                    ws.is_essential,
                )
                for ws in reply.word_summaries
            ]
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform fault injection: {_rpc_detail(e)}"
            ) from e

        # The reply carries only the per-word list, so derive the aggregate
        # counts client-side. Wire real server counts here if they exist.
        faults_injected = len(words)

        corrected = faults_injected if session.correct else 0
        return FpgaFiSummary(session, faults_injected, corrected, words)

    # -- frame utilities --------------------------------------------------- #
    def exclude_frames(self, fars: list[int]) -> None:
        """Exclude Frame Addresses from bulk operations
        (RPC: ``FpgaExcludeFars``). ``inject_at`` is unaffected.
        """
        try:
            request = skraft_client_pb2.FpgaFarListExcludeRequest(fars=fars)
            self._stub.FpgaExcludeFars(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to exclude the provided FARs: {_rpc_detail(e)}"
            ) from e

    # -- boundary scan ----------------------------------------------------- #
    def write_bscan(self, bscan: BscanPrimitive, value: int) -> bytes:
        """Write ``value`` into the given USER register
        (RPC: ``FpgaWriteBscan`` via ``BscanPrimitive.shift_in``).
        """
        try:
            total_bytes = bscan.size_in_bits // 8 or 1
            value_bytes = value.to_bytes(total_bytes, "big")
            return bscan.shift_in(self._stub, value_bytes)
        except grpc.RpcError as e:
            raise BscanError(
                f"failed to write bscan register {bscan.user_register_id}: "
                f"{_rpc_detail(e)}"
            ) from e

    def read_bscan(self, bscan: BscanPrimitive) -> bytes:
        """Read the current value of the given USER register
        (RPC: ``FpgaReadBscan`` via ``BscanPrimitive.shift_in``).
        """
        try:
            total_bytes = bscan.size_in_bits // 8 or 1
            dummy = bytes(total_bytes)
            return bscan.shift_in(self._stub, dummy, True)
        except grpc.RpcError as e:
            raise BscanError(
                f"failed to read bscan register {bscan.user_register_id}: "
                f"{_rpc_detail(e)}"
            ) from e


# --------------------------------------------------------------------------- #
# SkraftFpga
# --------------------------------------------------------------------------- #
class SkraftFpga:
    """Client/supervisor for a single SK-RAFT server connection.

    Usable as a context manager::

        with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
            with client.attach("xcku040") as dev:
                ...
    """

    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self._channel = None
        self._stub = None

    # -- connection lifecycle --------------------------------------------- #
    @classmethod
    def connect(cls, ip: str, port: int) -> "SkraftFpga":
        """Create a client and open the channel to the SK-RAFT server."""
        client = cls(ip, port)
        try:
            client._channel = grpc.insecure_channel(f"{ip}:{port}")
            client._stub = skraft_client_pb2_grpc.SKRaftFpgaStub(
                client._channel
            )
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to connect to gRPC server at {ip}:{port}: "
                f"{_rpc_detail(e)}"
            ) from e
        return client

    def __enter__(self) -> "SkraftFpga":
        return self

    def __exit__(self, *exc_info) -> None:
        self.disconnect()

    def disconnect(self) -> None:
        """Close the channel to the server."""
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None

    # -- device acquisition ------------------------------------------------ #
    def attach(self, device_part_number: str,
               programmer_part_number: str = "FT2XX") -> FpgaDevice:
        """Reserve a specific device by part number, via the given programmer
        (RPC: ``FpgaConnect``). Returns a context-manageable ``FpgaDevice``.
        """
        try:
            request = skraft_client_pb2.FpgaDeviceDetails(
                device_part_number=device_part_number,
                programmer_part_number=programmer_part_number,
            )
            self._stub.FpgaConnect(request)
        except grpc.RpcError as e:
            raise DeviceReservationError(
                f"failed to reserve device {device_part_number}: "
                f"{_rpc_detail(e)}"
            ) from e
        return FpgaDevice(self._stub, device_part_number)

    # -- standalone frame utility ----------------------------------------- #
    def extract_fars_from_bitstream(self,
                                    bitstream_path: ServerPath) -> list[int]:
        """Extract every Frame Address in a bitstream file
        (RPC: ``FpgaExtractFarsFromBitstream``). Requires per-frame CRC in the
        design.
        """
        try:
            request = skraft_client_pb2.FpgaFarListExtractRequest(
                bitstream_path=str(bitstream_path),
            )
            reply = self._stub.FpgaExtractFarsFromBitstream(request)
            return list(reply.fars)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to extract FARs from {bitstream_path}: "
                f"{_rpc_detail(e)}"
            ) from e
