"""
Client for the SK-RAFT server.

Connects to an SK-RAFT server over gRPC, reserves FPGA devices and runs
operations on them, such as programming, readback, fault injection and
scrubbing.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional, overload

import grpc
from google.protobuf import empty_pb2

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
    ScrubbingType,
    ReadbackOption,
    XadcSensor,
    XadcSensorSelector,
)
from .exceptions import (
    BscanError,
    ConnectionFailedError,
    DesignFileError,
    DeviceReservationError,
    FrameAddressError,
    XadcError,
)


SK_RAFT_VERSION = "1.0.0.alpha.11-3-g9355663"

# The size of each chunk that the client streams during a design file upload.
_UPLOAD_CHUNK_SIZE = 1 << 20

def _rpc_detail(error: grpc.RpcError) -> str:
    """
    Get a readable description of a gRPC error.

    Falls back to the general text of the error if the detailed
    description is not available.

    Parameters:
        error (grpc.RpcError): The error raised by a gRPC call.

    Returns:
        str: The description of the error.
    """
    try:
        return error.details()  # type: ignore[attr-defined]
    except Exception:
        return str(error)

def _read_pem(path: Optional[str]) -> Optional[bytes]:
    """
    Read a PEM file for the TLS connection.

    Parameters:
        path (Optional[str]): The path of the PEM file, if any.

    Returns:
        Optional[bytes]: The contents of the file, or None if no path is
            given.

    Raises:
        OSError: If the file cannot be read.
    """
    if path is None:
        return None
    with open(path, "rb") as f:
        return f.read()


def _kind_from_area(target: TargetMemory) -> int:
    """
    Convert a target memory selection into the matching wire target kind.

    A single injection can target only one kind of storage element. If no
    storage element is selected, the configuration memory (CRAM) is used.

    Parameters:
        target (TargetMemory): The memory selection to convert.

    Returns:
        int: The wire value for the selected target kind.

    Raises:
        ValueError: If more than one kind of storage element is selected.
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
    """
    Build the injection options to send to the server.

    Parameters:
        target (TargetMemory): The memories that the injection may target.
            Several memories can be combined.
        pblock (Optional[str]): The name of a pblock from the constraints
            (XDC) file. If given, the injection is limited to that pblock.

    Returns:
        skraft_client_pb2.FpgaInjectionOptions: The options message for
            the server.
    """
    return skraft_client_pb2.FpgaInjectionOptions(
        essentials=bool(target & TargetMemory.ESSENTIAL_CRAM),
        include_flip_flops=bool(target & TargetMemory.FF),
        include_lutrams=bool(target & TargetMemory.LUTRAM),
        include_brams=bool(target & TargetMemory.BRAM),
        include_pblock=pblock is not None,
        pblock_name=pblock or "",
    )


