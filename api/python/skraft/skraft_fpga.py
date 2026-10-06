# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024-2026 SOLIDKOSMOS S.A.

from __future__ import annotations

import hashlib
import os
from typing import Optional

import grpc
from google.protobuf import empty_pb2

from . import datatypes
from . import skraft_client_pb2
from . import skraft_client_pb2_grpc
from .datatypes import (
    BscanPrimitive,
    Design,
    FpgaFar7series,
    FpgaFarUltraScale,
    FpgaFiSession,
    FpgaFiSummary,
    FpgaFrame,
    FpgaInjectionReport,
    FpgaPblock,
    FpgaPblockAreaRange,
    FpgaPblockFar,
    FpgaPblockRange,
    FpgaRandomInjectionReport,
    FpgaScrubReport,
    FpgaScrubSummary,
    FpgaScrubWordSummary,
    FpgaWord,
    FpgaFiWordSummary,
    TargetMemory,
    ServerPath,
    ScrubbingType,
    ReadbackOption,
)
from .exceptions import (
    BscanError,
    ConnectionFailedError,
    DesignFileError,
    DeviceReservationError,
    FrameAddressError,
)


SK_RAFT_VERSION = "1.0.0.alpha.11-3-g9355663"

# The size of each chunk that the client streams during a design file upload.
_UPLOAD_CHUNK_SIZE = 1 << 20

def _rpc_detail(error: grpc.RpcError) -> str:
    """Get the detail string of a gRPC error (best effort)."""
    try:
        return error.details()  # type: ignore[attr-defined]
    except Exception:
        return str(error)


def _kind_from_area(target: TargetMemory) -> int:
    """Map a :class:`TargetMemory` to the wire ``FpgaTargetKind`` enum.

    ``FpgaInjectionTarget`` holds a single ``kind``. Thus, a specific
    injection can have a maximum of one storage-element flag.
    """
    storage_flags = [
        (TargetMemory.FF, skraft_client_pb2.FPGA_TARGET_KIND_FLIP_FLOP),
        (TargetMemory.LUTRAM, skraft_client_pb2.FPGA_TARGET_KIND_LUTRAM),
        (TargetMemory.BRAM, skraft_client_pb2.FPGA_TARGET_KIND_BRAM),
    ]
    selected = [kind for flag, kind in storage_flags if target & flag]
    if len(selected) > 1:
        raise ValueError(
            "a specific injection targets exactly one memory kind; got a "
            f"combined TargetMemory: {target!r}"
        )
    if selected:
        return selected[0]
    return skraft_client_pb2.FPGA_TARGET_KIND_CRAM


def _injection_options(
    target: TargetMemory, pblock: Optional[str]
) -> skraft_client_pb2.FpgaInjectionOptions:
    """Build the wire ``FpgaInjectionOptions`` for ``target``. If a
    ``pblock`` is given, limit the injection to that pblock of the XDC."""
    return skraft_client_pb2.FpgaInjectionOptions(
        essentials=bool(target & TargetMemory.ESSENTIAL_CRAM),
        include_flip_flops=bool(target & TargetMemory.FF),
        include_lutrams=bool(target & TargetMemory.LUTRAM),
        include_brams=bool(target & TargetMemory.BRAM),
        include_pblock=pblock is not None,
        pblock_name=pblock or "",
    )


