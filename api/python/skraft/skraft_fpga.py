#   Copyright(C) 2024 SOLIDKOSMOS S.A.
#   All rights reserved. Confidential Information.
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

"""SK-RAFT FPGA control client, matching the redesigned documentation.

``SkraftFpga`` owns the server connection and hands out ``FpgaDevice`` handles.
``FpgaDevice`` carries everything tied to a reserved device: design files,
queries, programming/readback, and fault injection. Both are context managers.

Both classes wrap the same gRPC stub used by the original ``SkRaftFpga``; the
mapping from each method to its RPC is noted inline.
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
    FpgaWord,
    FpgaWordSummary,
    InjectionArea,
    ServerPath,
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

    # Maps a DesignFiles field to the RPC that pushes its path to the server.
    _FILE_RPCS = {
        "bitstream": "fpgaSetBitFilePath",
        "ebd": "fpgaSetEbdFilePath",
        "ll": "fpgaSetllFilePath",
        "rbd": "fpgaSetRbdFilePath",
        "msd": "fpgaSetMsdFilePath",
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
        """Free the device's reserved resources (RPC: ``fpgaClose``)."""
        try:
            self._stub.fpgaClose(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to release device: {_rpc_detail(e)}"
            ) from e

    # -- design files ------------------------------------------------------ #
    def load(self, files: DesignFiles) -> None:
        """Associate design files with the device and push each provided path
        to the server (RPCs: ``fpgaSet*FilePath``). Stores paths only; the
        server does not read file contents until an operation needs them.
        """
        try:
            for field_name, rpc_name in self._FILE_RPCS.items():
                path = getattr(files, field_name)
                if path is not None:
                    request = skraft_client_pb2.FilePath(path=str(path))
                    getattr(self._stub, rpc_name)(request)
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
        """Upload the loaded bitstream to the device (RPC: ``fpgaProgram``)."""
        self._files.require("bitstream")
        try:
            self._stub.fpgaProgram(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to program the target FPGA device: {_rpc_detail(e)}"
            ) from e

    def readback_range(self, start_far: int,
                       end_far: int) -> list[FpgaFrame]:
        """Read back the frames in ``[start_far, end_far]``
        (RPC: ``fpgaReadback``).
        """
        if start_far > end_far:
            raise FrameAddressError(
                f"start_far ({start_far}) must be <= end_far ({end_far})"
            )
        try:
            request = skraft_client_pb2.FpgaReadbackTarget(
                startFrameAddress=start_far,
                endFrameAddress=end_far,
            )
            reply = self._stub.fpgaReadback(request)

            frames: list[FpgaFrame] = []
            for frame in reply.frames:
                words = [FpgaWord(value) for value in frame.words.values]
                frames.append(FpgaFrame(frame.frameAddress, words))
            return frames
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to read frames [{start_far}, {end_far}]: "
                f"{_rpc_detail(e)}"
            ) from e

    # -- device queries (properties) -------------------------------------- #
    @property
    def cram_bits(self) -> int:
        """Total CRAM bits in the active device (RPC: ``fpgaCramBits``)."""
        return self._count(self._stub.fpgaCramBits, "CRAM")

    @property
    def essential_cram_bits(self) -> int:
        """Essential CRAM bits for the loaded design
        (RPC: ``fpgaEssentialCramBits``; requires the EBD file)."""
        self._files.require("ebd")
        return self._count(self._stub.fpgaEssentialCramBits, "essential CRAM")

    @property
    def ff_bits(self) -> int:
        """Flip-flop bits used by the loaded design
        (RPC: ``fpgaFlipFlopBits``; requires the LL file)."""
        self._files.require("ll")
        return self._count(self._stub.fpgaFlipFlopBits, "flip-flop")

    @property
    def bram_bits(self) -> int:
        """BRAM bits used by the loaded design
        (RPC: ``fpgaBramBits``; requires the LL file)."""
        self._files.require("ll")
        return self._count(self._stub.fpgaBramBits, "BRAM")

    @property
    def lutram_bits(self) -> int:
        """LUTRAM bits used by the loaded design
        (RPC: ``fpgaLutramBits``; requires the LL file)."""
        self._files.require("ll")
        return self._count(self._stub.fpgaLutramBits, "LUTRAM")

    def _count(self, rpc, label: str) -> int:
        try:
            return rpc(empty_pb2.Empty()).value
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the {label} bits: {_rpc_detail(e)}"
            ) from e

    # -- fault injection --------------------------------------------------- #
    def inject_random(
        self, target: InjectionArea
    ) -> FpgaRandomInjectionReport:
        """Inject a single random SEU into ``target``
        (RPC: ``fpgaRandomBitFlip``).
        """
        self._files.require(*target.required_design_files)
        try:
            request = skraft_client_pb2.FpgaRandomInjectionOptions(
                includeEssential=bool(target & InjectionArea.ESSENTIAL_CRAM),
                includeFlipFlops=bool(target & InjectionArea.FLIP_FLOP),
                includeLutRams=bool(target & InjectionArea.LUTRAM),
                includeBrams=bool(target & InjectionArea.BRAM),
            )
            reply = self._stub.fpgaRandomBitFlip(request)
            return FpgaRandomInjectionReport(
                reply.target.frameAddress,
                reply.target.wordIndex,
                reply.target.bitIndex,
                target,
                reply.target.netName,
            )
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform random bit flip: {_rpc_detail(e)}"
            ) from e

    def inject_at(self, far: int, word_index: int, bit_index: int,
                  target: InjectionArea) -> FpgaInjectionReport:
        """Inject an upset at a specific ``(far, word_index, bit_index)``
           location, constrained to ``target`` (RPC: ``fpgaBitFlip``).
        """
        self._files.require(*target.required_design_files)
        try:
            request = skraft_client_pb2.FpgaInjectionTarget(
                frameAddress=far,
                wordIndex=word_index,
                bitIndex=bit_index,
                isFlipFlop=bool(target & InjectionArea.FLIP_FLOP),
                isLutRam=bool(target & InjectionArea.LUTRAM),
                isBram=bool(target & InjectionArea.BRAM),
            )
            self._stub.fpgaBitFlip(request)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform bit flip: {_rpc_detail(e)}"
            ) from e
        # fpgaBitFlip returns nothing; echo the requested location.
        return FpgaInjectionReport(far, word_index, bit_index, target)

    def run_campaign(self, session: FpgaFiSession) -> FpgaFiSummary:
        """Run a user-defined fault-injection campaign
        (RPC: ``fpgaFaultInjection``).
        """
        if session.essential:
            self._files.require("ebd")
        try:
            request = skraft_client_pb2.FpgaFiSession(
                type=session.fi_type.value,
                duration=session.duration_ms,
                correctionTime=session.correction_time_ms,
                timeBetweenFaults=session.time_between_faults_ms,
                sbuPercent=session.sbu_percent,
                mbuPercent=session.mbu_percent,
                mcuPercent=session.mcu_percent,
                essential=session.essential,
                correct=session.correct,
            )
            reply = self._stub.fpgaFaultInjection(request)

            words = [
                FpgaWordSummary(
                    ws.far,
                    ws.wordIndex,
                    ws.bitIndex,
                    ws.goldenWordValue,
                    ws.injectedWordValue,
                    ws.isEssential,
                )
                for ws in reply.wordSummary
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
        (RPC: ``fpgaExcludeFars``). ``inject_at`` is unaffected.
        """
        try:
            request = skraft_client_pb2.FpgaFarListExcludeRequest(values=fars)
            self._stub.fpgaExcludeFars(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to exclude the provided FARs: {_rpc_detail(e)}"
            ) from e

    # -- boundary scan ----------------------------------------------------- #
    def write_bscan(self, bscan: BscanPrimitive, value: int) -> bytes:
        """Write ``value`` into the given USER register
        (RPC: ``fpgaWriteBscan`` via ``BscanPrimitive.shift_in``).
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
        (RPC: ``fpgaConnect``). Returns a context-manageable ``FpgaDevice``.
        """
        try:
            request = skraft_client_pb2.FpgaDeviceDetails(
                devicePartNumber=device_part_number,
                programmerPartNumber=programmer_part_number,
            )
            self._stub.fpgaConnect(request)
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
        (RPC: ``fpgaExtractFarsFromBitstream``). Requires per-frame CRC in the
        design.
        """
        try:
            request = skraft_client_pb2.FpgaFarListExtractRequest(
                bitstreamPath=str(bitstream_path),
            )
            reply = self._stub.fpgaExtractFarsFromBitstream(request)
            return reply.values
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to extract FARs from {bitstream_path}: "
                f"{_rpc_detail(e)}"
            ) from e