class FpgaDevice:
    """
    A device on the SK-RAFT server.

    A reserved device is normally obtained from SkraftFpga.attach. The class
    can be used as a context manager, in which case the reservation is
    released automatically when the block ends.

    Attributes:
        serial_number (str): The serial number of the device.
        part_number (str): The part number of the device. Empty if it is
            not known.
        design (Design): The design that was last uploaded to the server.
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
        """
        Create a handle for a device on the server.

        Creating the handle does not reserve the device. Use
        SkraftFpga.attach to reserve a device.

        Parameters:
            stub (skraft_client_pb2_grpc.SKRaftFpgaStub): The gRPC stub of
                the server connection.
            serial_number (str): The serial number of the device.
            part_number (str): The part number of the device. Empty if it
                is not known.
        """
        self._stub = stub
        self.serial_number = serial_number
        self.part_number = part_number
        self._design = Design()

    def __enter__(self) -> "FpgaDevice":
        """
        Enter the context manager.

        Returns:
            FpgaDevice: This device.
        """
        return self

    def __exit__(self, *exc_info) -> None:
        """
        Leave the context manager and release the device.

        Parameters:
            *exc_info: Details of any exception raised inside the block.
                They are not used.

        Raises:
            ConnectionFailedError: If the server could not release the
                device.
        """
        self.release()

    def release(self) -> None:
        """
        Release the device and the resources reserved for it on the server.

        Uses the FpgaClose RPC.

        Raises:
            ConnectionFailedError: If the server could not release the
                device.
        """
        try:
            self._stub.FpgaClose(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to release device: {_rpc_detail(e)}"
            ) from e

    def uploadDesignToServer(self, design: Design) -> None:
        """
        Upload the files of a design to the server.

        Each file is sent in its own stream through the FpgaUploadDesignFile
        RPC. The server keeps the files and uses them in later operations.
        Once every file has been sent, the design is also kept on the client
        so that later calls can check which files are available.

        Parameters:
            design (Design): The design whose files should be uploaded.
                Files that are not set are skipped.

        Raises:
            DesignFileError: If a design file cannot be read or its upload
                fails.
        """
        for field_name, file_type in self._FILE_TYPES.items():
            path = getattr(design, field_name)
            if path is not None:
                self._upload_file(path, file_type)
        self._design = design

    def _upload_file(self, path: str, file_type: int) -> None:
        """
        Upload a single design file to the server.

        Parameters:
            path (str): The local path of the file.
            file_type (int): The wire value that identifies the kind of
                file.

        Raises:
            DesignFileError: If the file cannot be read or the upload fails.
        """
        requests = self._file_requests(path, file_type)
        try:
            self._stub.FpgaUploadDesignFile(requests)
        except grpc.RpcError as e:
            raise DesignFileError(
                f"failed to upload design file {path}: {_rpc_detail(e)}"
            ) from e

    @staticmethod
    def _file_requests(path: str, file_type: int):
        """
        Prepare the messages that stream a design file to the server.

        A checksum of the file is calculated first and sent with the file,
        so that the server can confirm the file arrived intact. The file
        content is then streamed in fixed-size chunks.

        Parameters:
            path (str): The local path of the file.
            file_type (int): The wire value that identifies the kind of
                file.

        Returns:
            Iterator[skraft_client_pb2.UploadDesignFileRequest]: The
                messages of the stream.

        Raises:
            DesignFileError: If the file cannot be read.
        """
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
            """
            Produce the messages for the upload stream.

            The first message describes the file. The messages that follow
            carry the file content in chunks.

            Yields:
                skraft_client_pb2.UploadDesignFileRequest: The next message
                    in the stream.
            """
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

        return requests()

    @property
    def design(self) -> Design:
        """
        The design that was last uploaded to the server.

        Returns:
            Design: The last uploaded design, or an empty design if nothing
                has been uploaded yet.
        """
        return self._design

    def programFPGA(self) -> None:
        """
        Program the device with the uploaded bitstream.

        The bitstream must be uploaded first. Uses the FpgaProgram RPC.

        Raises:
            DesignFileError: If the bitstream has not been uploaded.
            ConnectionFailedError: If the server could not program the
                device.
        """
        self._design.require("bit")
        try:
            self._stub.FpgaProgram(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to program the target FPGA device: {_rpc_detail(e)}"
            ) from e

    def readback_range(self, start_far: int,
                       end_far: int) -> list[FpgaFrame]:
        """
        Read back a range of configuration frames from the device.

        Uses the FpgaReadBackRange RPC.

        Parameters:
            start_far (int): The frame address where the range starts.
            end_far (int): The frame address where the range ends. This
                frame is included in the result.

        Returns:
            list[FpgaFrame]: The frames that were read back.

        Raises:
            FrameAddressError: If the start address comes after the end
                address, or if the server could not read the frames.
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
        """
        Shut down the device.

        Uses the FpgaShutdown RPC.

        Raises:
            ConnectionFailedError: If the server could not shut down the
                device.
        """
        try:
            self._stub.FpgaShutdown(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to shutdown the device: {_rpc_detail(e)}"
            ) from e

    def startup_sequence(self):
        """
        Run the startup sequence on the device.

        Uses the FpgaStartupSequence RPC.

        Raises:
            ConnectionFailedError: If the startup sequence fails.
        """
        try:
            self._stub.FpgaStartupSequence(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"Startup sequence failed: {_rpc_detail(e)}"
            ) from e

    def restore_application_layer(self):
        """
        Restore the application layer of the device.

        Uses the FpgaRestoreApplication RPC.

        Raises:
            ConnectionFailedError: If the application layer could not be
                restored.
        """
        try:
            self._stub.FpgaRestoreApplication(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"Failed to restore application layer: {_rpc_detail(e)}"
            ) from e

    def readback(self, option: ReadbackOption) -> list[FpgaFrame]:
        """
        Read back every configuration frame of the device.

        Uses the FpgaReadBack RPC.

        Parameters:
            option (ReadbackOption): How the readback is done. The capture
                option asks the server to capture the current state of all
                changeable elements of the device before reading it back.

        Returns:
            list[FpgaFrame]: All frames that were read back.

        Raises:
            ConnectionFailedError: If the server could not read back the
                device.
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
        """
        Convert the frames in a server reply into FpgaFrame objects.

        Parameters:
            reply: A server reply that holds a list of frames.

        Returns:
            list[FpgaFrame]: The converted frames.
        """
        # FpgaFrame.words is a flat repeated uint32. The wire format does
        # not have the FpgaWord wrapper message any more.
        frames: list[FpgaFrame] = []
        for frame in reply.frames:
            words = [FpgaWord(value) for value in frame.words]
            frames.append(FpgaFrame(frame.frame_address, words))
        return frames

    @property
    def cram_bits(self) -> int:
        """
        The total number of configuration memory (CRAM) bits in the device.

        Returns:
            int: The number of CRAM bits.

        Raises:
            ConnectionFailedError: If the server could not count the bits.
        """
        return self.bit_count(TargetMemory.CRAM)

    @property
    def essential_cram_bits(self) -> int:
        """
        The number of essential CRAM bits in the loaded design.

        Requires the essential bits (EBD) file.

        Returns:
            int: The number of essential CRAM bits.

        Raises:
            DesignFileError: If the essential bits (EBD) file has not
                been uploaded.
            ConnectionFailedError: If the server could not count the bits.
        """
        return self.bit_count(TargetMemory.ESSENTIAL_CRAM)

    @property
    def ff_bits(self) -> int:
        """
        The number of flip-flop bits used by the loaded design.

        Requires the logic location (LL) file.

        Returns:
            int: The number of flip-flop bits.

        Raises:
            DesignFileError: If the logic location (LL) file has not
                been uploaded.
            ConnectionFailedError: If the server could not count the bits.
        """
        return self.bit_count(TargetMemory.FF)

    @property
    def bram_bits(self) -> int:
        """
        The number of block RAM (BRAM) bits used by the loaded design.

        Requires the logic location (LL) file.

        Returns:
            int: The number of BRAM bits.

        Raises:
            DesignFileError: If the logic location (LL) file has not
                been uploaded.
            ConnectionFailedError: If the server could not count the bits.
        """
        return self.bit_count(TargetMemory.BRAM)

    @property
    def lutram_bits(self) -> int:
        """
        The number of LUTRAM bits used by the loaded design.

        Requires the logic location (LL) file.

        Returns:
            int: The number of LUTRAM bits.

        Raises:
            DesignFileError: If the logic location (LL) file has not
                been uploaded.
            ConnectionFailedError: If the server could not count the bits.
        """
        return self.bit_count(TargetMemory.LUTRAM)

    def all_bit_counts(self, pblock: Optional[str] = None) -> dict[str, int]:
        """
        Get every bit count for the loaded design in one call.

        Without a pblock, the counts cover the whole device and come from
        the FpgaGetAllBitCounts RPC. With a pblock, each count only includes
        the bits that fall inside that pblock, and each memory type is
        requested separately. A memory type whose design file has not been
        uploaded gives a count of 0.

        Parameters:
            pblock (Optional[str]): The name of a pblock from the
                constraints (XDC) file. If omitted, the whole device is
                counted. Using a pblock requires the constraints file.

        Returns:
            dict[str, int]: The bit counts, under the keys cram_bits,
                essential_cram_bits, bram_bits, flip_flop_bits,
                lutram_bits, pblock_bits and pblock_essential_bits.

        Raises:
            DesignFileError: If a pblock is given and the constraints
                (XDC) file has not been uploaded.
            ConnectionFailedError: If the server could not provide the
                counts.
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
        """
        Count the bits of one memory type in the loaded design.

        CRAM counts every configuration bit. ESSENTIAL_CRAM counts the
        essential bits and needs the essential bits (EBD) file. FF, LUTRAM
        and BRAM count storage element bits and need the logic location (LL)
        file. Uses the FpgaGetBitCount RPC.

        Parameters:
            target (TargetMemory): The memory type to count. Only one memory
                type can be given.
            pblock (Optional[str]): The name of a pblock from the
                constraints (XDC) file. If given, only the bits inside that
                pblock are counted.

        Returns:
            int: The number of bits.

        Raises:
            DesignFileError: If a design file needed for the target or
                the pblock has not been uploaded.
            ValueError: If the target is not a single memory type.
            ConnectionFailedError: If the server could not count the bits.
        """
        if target not in self._BIT_CATEGORIES:
            raise ValueError(
                f"bit_count takes a single TargetMemory, got {target!r}"
            )
        self._design.require(*target.required_design_files,
                             *(("xdc",) if pblock else ()))
        return self._count(target, pblock)

    def _count(self, target: TargetMemory, pblock: Optional[str]) -> int:
        """
        Ask the server for the bit count of one memory type.

        Parameters:
            target (TargetMemory): The memory type to count.
            pblock (Optional[str]): The pblock to limit the count to, or
                None for the whole device.

        Returns:
            int: The number of bits.

        Raises:
            ConnectionFailedError: If the server could not count the bits.
        """
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

    def inject_random(
        self, target: TargetMemory, pblock: Optional[str] = None
    ) -> FpgaRandomInjectionReport:
        """
        Inject a single upset at a random location.

        Uses the FpgaRandomBitFlip RPC.

        Parameters:
            target (TargetMemory): The memories where the upset may be
                injected. Several memories can be combined.
            pblock (Optional[str]): The name of a pblock from the
                constraints (XDC) file. If given, the upset is injected
                inside that pblock.

        Returns:
            FpgaRandomInjectionReport: The location of the injected upset
                and, when known, the name of the affected net.

        Raises:
            DesignFileError: If a design file needed for the target or
                the pblock has not been uploaded.
            ConnectionFailedError: If the server could not inject the upset.
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
        """
        Inject an upset into every bit of the selected memories.

        Uses the FpgaExhaustiveBitFlip RPC.

        Parameters:
            target (TargetMemory): The memories to inject into. Several
                memories can be combined.
            pblock (Optional[str]): The name of a pblock from the
                constraints (XDC) file. If given, only the bits inside that
                pblock are injected.

        Returns:
            tuple[list[FpgaInjectionReport], int]: A report for each
                injected location, and the number of injected bits as
                reported by the server.

        Raises:
            DesignFileError: If a design file needed for the target or
                the pblock has not been uploaded.
            ConnectionFailedError: If the server could not run the
                injection.
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
        """
        Inject an upset at one specific location.

        Uses the FpgaBitFlip RPC.

        Parameters:
            far (int): The frame address.
            word_index (int): The index of the word inside the frame.
            bit_index (int): The index of the bit inside the word.
            target (TargetMemory): The memory at that location. At most one
                storage element type can be given. If none is given, the
                location is treated as CRAM.

        Returns:
            FpgaInjectionReport: The requested location. The server returns
                no details, so this simply repeats the input.

        Raises:
            DesignFileError: If a design file needed for the target has
                not been uploaded.
            ValueError: If more than one storage element type is given.
            ConnectionFailedError: If the server could not inject the upset.
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
        return FpgaInjectionReport(far, word_index, bit_index, target)

    def scrub(self, option: ScrubbingType, scrub_cycle: int,
              duration_ms: int, session_id: str = "") -> FpgaScrubReport:
        """
        Run a scrubbing session on the device.

        Uses the FpgaScrubbing RPC.

        Parameters:
            option (ScrubbingType): The kind of scrubbing to run. Essential
                scrubbing needs the essential bits (EBD) file, which the
                server uses to tell essential upsets from non-essential
                ones.
            scrub_cycle (int): The scrub cycle setting for the session.
            duration_ms (int): How long the session runs, in milliseconds.
            session_id (str): An optional identifier for the session.

        Returns:
            FpgaScrubReport: A summary of each scrub cycle, including its
                timings and the words that differed from the golden data.

        Raises:
            DesignFileError: If essential scrubbing is requested and
                the essential bits (EBD) file has not been uploaded.
            ConnectionFailedError: If the server could not run the session.
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
        """
        Run a fault injection campaign defined by the user.

        If the campaign targets essential bits, the essential bits (EBD)
        file is needed. Uses the FpgaFaultInjection RPC.

        Parameters:
            session (FpgaFiSession): The settings of the campaign.

        Returns:
            FpgaFiSummary: The campaign settings, the number of injected and
                corrected faults, and the details of each affected word. The
                counts are worked out on the client from the returned words.

        Raises:
            DesignFileError: If the campaign targets essential bits and
                the essential bits (EBD) file has not been uploaded.
            ConnectionFailedError: If the server could not run the campaign.
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
        """
        Get the essential bit masks from the essential bits (EBD) file.

        Each returned frame is a mask, not configuration data. A set bit
        marks an essential bit at that position. Requires the EBD file.
        Uses the FpgaEssentialFrames RPC.

        Returns:
            list[FpgaFrame]: The mask frames.

        Raises:
            DesignFileError: If the essential bits (EBD) file has not
                been uploaded.
            ConnectionFailedError: If the server could not provide the
                frames.
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
        """
        Get the readback masks from the mask (MSD) file.

        A set bit marks a position to ignore when a readback is compared
        with the golden data. Requires the MSD file. Uses the
        FpgaMaskFrames RPC.

        Returns:
            list[FpgaFrame]: The mask frames.

        Raises:
            DesignFileError: If the readback mask (MSD) file has not
                been uploaded.
            ConnectionFailedError: If the server could not provide the
                frames.
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
        """
        Get every frame address of the device.

        Uses the FpgaFarList RPC.

        Returns:
            list[int]: All frame addresses of the device.

        Raises:
            FrameAddressError: If the server could not provide the list.
        """
        try:
            reply = self._stub.FpgaFarList(empty_pb2.Empty())
            return list(reply.fars)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to get the FAR list: {_rpc_detail(e)}"
            ) from e

    def extract_fars_from_bitstream(self, bitstream: str) -> list[int]:
        """
        Extract every frame address from a bitstream.

        The bitstream is sent to the server only for this operation, so the
        bitstream uploaded with uploadDesignToServer is not changed. It must
        be generated with per-frame CRC. Uses the
        FpgaExtractFarsFromBitstream RPC.

        Parameters:
            bitstream (str): The local path of the bitstream file.

        Returns:
            list[int]: The frame addresses found in the bitstream.

        Raises:
            DesignFileError: If the bitstream cannot be read.
            FrameAddressError: If the frame addresses could not be
                extracted.
        """
        requests = self._file_requests(
            bitstream, skraft_client_pb2.FPGA_FILE_TYPE_BIT,
        )
        try:
            reply = self._stub.FpgaExtractFarsFromBitstream(requests)
            return list(reply.fars)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to extract FARs from {bitstream}: "
                f"{_rpc_detail(e)}"
            ) from e

    def exclude_frames(self, fars: list[int]) -> None:
        """
        Exclude frame addresses from feature operations.

        Excluded frames are skipped by feature operations. Injection at a
        single location with inject_at is not affected. Uses the
        FpgaExcludeFars RPC.

        Parameters:
            fars (list[int]): The frame addresses to exclude.

        Raises:
            FrameAddressError: If the server could not exclude the frames.
        """
        try:
            request = skraft_client_pb2.FpgaFarListExcludeRequest(fars=fars)
            self._stub.FpgaExcludeFars(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to exclude the provided FARs: {_rpc_detail(e)}"
            ) from e

    def pblocks(self) -> list[FpgaPblock]:
        """
        List every pblock declared in the constraints.

        Requires the constraints (XDC) file. Uses the FpgaGetPblocks RPC.

        Returns:
            list[FpgaPblock]: Each pblock with its name and its range
                clauses. A clause can be passed to pblock_by_clause to find
                the frames it covers.

        Raises:
            DesignFileError: If the constraints (XDC) file has not
                been uploaded.
            FrameAddressError: If the server could not provide the pblocks.
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
        """
        Find the frames covered by a pblock range clause.

        The result can be used with inject_at to limit injection to one
        region of the device. Requires the constraints (XDC) file. Uses the
        FpgaGetPblockFarsByClause RPC.

        Parameters:
            clause (str): A pblock range clause, written as it appears in
                the constraints file.

        Returns:
            list[FpgaPblockFar]: Each frame address covered by the clause,
                together with the word and bit ranges it covers inside that
                frame.

        Raises:
            DesignFileError: If the constraints (XDC) file has not
                been uploaded.
            FrameAddressError: If the server could not resolve the clause.
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
        """
        Convert a range message from the server into an FpgaPblockRange.

        Parameters:
            message: A server message that holds the start and end of a
                range.

        Returns:
            FpgaPblockRange: The converted range.
        """
        # "from" is a reserved word in Python, so it is read with getattr.
        return FpgaPblockRange(getattr(message, "from"), message.to)

    def write_bscan(self, bscan: BscanPrimitive, value: int) -> bytes:
        """
        Write a value into a USER register through a BSCAN primitive.

        The value is sent most significant byte first and padded to a whole
        number of bytes. Uses the FpgaWriteBscan RPC.

        Parameters:
            bscan (BscanPrimitive): The BSCAN primitive that gives access to
                the register.
            value (int): The value to write. It must not be negative and
                must fit in the register.

        Returns:
            bytes: The data returned by the register during the write.

        Raises:
            OverflowError: If the value is negative or too large for the
                register.
            BscanError: If the register could not be written.
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
        """
        Read the current value of a USER register through a BSCAN primitive.

        Uses the FpgaReadBscan RPC.

        Parameters:
            bscan (BscanPrimitive): The BSCAN primitive that gives access to
                the register.

        Returns:
            bytes: The current value of the register.

        Raises:
            BscanError: If the register could not be read.
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
        """
        Read a register of the device.

        Uses the FpgaReadRegister RPC.

        Parameters:
            reg_addr (int): The address of the register, for example
                RegisterAddress.STATUS.

        Returns:
            int: The value of the register.

        Raises:
            FrameAddressError: If the register could not be read.
        """
        try:
            request = skraft_client_pb2.FpgaReadRegisterRequest(
                addr=int(reg_addr),
            )
            reply = self._stub.FpgaReadRegister(request)

            return reply.value
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to read register: {_rpc_detail(e)}"
            ) from e

    def write_register(self, reg_addr: int, value: int):
        """
        Write a value into a register of the device.

        Uses the FpgaWriteRegister RPC.

        Parameters:
            reg_addr (int): The address of the register, for example
                RegisterAddress.CTRL0.
            value (int): The value to write.

        Raises:
            FrameAddressError: If the register could not be written.
        """
        try:
            request = skraft_client_pb2.FpgaWriteRegisterRequest(
                addr=int(reg_addr), value=value,
            )
            self._stub.FpgaWriteRegister(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to write register: {_rpc_detail(e)}"
            ) from e

    def decode_far(self, far: int) -> FpgaFar7series | FpgaFarUltraScale:
        """
        Split a frame address into its individual fields.

        The server decides which device family layout applies. Uses the
        FpgaDecodeFrameAddress RPC.

        Parameters:
            far (int): The frame address to decode.

        Returns:
            FpgaFar7series | FpgaFarUltraScale: The decoded fields, in the
                layout of the device family.

        Raises:
            FrameAddressError: If the server could not decode the address.
        """
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

    @overload
    def xadc(
        self, adc_sensor_selector: XadcSensorSelector, /
    ) -> XadcSensor: ...

    @overload
    def xadc(self, drp_address: int, /) -> XadcSensor: ...

    def xadc(self, sensor: XadcSensorSelector | int, /) -> XadcSensor:
        """
        Read an XADC sensor of the device.

        The sensor is given either by a selector of the library, for example
        VCCINT or TEMPERATURE, or by the DRP address of its status register.
        The value is in units of the International System of Units (SI):
        volts (V) for voltages and degrees Celsius (degC) for temperatures.

        Only the on-chip sensors, and their recorded maximum and minimum
        values, can be read. Uses the FpgaXadcSensor RPC.

        Parameters:
            sensor (XadcSensorSelector | int): The selector of the sensor,
                or the DRP address of its status register.

        Returns:
            XadcSensor: The value of the sensor, in V or degC.

        Raises:
            TypeError: If the sensor is neither a selector nor a DRP
                address.
            XadcError: If the server could not read the sensor, for example
                because the DRP address is not a sensor, or the device does
                not have the sensor.

        Examples:
            >>> dev.xadc(VCCINT).value       # V
            >>> dev.xadc(TEMPERATURE).value  # degC
            >>> dev.xadc(0x01).value         # V, VCCINT by DRP address
        """
        if isinstance(sensor, XadcSensorSelector):
            addr = sensor.addr
        elif isinstance(sensor, int) and not isinstance(sensor, bool):
            addr = sensor
        else:
            raise TypeError(
                "expected an XadcSensorSelector or a DRP address, got "
                f"{type(sensor).__name__}"
            )

        try:
            request = skraft_client_pb2.FpgaXadcSensorRequest(addr=addr)
            reply = self._stub.FpgaXadcSensor(request)

            return XadcSensor(addr, reply.value)
        except grpc.RpcError as e:
            raise XadcError(
                f"failed to read XADC sensor at DRP address {addr:#04x}: "
                f"{_rpc_detail(e)}"
            ) from e

class SkraftFpga:
    """
    A client for a single connection to an SK-RAFT server.

    Use connect to create a client and open the connection. The class can
    be used as a context manager, in which case the connection is closed
    automatically when the block ends.

    Attributes:
        ip (str): The address of the server.
        port (int): The port of the server.
    """

    def __init__(self, ip: str, port: int):
        """
        Create a client without opening a connection.

        Use connect instead to get a client that is ready to use.

        Parameters:
            ip (str): The address of the server.
            port (int): The port of the server.
        """
        self.ip = ip
        self.port = port
        self._channel = None
        self._stub = None

    # -- connection lifecycle --------------------------------------------- #
    @classmethod
    def connect(cls, ip: str, port: int,
                tls_server_cert: Optional[str] = None,
                tls_cert: Optional[str] = None,
                tls_key: Optional[str] = None) -> "SkraftFpga":
        """
        Create a client and open a connection to the server.

        After connecting, the server version is checked and a warning is
        printed if it does not match the version this client expects.

        The connection uses TLS when any of the TLS files is given. This is
        needed when the server is started with -tls-cert and -tls-key.

        Parameters:
            ip (str): The address of the server.
            port (int): The port of the server.
            tls_server_cert (Optional[str]): The path of the PEM certificate
                of the server (the -tls-cert of the server), used to verify
                the server. Its names must include the ip given here. If it
                is not given, the server is verified against the trusted
                certificates of the system.
            tls_cert (Optional[str]): The path of the PEM certificate of
                this client. It is needed when the server is started with
                -tls-public-key, and must hold that public key. Give it
                together with tls_key.
            tls_key (Optional[str]): The path of the PEM private key of this
                client, the private key of tls_cert.

        Returns:
            SkraftFpga: The connected client.

        Raises:
            ValueError: If only one of tls_cert and tls_key is given.
            OSError: If a TLS file cannot be read.
            ConnectionFailedError: If the server cannot be reached.
        """
        if (tls_cert is None) != (tls_key is None):
            raise ValueError("TLS needs both tls_cert and tls_key")

        client = cls(ip, port)
        # A full readback of a large device is larger than the default
        # limit of 4 MB.
        options = [("grpc.max_receive_message_length", -1),
                   ("grpc.max_send_message_length", -1)]
        try:
            if tls_server_cert is None and tls_cert is None:
                client._channel = grpc.insecure_channel(
                    f"{ip}:{port}", options=options,
                )
            else:
                credentials = grpc.ssl_channel_credentials(
                    root_certificates=_read_pem(tls_server_cert),
                    private_key=_read_pem(tls_key),
                    certificate_chain=_read_pem(tls_cert),
                )
                client._channel = grpc.secure_channel(
                    f"{ip}:{port}", credentials, options=options,
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
        """
        Get the version of the server.

        Uses the Version RPC.

        Returns:
            str: The version reported by the server.

        Raises:
            ConnectionFailedError: If the server could not be reached.
        """
        try:
            reply = self._stub.Version(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the server version from "
                f"{self.ip}:{self.port}: {_rpc_detail(e)}"
            ) from e
        return reply.version

    def __enter__(self) -> "SkraftFpga":
        """
        Enter the context manager.

        Returns:
            SkraftFpga: This client.
        """
        return self

    def __exit__(self, *exc_info) -> None:
        """
        Leave the context manager and close the connection.

        Parameters:
            *exc_info: Details of any exception raised inside the block.
                They are not used.
        """
        self.disconnect()

    def disconnect(self) -> None:
        """
        Close the connection to the server.

        Calling it again after the connection is closed has no effect.
        """
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None

    def get_devices(self) -> list[FpgaDevice]:
        """
        List the devices connected to the server.

        Listing the devices does not reserve them. Use attach to reserve a
        device. Uses the FpgaGetDevices RPC.

        Returns:
            list[FpgaDevice]: One entry for each connected device, with its
                serial number and part number.

        Raises:
            DeviceReservationError: If the server could not list the
                devices.
        """
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
        """
        Reserve a device by its serial number.

        The serial number is the one Vivado shows for the device. If the
        reservation fails, any programmers opened during the attempt are
        closed again. Uses the FpgaConnect and FpgaSelectDevice RPCs.

        Parameters:
            serial_number (str): The serial number of the device to reserve.

        Returns:
            FpgaDevice: The reserved device. It can be used as a context
                manager so that the reservation is released automatically.

        Raises:
            DeviceReservationError: If the device could not be reserved.
                When no device matches, the error message lists the serial
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
        """
        Close any programmers that were opened during a failed attempt.

        Errors from the server are ignored, since this is only a clean-up
        step.
        """
        try:
            self._stub.FpgaClose(empty_pb2.Empty())
        except grpc.RpcError:
            pass