# --------------------------------------------------------------------------- #
# FpgaDevice
# --------------------------------------------------------------------------- #
class FpgaDevice:
    """A reserved FPGA device. Get it with :meth:`SkraftFpga.attach`.

    Use it as a context manager to always release the reservation::

        with client.attach("210183A1B2C3A") as dev:
            dev.uploadDesignToServer(Design(bit="top.bit", ebd="top.ebd"))
            dev.programFPGA()
    """

    # This table maps a Design field to an FpgaFileType enum value. The
    # client sends this value with the file through the FpgaUploadDesignFile
    # RPC.
    _FILE_TYPES = {
        "bit": skraft_client_pb2.FPGA_FILE_TYPE_BIT,
        "ebd": skraft_client_pb2.FPGA_FILE_TYPE_EBD,
        "ll": skraft_client_pb2.FPGA_FILE_TYPE_LL,
        "xdc": skraft_client_pb2.FPGA_FILE_TYPE_XDC,
        "rbd": skraft_client_pb2.FPGA_FILE_TYPE_RBD,
        "msd": skraft_client_pb2.FPGA_FILE_TYPE_MSD,
    }

    # This table maps a TargetMemory to the FpgaBitCategory enum value that
    # the FpgaGetBitCount RPC uses.
    _BIT_CATEGORIES = {
        TargetMemory.CRAM: skraft_client_pb2.FPGA_BIT_CATEGORY_CRAM,
        TargetMemory.ESSENTIAL_CRAM:
            skraft_client_pb2.FPGA_BIT_CATEGORY_ESSENTIAL_CRAM,
        TargetMemory.BRAM: skraft_client_pb2.FPGA_BIT_CATEGORY_BRAM,
        TargetMemory.FF: skraft_client_pb2.FPGA_BIT_CATEGORY_FLIP_FLOP,
        TargetMemory.LUTRAM: skraft_client_pb2.FPGA_BIT_CATEGORY_LUTRAM,
    }

    def __init__(self, stub, serial_number: str, part_number: str = ""):
        self._stub = stub
        self.serial_number = serial_number
        self.part_number = part_number
        self._design = Design()

    # -- lifecycle --------------------------------------------------------- #
    def __enter__(self) -> "FpgaDevice":
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()

    def release(self) -> None:
        """Release the reserved resources of the device
        (RPC: ``FpgaClose``)."""
        try:
            self._stub.FpgaClose(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to release device: {_rpc_detail(e)}"
            ) from e

    # -- design files ------------------------------------------------------ #
    def uploadDesignToServer(self, design: Design) -> None:
        """Upload each file of ``design`` to the server for this device
        (RPC: ``FpgaUploadDesignFile``, one stream for each file).
        The server reads the files when the device is programmed.
        """
        for field_name, file_type in self._FILE_TYPES.items():
            path = getattr(design, field_name)
            if path is not None:
                self._upload_file(path, file_type)
        self._design = design

    def _upload_file(self, path: str, file_type: int) -> None:
        # Calculate the hash of the file first. After the upload, the server
        # uses the hash to make sure that the file is correct.
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(_UPLOAD_CHUNK_SIZE), b""):
                    digest.update(chunk)
        except OSError as e:
            raise DesignFileError(
                f"failed to read design file {path}: {e}"
            ) from e

        def requests():
            yield skraft_client_pb2.UploadDesignFileRequest(
                info=skraft_client_pb2.FpgaDesignFileInfo(
                    type=file_type,
                    relative_path=os.path.basename(path),
                    size=os.path.getsize(path),
                    sha256=digest.hexdigest(),
                )
            )
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(_UPLOAD_CHUNK_SIZE), b""):
                    yield skraft_client_pb2.UploadDesignFileRequest(chunk=chunk)

        try:
            self._stub.FpgaUploadDesignFile(requests())
        except grpc.RpcError as e:
            raise DesignFileError(
                f"failed to upload design file {path}: {_rpc_detail(e)}"
            ) from e

    @property
    def design(self) -> Design:
        """The design that was last uploaded to the server."""
        return self._design

    # -- programming & readback ------------------------------------------- #
    def programFPGA(self) -> None:
        """Program the device with the uploaded bitstream
        (RPC: ``FpgaProgram``)."""
        self._design.require("bit")
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
        """Do a shutdown of the FPGA device (RPC: ``FpgaShutdown``)."""
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
                start_frame_address=0, # The server ignores this value.
                end_frame_address=0,   # The server ignores this value.
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
        # FpgaFrame.words is a flat repeated uint32. The wire format does
        # not have the FpgaWord wrapper message any more.
        frames: list[FpgaFrame] = []
        for frame in reply.frames:
            words = [FpgaWord(value) for value in frame.words]
            frames.append(FpgaFrame(frame.frame_address, words))
        return frames

    # -- device queries (properties) -------------------------------------- #
    @property
    def cram_bits(self) -> int:
        """The total number of CRAM bits in the active device
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_CRAM``)."""
        return self.bit_count(TargetMemory.CRAM)

    @property
    def essential_cram_bits(self) -> int:
        """The number of essential CRAM bits for the loaded design
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_ESSENTIAL_CRAM``).
        The EBD file is necessary."""
        return self.bit_count(TargetMemory.ESSENTIAL_CRAM)

    @property
    def ff_bits(self) -> int:
        """The number of flip-flop bits that the loaded design uses
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_FLIP_FLOP``).
        The LL file is necessary."""
        return self.bit_count(TargetMemory.FF)

    @property
    def bram_bits(self) -> int:
        """The number of BRAM bits that the loaded design uses
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_BRAM``).
        The LL file is necessary."""
        return self.bit_count(TargetMemory.BRAM)

    @property
    def lutram_bits(self) -> int:
        """The number of LUTRAM bits that the loaded design uses
        (RPC: ``FpgaGetBitCount`` with ``FPGA_BIT_CATEGORY_LUTRAM``).
        The LL file is necessary."""
        return self.bit_count(TargetMemory.LUTRAM)

    def all_bit_counts(self, pblock: Optional[str] = None) -> dict[str, int]:
        """Return all bit statistics of the loaded design, for the full
        device (RPC: ``FpgaGetAllBitCounts``) or only for the named
        ``pblock`` of the XDC (RPC: ``FpgaGetBitCount`` for each memory).

        For a pblock, each memory is intersected with the pblock. For
        example, ``flip_flop_bits`` counts the bits in the pblock that the
        LL file marks as flip-flops. A memory without an uploaded design
        file gives a count of 0.
        """
        if pblock is not None:
            self._design.require("xdc")
            counts = {
                "cram_bits": self._count(TargetMemory.CRAM, pblock),
                "essential_cram_bits":
                    self._count(TargetMemory.ESSENTIAL_CRAM, pblock),
                "bram_bits": self._count(TargetMemory.BRAM, pblock),
                "flip_flop_bits": self._count(TargetMemory.FF, pblock),
                "lutram_bits": self._count(TargetMemory.LUTRAM, pblock),
            }
            counts["pblock_bits"] = counts["cram_bits"]
            counts["pblock_essential_bits"] = counts["essential_cram_bits"]
            return counts

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
            "pblock_bits": reply.pblock_bits,
            "pblock_essential_bits": reply.pblock_essential_bits,
        }

    def bit_count(self, target: TargetMemory,
                  pblock: Optional[str] = None) -> int:
        """Count the ``target`` bits of the loaded design, for the full
        device or only for the named ``pblock`` of the XDC
        (RPC: ``FpgaGetBitCount``).

        ``target`` must be a single memory. ``CRAM`` counts all bits.
        ``ESSENTIAL_CRAM`` counts the essential bits (EBD file). ``FF``,
        ``LUTRAM`` and ``BRAM`` count the storage bits (LL file). With a
        ``pblock``, the method counts only the target bits in the pblock.
        For example, with ``FF`` it counts the bits in the pblock that the
        LL file marks as flip-flops.
        """
        if target not in self._BIT_CATEGORIES:
            raise ValueError(
                f"bit_count takes a single TargetMemory, got {target!r}"
            )
        self._design.require(*target.required_design_files,
                             *(("xdc",) if pblock else ()))
        return self._count(target, pblock)

    def _count(self, target: TargetMemory, pblock: Optional[str]) -> int:
        try:
            request = skraft_client_pb2.FpgaBitCountRequest(
                category=self._BIT_CATEGORIES[target],
                pblock_name=pblock or "",
            )
            return self._stub.FpgaGetBitCount(request).value
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to count the {target.name} bits: {_rpc_detail(e)}"
            ) from e

    # -- fault injection --------------------------------------------------- #
    def inject_random(
        self, target: TargetMemory, pblock: Optional[str] = None
    ) -> FpgaRandomInjectionReport:
        """Inject a single random SEU into ``target``
        (RPC: ``FpgaRandomBitFlip``). If a ``pblock`` is given, the
        injection is limited to that pblock of the XDC.
        """
        self._design.require(*target.required_design_files,
                             *(("xdc",) if pblock else ()))
        try:
            request = _injection_options(target, pblock)
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

    def inject_exhaustive(
        self, target: TargetMemory, pblock: Optional[str] = None
    ) -> tuple[list[FpgaInjectionReport], int]:
        """Inject an upset into each bit of ``target``
        (RPC: ``FpgaExhaustiveBitFlip``). If a ``pblock`` is given, the
        injection is limited to that pblock of the XDC.

        This method uses the same ``FpgaInjectionOptions`` selector as
        :meth:`inject_random`. Thus, you can combine memories in ``target``.
        The method returns the report for each location and the
        ``injected_bit_count`` from the server. ``injected_bit_count`` is the
        reference value. It can be different from ``len(reports)`` if the
        server truncates or aggregates the target list.
        """
        self._design.require(*target.required_design_files,
                             *(("xdc",) if pblock else ()))
        try:
            request = _injection_options(target, pblock)
            reply = self._stub.FpgaExhaustiveBitFlip(request)
            reports = [
                FpgaInjectionReport(
                    t.frame_address,
                    t.word_index,
                    t.bit_index,
                    target,
                    t.net_name or None,
                )
                for t in reply.targets
            ]
            return reports, reply.injected_bit_count
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to perform exhaustive bit flip: {_rpc_detail(e)}"
            ) from e

    def inject_at(self, far: int, word_index: int, bit_index: int,
                  target: TargetMemory) -> FpgaInjectionReport:
        """Inject an upset at a specific ``(far, word_index, bit_index)``
        location, constrained to ``target`` (RPC: ``FpgaBitFlip``).

        The wire message holds a single ``FpgaTargetKind`` enum, not three
        booleans. Thus, ``target`` must name a maximum of one storage-element
        memory (``FF``, ``LUTRAM`` or ``BRAM``). A ``target`` without a
        storage-element memory is treated as CRAM.
        """
        self._design.require(*target.required_design_files)
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
        # FpgaBitFlip returns nothing. Return the requested location.
        return FpgaInjectionReport(far, word_index, bit_index, target)

    def scrub(self, option: ScrubbingType, scrub_cycle: int,
              duration_ms: int, session_id: str = "") -> FpgaScrubReport:
        """Run a scrubbing session (RPC: ``FpgaScrubbing``).

        ``ESSENTIAL`` scrubbing must have the EBD file. The server uses the
        EBD file to find which upsets are essential and which are not.
        """
        if option == ScrubbingType.ESSENTIAL:
            self._design.require("ebd")
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
        """Run a user-defined fault injection campaign
        (RPC: ``FpgaFaultInjection``).
        """
        if session.essential:
            self._design.require("ebd")
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

        # The reply holds only the list of words. Thus, the client calculates
        # the total counts. If the server gives real counts, use them here.
        faults_injected = len(words)

        corrected = faults_injected if session.correct else 0
        return FpgaFiSummary(session, faults_injected, corrected, words)

    # -- frame utilities --------------------------------------------------- #
    def essential_frames(self) -> list[FpgaFrame]:
        """Return the frames that come from the essential bits (EBD) file
        (RPC: ``FpgaEssentialFrames``).

        A set bit in a returned word marks an essential bit at that position.
        Thus, the frames are masks, not configuration data. The EBD file is
        necessary.
        """
        self._design.require("ebd")
        try:
            reply = self._stub.FpgaEssentialFrames(empty_pb2.Empty())
            return self._frames_from_reply(reply)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the essential frames: {_rpc_detail(e)}"
            ) from e

    def mask_frames(self) -> list[FpgaFrame]:
        """Return the frames that come from the readback mask (MSD) file
        (RPC: ``FpgaMaskFrames``).

        A set bit marks a position to ignore when you compare a readback
        with the golden data. The MSD file is necessary.
        """
        self._design.require("msd")
        try:
            reply = self._stub.FpgaMaskFrames(empty_pb2.Empty())
            return self._frames_from_reply(reply)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the mask frames: {_rpc_detail(e)}"
            ) from e

    def far_list(self) -> list[int]:
        """Return all frame addresses (FAR) of the device
        (RPC: ``FpgaFarList``)."""
        try:
            reply = self._stub.FpgaFarList(empty_pb2.Empty())
            return list(reply.fars)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to get the FAR list: {_rpc_detail(e)}"
            ) from e

    def exclude_frames(self, fars: list[int]) -> None:
        """Exclude frame addresses from bulk operations
        (RPC: ``FpgaExcludeFars``). This exclusion has no effect on
        ``inject_at``.
        """
        try:
            request = skraft_client_pb2.FpgaFarListExcludeRequest(fars=fars)
            self._stub.FpgaExcludeFars(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to exclude the provided FARs: {_rpc_detail(e)}"
            ) from e

    def pblocks(self) -> list[FpgaPblock]:
        """List all pblocks that the constraints declare
        (RPC: ``FpgaGetPblocks``).

        Each returned :class:`FpgaPblock` holds its name and its range
        clauses. You can give a clause to :meth:`pblock_by_clause` to get the
        frames that the clause occupies. The XDC file is necessary.
        """
        self._design.require("xdc")
        try:
            reply = self._stub.FpgaGetPblocks(empty_pb2.Empty())
            return [
                FpgaPblock(
                    pblock.name,
                    [clause.value for clause in pblock.clauses],
                )
                for pblock in reply.pblocks
            ]
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to get the pblocks: {_rpc_detail(e)}"
            ) from e

    def pblock_by_clause(self, clause: str) -> list[FpgaPblockFar]:
        """Find the frames that a pblock clause occupies
        (RPC: ``FpgaGetPblockFarsByClause``).

        ``clause`` is the pblock range expression as written in the
        constraints, for example ``"SLICE_X0Y0:SLICE_X7Y49"``. Each returned
        :class:`FpgaPblockFar` names a frame address and the word/bit
        rectangles in that frame that the pblock covers. You can use these
        FAR, word and bit values with :meth:`inject_at` to limit injection
        to one region of the device. The XDC file is necessary.
        """
        self._design.require("xdc")
        try:
            request = skraft_client_pb2.FpgaPblockClause(value=clause)
            reply = self._stub.FpgaGetPblockFarsByClause(request)
            return [
                FpgaPblockFar(
                    entry.far,
                    [
                        FpgaPblockAreaRange(
                            self._pblock_range(area.bit_range),
                            self._pblock_range(area.word_range),
                        )
                        for area in entry.occupied_area
                    ],
                )
                for entry in reply.fars
            ]
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to get the pblock for clause {clause!r}: "
                f"{_rpc_detail(e)}"
            ) from e

    @staticmethod
    def _pblock_range(message) -> FpgaPblockRange:
        return FpgaPblockRange(getattr(message, "from"), message.to)

    def write_bscan(self, bscan: BscanPrimitive, value: int) -> bytes:
        """Write ``value`` into the given USER register
        (RPC: ``FpgaWriteBscan`` through ``BscanPrimitive.shift_in``).
        """
        try:
            total_bytes = -(-bscan.size_in_bits // 8) or 1
            value_bytes = value.to_bytes(total_bytes, "big")
            return bscan.shift_in(self._stub, value_bytes)
        except grpc.RpcError as e:
            raise BscanError(
                f"failed to write bscan register {bscan.user_register_id}: "
                f"{_rpc_detail(e)}"
            ) from e

    def read_bscan(self, bscan: BscanPrimitive) -> bytes:
        """Read the current value of the given USER register
        (RPC: ``FpgaReadBscan`` through ``BscanPrimitive.shift_in``).
        """
        try:
            total_bytes = -(-bscan.size_in_bits // 8) or 1
            dummy = bytes(total_bytes)
            return bscan.shift_in(self._stub, dummy, True)
        except grpc.RpcError as e:
            raise BscanError(
                f"failed to read bscan register {bscan.user_register_id}: "
                f"{_rpc_detail(e)}"
            ) from e

    def read_register(self, reg_addr: int) -> int:
        try:
            request = skraft_client_pb2.FpgaReadRegisterRequest(addr=reg_addr)
            reply = self._stub.FpgaReadRegister(request)

            return reply.value
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to read register: {_rpc_detail(e)}"
            ) from e

    def write_register(self, reg_addr: int, value: int):
        try:
            request = skraft_client_pb2.FpgaWriteRegisterRequest(addr=reg_addr, 
                                                                 value=value)
            self._stub.FpgaWriteRegister(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to write register: {_rpc_detail(e)}"
            ) from e

    def decode_far(self, far: int) -> FpgaFar7series | FpgaFarUltraScale:
        try:
            request = skraft_client_pb2.FpgaFarDecodeRequest(value=far)
            reply = self._stub.FpgaDecodeFrameAddress(request)

            if reply.far_model == skraft_client_pb2.FPGA_7SERIES_FAR_MODEL:
                far_decoded = FpgaFar7series(
                                far,
                                reply.block_type,
                                reply.top_bottom,
                                reply.row_address,
                                reply.column_address,
                                reply.minor_address)
            else:
                far_decoded = FpgaFarUltraScale(
                                far,
                                reply.block_type,
                                reply.row_address,
                                reply.column_address,
                                reply.minor_address)

            return far_decoded

        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to decode Frame Address: {_rpc_detail(e)}"
            ) from e

# --------------------------------------------------------------------------- #
# SkraftFpga
# --------------------------------------------------------------------------- #
class SkraftFpga:
    """The client and supervisor for a single connection to an SK-RAFT server.

    You can use it as a context manager::

        with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
            with client.attach("210183A1B2C3A") as dev:
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
            # A full readback of a large device is larger than the default
            # limit of 4 MB.
            client._channel = grpc.insecure_channel(
                f"{ip}:{port}",
                options=[("grpc.max_receive_message_length", -1),
                         ("grpc.max_send_message_length", -1)],
            )
            client._stub = skraft_client_pb2_grpc.SKRaftFpgaStub(
                client._channel
            )
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to connect to gRPC server at {ip}:{port}: "
                f"{_rpc_detail(e)}"
            ) from e

        if SK_RAFT_VERSION not in client.version():
            print(f"WARNING: expected version {SK_RAFT_VERSION}, got {client.version()}")

        return client

    def version(self) -> str:
        try:
            reply = self._stub.Version(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the server version from "
                f"{self.ip}:{self.port}: {_rpc_detail(e)}"
            ) from e
        return reply.version

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

    def get_devices(self) -> list[FpgaDevice]:
        try:
            reply = self._stub.FpgaGetDevices(empty_pb2.Empty())

            return [
                FpgaDevice(self._stub, entry.serial_number, entry.part_number)
                for entry in reply.devices
            ]
        except grpc.RpcError as e:
            self._release_programmers()
            raise DeviceReservationError(
                    f"failed to get devices: "
                    f"{_rpc_detail(e)}"
            ) from e

    # -- device acquisition ------------------------------------------------ #
    def attach(self, serial_number: str) -> FpgaDevice:
        """Reserve the device with the given serial number, for example the
        ``210183A1B2C3A`` of the Vivado target ``Digilent/210183A1B2C3A``
        (RPCs: ``FpgaConnect``, ``FpgaSelectDevice``). The method returns an
        ``FpgaDevice`` that you can use as a context manager.

        If no device has this serial number, the error lists the serial
        numbers of the connected devices.
        """
        try:
            self._stub.FpgaConnect(empty_pb2.Empty())
            self._stub.FpgaSelectDevice(
                skraft_client_pb2.FpgaDeviceDetails(
                    device_serial_number=serial_number,
                )
            )
        except grpc.RpcError as e:
            self._release_programmers()
            raise DeviceReservationError(
                f"failed to reserve device {serial_number}: "
                f"{_rpc_detail(e)}"
            ) from e
        return FpgaDevice(self._stub, serial_number)

    def _release_programmers(self) -> None:
        """Close the programmers that ``FpgaConnect`` opened, after a failed
        :meth:`attach` (best effort)."""
        try:
            self._stub.FpgaClose(empty_pb2.Empty())
        except grpc.RpcError:
            pass

    # -- standalone frame utility ----------------------------------------- #
    def extract_fars_from_bitstream(self,
                                    bitstream_path: ServerPath) -> list[int]:
        """Extract all frame addresses from a bitstream file
        (RPC: ``FpgaExtractFarsFromBitstream``). The design must use
        per-frame CRC.
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

