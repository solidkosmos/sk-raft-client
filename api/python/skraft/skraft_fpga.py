# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024-2026 SOLIDKOSMOS S.A.

"""
Client for the SK-RAFT server.

Connects to an SK-RAFT server over gRPC, reserves FPGA devices and runs
operations on them, such as programming, readback, fault injection and
scrubbing.
"""

from __future__ import annotations

import hashlib
import os
from typing import Iterable, Optional, overload

import grpc
from google.protobuf import empty_pb2

from . import skraft_client_pb2
from . import skraft_client_pb2_grpc
from .datatypes import (
    BscanPrimitive,
    Design,
    FpgaComponent,
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
    JtagFrequency,
    TargetMemory,
    ScrubbingType,
    ReadbackOption,
    XadcAlarm,
    XadcAlarmSelector,
    XadcFlags,
    XadcRegister,
    XadcSensor,
    XadcSensorSelector,
)
from .exceptions import (
    BscanError,
    ConnectionFailedError,
    DesignFileError,
    DeviceReservationError,
    FrameAddressError,
    JtagError,
    XadcError,
)


SK_RAFT_VERSION = "1.0.0"

# The size of each chunk that the client streams during a design file upload.
_UPLOAD_CHUNK_SIZE = 1 << 20

# The number of hexadecimal digits of the checksum in the name of the folder
# of a design on the server.
_DESIGN_CHECKSUM_DIGITS = 8

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
    target: TargetMemory, pblock: Optional[str],
    component: Optional[str] = None,
) -> skraft_client_pb2.FpgaInjectionOptions:
    """
    Build the injection options to send to the server.

    Parameters:
        target (TargetMemory): The memories that the injection may target.
            Several memories can be combined.
        pblock (Optional[str]): The name of a pblock from the constraints
            (XDC) file. If given, the injection is limited to that pblock.
        component (Optional[str]): A component of the design hierarchy,
            for example "top/sub". If given, the injection is limited to
            the flip-flops of that component.

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
        components=[component] if component else [],
    )


def _pblock_names(pblocks: Optional[Iterable[str]]) -> list[str]:
    """
    Check a collection of pblock names and put the names in a list.

    Parameters:
        pblocks (Optional[Iterable[str]]): The names of pblocks from the
            constraints (XDC) file, for example a set. None and an empty
            collection give an empty list.

    Returns:
        list[str]: The names in alphabetical order, each name one time.

    Raises:
        TypeError: If pblocks is one string, or if it holds a name that is
            not a string.
    """
    if pblocks is None:
        return []
    # A string is also iterable, but each character would become a name.
    if isinstance(pblocks, str):
        raise TypeError(
            "expected a collection of pblock names, for example "
            f"{{{pblocks!r}}}, got a str"
        )

    names: set[str] = set()
    for name in pblocks:
        if not isinstance(name, str):
            raise TypeError(
                f"expected a pblock name as str, got {type(name).__name__}"
            )
        names.add(name)

    return sorted(names)


def _xadc_register_address(register: XadcRegister | int) -> int:
    """
    Check an XADC control register and get its DRP address.

    Parameters:
        register (XadcRegister | int): The register, or its DRP address.

    Returns:
        int: The DRP address of the register.

    Raises:
        TypeError: If the register is not an XadcRegister or an int.
    """
    # A bool is also an int, but True and False are not addresses.
    if not isinstance(register, int) or isinstance(register, bool):
        raise TypeError(
            "expected an XadcRegister or a DRP address, got "
            f"{type(register).__name__}"
        )
    return int(register)


def _xadc_alarm_address(alarm: XadcAlarmSelector | int) -> int:
    """
    Check an XADC alarm threshold and get the DRP address of its register.

    Parameters:
        alarm (XadcAlarmSelector | int): The selector of the threshold, or
            the DRP address of its alarm register.

    Returns:
        int: The DRP address of the alarm register.

    Raises:
        TypeError: If the alarm is neither a selector nor a DRP address.
    """
    if isinstance(alarm, XadcAlarmSelector):
        return alarm.addr
    # A bool is also an int, but True and False are not addresses.
    if not isinstance(alarm, int) or isinstance(alarm, bool):
        raise TypeError(
            "expected an XadcAlarmSelector or a DRP address, got "
            f"{type(alarm).__name__}"
        )
    return alarm


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
        design (Design): The design that was last uploaded to the server,
            or programmed.
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

    def upload_design_to_server(self, design: Design) -> None:
        """
        Upload the files of a design to the server.

        Each file is sent in its own stream through the FpgaUploadDesignFile
        RPC. The server keeps the files of each design in a folder of its
        own. Thus, you can upload several designs, and then program one of
        them with programFPGA. Once every file has been sent, the design is
        also kept on the client so that later calls can check which files
        are available.

        Parameters:
            design (Design): The design whose files should be uploaded.
                Files that are not set are skipped.

        Raises:
            DesignFileError: If a design file cannot be read or its upload
                fails.
        """
        for path, info in self._design_files(design):
            self._upload_file(path, info)
        self._design = design

    def _design_files(
        self, design: Design
    ) -> list[tuple[str, skraft_client_pb2.FpgaDesignFileInfo]]:
        """
        Describe the files of a design, as the server keeps them.

        The server keeps the files of each design in a folder of its own, so
        that two designs with the same file names do not overwrite each
        other. The name of the folder is the name of the bitstream and a
        short checksum of all the files of the design. Thus, the same files
        always go to the same folder.

        Parameters:
            design (Design): The design. Files that are not set are skipped.

        Returns:
            list[tuple[str, skraft_client_pb2.FpgaDesignFileInfo]]: The
                local path and the description of each file.

        Raises:
            DesignFileError: If a design file cannot be read.
        """
        files = []
        for field_name, file_type in self._FILE_TYPES.items():
            path = getattr(design, field_name)
            if path is not None:
                files.append((path, self._file_info(path, file_type)))

        checksum = hashlib.sha256()
        for _, info in files:
            checksum.update(f"{info.type}:{info.sha256}\n".encode())
        name = "design"
        if design.bit is not None:
            name = os.path.splitext(os.path.basename(design.bit))[0]
        folder = f"{name}_{checksum.hexdigest()[:_DESIGN_CHECKSUM_DIGITS]}"

        for _, info in files:
            info.relative_path = f"{folder}/{info.relative_path}"
        return files

    def _upload_file(
        self, path: str, info: skraft_client_pb2.FpgaDesignFileInfo
    ) -> None:
        """
        Upload a single design file to the server.

        Parameters:
            path (str): The local path of the file.
            info (skraft_client_pb2.FpgaDesignFileInfo): The description of
                the file, from _file_info.

        Raises:
            DesignFileError: If the file cannot be read or the upload fails.
        """
        requests = self._file_requests(path, info)
        try:
            self._stub.FpgaUploadDesignFile(requests)
        except grpc.RpcError as e:
            raise DesignFileError(
                f"failed to upload design file {path}: {_rpc_detail(e)}"
            ) from e

    @staticmethod
    def _file_info(
        path: str, file_type: int
    ) -> skraft_client_pb2.FpgaDesignFileInfo:
        """
        Describe a local design file for the server.

        A checksum of the file is calculated, so that the server can confirm
        that the file arrived intact, and that it did not change before the
        programming.

        Parameters:
            path (str): The local path of the file.
            file_type (int): The wire value that identifies the kind of
                file.

        Returns:
            skraft_client_pb2.FpgaDesignFileInfo: The type, the file name,
                the size and the checksum (sha256) of the file.

        Raises:
            DesignFileError: If the file cannot be read.
        """
        try:
            digest = hashlib.sha256()
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(_UPLOAD_CHUNK_SIZE), b""):
                    digest.update(chunk)
            size = os.path.getsize(path)
        except OSError as e:
            raise DesignFileError(
                f"failed to read design file {path}: {e}"
            ) from e

        return skraft_client_pb2.FpgaDesignFileInfo(
            type=file_type,
            relative_path=os.path.basename(path),
            size=size,
            sha256=digest.hexdigest(),
        )

    @staticmethod
    def _file_requests(
        path: str, info: skraft_client_pb2.FpgaDesignFileInfo
    ):
        """
        Prepare the messages that stream a design file to the server.

        The description of the file is sent first. The file content is then
        streamed in fixed-size chunks.

        Parameters:
            path (str): The local path of the file.
            info (skraft_client_pb2.FpgaDesignFileInfo): The description of
                the file, from _file_info.

        Returns:
            Iterator[skraft_client_pb2.UploadDesignFileRequest]: The
                messages of the stream.
        """
        def requests():
            """
            Produce the messages for the upload stream.

            The first message describes the file. The messages that follow
            carry the file content in chunks.

            Yields:
                skraft_client_pb2.UploadDesignFileRequest: The next message
                    in the stream.
            """
            yield skraft_client_pb2.UploadDesignFileRequest(info=info)
            with open(path, "rb") as file:
                for chunk in iter(lambda: file.read(_UPLOAD_CHUNK_SIZE), b""):
                    yield skraft_client_pb2.UploadDesignFileRequest(chunk=chunk)

        return requests()

    @property
    def design(self) -> Design:
        """
        The design that was last uploaded to the server, or programmed.

        Returns:
            Design: The last uploaded or programmed design, or an empty
                design if nothing has been uploaded yet.
        """
        return self._design

    def program_fpga(self, design: Optional[Design] = None) -> None:
        """
        Program the device with an uploaded design.

        Upload the design with uploadDesignToServer first. The server keeps
        each uploaded design. Thus, you can upload several designs, and then
        program the one to use. The client reads the local files of the
        design again, and the server checks that its copies are the same.
        After the programming, later calls check the files of this design.
        Uses the FpgaProgram RPC.

        Parameters:
            design (Optional[Design]): The design to program. If not given,
                the design that was last uploaded or programmed is used.

        Raises:
            TypeError: If the design is not a Design.
            DesignFileError: If the design has no bitstream, or if a design
                file cannot be read.
            ConnectionFailedError: If the server could not program the
                device, for example because the design was not uploaded.

        Examples:
            >>> dev.uploadDesignToServer(design_a)
            >>> dev.uploadDesignToServer(design_b)
            >>> dev.programFPGA(design_a)
            >>> dev.programFPGA(design_b)
        """
        if design is None:
            design = self._design
        if not isinstance(design, Design):
            raise TypeError(
                f"expected a Design, got {type(design).__name__}"
            )
        design.require("bit")

        files = [info for _, info in self._design_files(design)]
        try:
            self._stub.FpgaProgram(
                skraft_client_pb2.FpgaProgramRequest(files=files)
            )
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to program the target FPGA device with "
                f"{design.bit}: {_rpc_detail(e)}"
            ) from e
        self._design = design

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

    def write_frame(self, frame: FpgaFrame, restore: bool = False) -> None:
        """
        Write one configuration frame to the device.

        The server writes the words of the frame at the frame address of
        the frame. The frame must have all the words of a frame of the
        device, as a frame from readback has. Uses the FpgaWriteFrame RPC.

        Parameters:
            frame (FpgaFrame): The frame to write.
            restore (bool): If True, the server also restores the
                flip-flops and RAMs of the whole device after the write.
                Keep it False to change only the configuration data.

        Raises:
            TypeError: If the frame is not an FpgaFrame.
            ConnectionFailedError: If the server could not write the frame,
                for example because the frame address is not on the device
                or the number of words is not correct.

        Examples:
            >>> frames = dev.readback(ReadbackOption.READBACK)
            >>> dev.write_frame(frames[1])
        """
        if not isinstance(frame, FpgaFrame):
            raise TypeError(
                f"expected an FpgaFrame, got {type(frame).__name__}"
            )

        try:
            request = skraft_client_pb2.FpgaWriteFrameRequest(
                frame=skraft_client_pb2.FpgaFrame(
                    frame_address=frame.far,
                    words=[word.value for word in frame.words],
                ),
                restore=restore,
            )
            self._stub.FpgaWriteFrame(request)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to write frame {frame.far:#010x}: {_rpc_detail(e)}"
            ) from e

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

    def configure_seed(self, seed: int) -> None:
        """
        Set the seed of the random generator for random injections.

        With the same seed, the same design and the same targets,
        inject_random selects the same sequence of locations. Thus, you can
        repeat a random campaign. Each SkraftFpga.attach sets a new seed
        from the current time. Thus, set the seed after attach. Uses the
        FpgaConfigureSeed RPC.

        Parameters:
            seed (int): The seed, from 0 to 2**32 - 1.

        Raises:
            TypeError: If the seed is not an integer.
            ValueError: If the seed is out of range.
            ConnectionFailedError: If the server could not set the seed.

        Examples:
            >>> dev.configure_seed(42)
            >>> dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
        """
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError(
                f"expected an integer seed, got {type(seed).__name__}"
            )
        # The server keeps the seed in a 32-bit unsigned integer.
        if not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError(
                f"the seed must be from 0 to {0xFFFFFFFF}, got {seed}"
            )

        try:
            request = skraft_client_pb2.FpgaSeedOptions(seed=seed)
            self._stub.FpgaConfigureSeed(request)
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to configure the seed {seed}: {_rpc_detail(e)}"
            ) from e

    def configure_jtag_frequency(self, frequency: JtagFrequency) -> None:
        """
        Set the JTAG clock (TCK) frequency of the FTDI that accesses the
        device.

        The frequency is from 460 kHz to 15 MHz. The FTDI makes only the
        frequencies 30 MHz / n, for an integer n. Thus, use one of the
        JTAG_* constants, for example JTAG_10_MHZ, to get the frequency
        without change. See JtagFrequency. Uses the FpgaConfigureFrequency
        RPC.

        Parameters:
            frequency (JtagFrequency): The TCK frequency.

        Raises:
            TypeError: If the frequency is not a JtagFrequency.
            JtagError: If the server could not set the frequency.

        Examples:
            >>> dev.configure_jtag_frequency(JTAG_10_MHZ)
            >>> dev.configure_jtag_frequency(
            ...     JtagFrequency(750, FrequencyUnit.KHZ)
            ... )
        """
        if not isinstance(frequency, JtagFrequency):
            raise TypeError(
                f"expected a JtagFrequency, got {type(frequency).__name__}"
            )

        try:
            request = skraft_client_pb2.FpgaFrequencyOptions(
                frequency=frequency.value, unit=frequency.unit,
            )
            self._stub.FpgaConfigureFrequency(request)
        except grpc.RpcError as e:
            raise JtagError(
                f"failed to configure the TCK frequency {frequency}: "
                f"{_rpc_detail(e)}"
            ) from e

    def configure_latency(self, latency_ms: int) -> None:
        """
        Set the latency timer of the FTDI that accesses the device.

        The FTDI sends the data that it holds to the host when the latency
        timer expires, if its buffer is not full. Uses the
        FpgaConfigureLatency RPC.

        Parameters:
            latency_ms (int): The latency, in milliseconds (ms), from 0 to
                255. The FTDI driver can refuse low values.

        Raises:
            TypeError: If the latency is not an integer.
            ValueError: If the latency does not fit in 8 bits.
            JtagError: If the server could not set the latency.

        Examples:
            >>> dev.configure_latency(2)
        """
        if not isinstance(latency_ms, int) or isinstance(latency_ms, bool):
            raise TypeError(
                f"expected the latency as int, got "
                f"{type(latency_ms).__name__}"
            )
        # The FTDI keeps the latency in an 8-bit register.
        if not 0 <= latency_ms <= 0xFF:
            raise ValueError(
                f"the latency must be from 0 to {0xFF} ms, got {latency_ms}"
            )

        try:
            request = skraft_client_pb2.FpgaLatencyOptions(
                latency_ms=latency_ms,
            )
            self._stub.FpgaConfigureLatency(request)
        except grpc.RpcError as e:
            raise JtagError(
                f"failed to configure the latency {latency_ms} ms: "
                f"{_rpc_detail(e)}"
            ) from e

    def inject_random(
        self,
        target: TargetMemory,
        pblock: Optional[str] = None,
        exclude_pblock: Optional[Iterable[str]] = None,
        component: Optional[str] = None,
    ) -> FpgaRandomInjectionReport:
        """
        Inject a single upset at a random location.

        To repeat the same locations, set the seed with configure_seed.
        Uses the FpgaRandomBitFlip RPC. With exclude_pblock, it also uses
        the FpgaExcludePblocks and FpgaIncludePblocks RPCs.

        Parameters:
            target (TargetMemory): The memories where the upset may be
                injected. Several memories can be combined.
            pblock (Optional[str]): The name of a pblock from the
                constraints (XDC) file. If given, the upset is injected
                inside that pblock.
            exclude_pblock (Optional[Iterable[str]]): The names of pblocks
                from the constraints (XDC) file, for example a set. If
                given, the upset is not injected into the bits of these
                pblocks. The exclusion applies to this call only.
            component (Optional[str]): A component of the design hierarchy,
                as in the net paths of the logic location (LL) file, for
                example "top_component/sub_component". If given, the upset
                is injected into a flip-flop of that component. The
                component must be one or more whole levels of the path.
                Use it with TargetMemory.FF only.

        Returns:
            FpgaRandomInjectionReport: The location of the injected upset
                and, when known, the name of the affected net.

        Raises:
            TypeError: If exclude_pblock is one string, or if it holds a
                name that is not a string.
            ValueError: If exclude_pblock holds the pblock given in pblock.
            DesignFileError: If a design file needed for the target or
                the pblocks has not been uploaded.
            FrameAddressError: If the server could not exclude the pblocks,
                or could not include them again.
            ConnectionFailedError: If the server could not inject the upset,
                for example because component is given with a target other
                than TargetMemory.FF, or the component has no flip-flops.

        Examples:
            >>> dev.inject_random(TargetMemory.FF, exclude_pblock={"pb_sr"})
            >>> dev.inject_random(
            ...     TargetMemory.FF,
            ...     exclude_pblock={"pb_sr", "pb_sr2", "pb_sr3"},
            ... )
            >>> report = dev.inject_random(
            ...     TargetMemory.FF, component="top_component/sub_component",
            ... )
            >>> report.net_name
            'top_component/sub_component/count_reg[3]'
        """
        excluded = _pblock_names(exclude_pblock)
        if pblock is not None and pblock in excluded:
            raise ValueError(
                f"exclude_pblock holds the injected pblock {pblock!r}"
            )

        self._design.require(*target.required_design_files,
                             *(("xdc",) if pblock or excluded else ()))
        if excluded:
            self._exclude_pblocks(excluded)

        try:
            request = _injection_options(target, pblock, component)
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
        finally:
            # The server keeps an exclusion until the next programming. The
            # exclusion applies to this call only, thus include the pblocks
            # again, also if the injection failed.
            if excluded:
                self._include_pblocks(excluded)

    def _exclude_pblocks(self, names: list[str]) -> None:
        """
        Exclude pblocks from the injection on the server.

        The server keeps the exclusion until _include_pblocks or the next
        programming. Uses the FpgaExcludePblocks RPC.

        Parameters:
            names (list[str]): The names of the pblocks to exclude.

        Raises:
            FrameAddressError: If the server could not exclude the pblocks.
        """
        try:
            request = skraft_client_pb2.FpgaPblockListExcludeRequest(
                pblock_names=names,
            )
            self._stub.FpgaExcludePblocks(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to exclude the pblocks {names}: {_rpc_detail(e)}"
            ) from e

    def _include_pblocks(self, names: list[str]) -> None:
        """
        Include pblocks in the injection on the server again.

        Uses the FpgaIncludePblocks RPC.

        Parameters:
            names (list[str]): The names of the pblocks to include.

        Raises:
            FrameAddressError: If the server could not include the pblocks.
        """
        try:
            request = skraft_client_pb2.FpgaPblockListIncludeRequest(
                pblock_names=names,
            )
            self._stub.FpgaIncludePblocks(request)
        except grpc.RpcError as e:
            raise FrameAddressError(
                f"failed to include the pblocks {names}: {_rpc_detail(e)}"
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
            bitstream,
            self._file_info(bitstream, skraft_client_pb2.FPGA_FILE_TYPE_BIT),
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

    def components(self) -> list[FpgaComponent]:
        """
        List the components of the design hierarchy.

        The server finds the components in the nets of the flip-flops in
        the logic location (LL) file. Give the path of a component to
        inject_random, as component, to inject into its flip-flops.
        Requires the LL file. Uses the FpgaGetComponents RPC.

        Returns:
            list[FpgaComponent]: The top-level components, each with its
                sub components, in the order of their names. Empty if no
                flip-flop net is inside a component.

        Raises:
            DesignFileError: If the logic location (LL) file has not been
                uploaded.
            ConnectionFailedError: If the server could not provide the
                components.

        Examples:
            >>> for component in dev.components():
            ...     print(component)
            top_component (120 flip-flops)
            |-- other_component (40 flip-flops)
            `-- sub_component (80 flip-flops)
                `-- sub_sub_component (16 flip-flops)
            >>> dev.inject_random(
            ...     TargetMemory.FF, component="top_component/sub_component",
            ... )
        """
        self._design.require("ll")
        try:
            reply = self._stub.FpgaGetComponents(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise ConnectionFailedError(
                f"failed to get the components: {_rpc_detail(e)}"
            ) from e
        return [self._component(message) for message in reply.components]

    @staticmethod
    def _component(message) -> FpgaComponent:
        """
        Convert a component message of the server, with its sub components.

        Parameters:
            message (skraft_client_pb2.FpgaComponent): The component, as the
                server sends it.

        Returns:
            FpgaComponent: The component, with all its sub components.
        """
        return FpgaComponent(
            message.name, message.path, message.flip_flop_count,
            [FpgaDevice._component(child) for child in message.children],
        )

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

    @overload
    def xadc_alarm(
        self, adc_alarm_selector: XadcAlarmSelector, /
    ) -> XadcAlarm: ...

    @overload
    def xadc_alarm(self, drp_address: int, /) -> XadcAlarm: ...

    def xadc_alarm(self, alarm: XadcAlarmSelector | int, /) -> XadcAlarm:
        """
        Read an XADC alarm threshold of the device.

        The threshold is given either by a selector of the library, for
        example TEMPERATURE_UPPER or VCCINT_LOWER, or by the DRP address of
        its alarm register. The server converts the raw value of the
        register. The value is in units of the International System of
        Units (SI): volts (V) for voltages and degrees Celsius (degC) for
        temperatures. Uses the FpgaXadcAlarm RPC.

        Parameters:
            alarm (XadcAlarmSelector | int): The selector of the threshold,
                or the DRP address of its alarm register.

        Returns:
            XadcAlarm: The threshold, in V or degC.

        Raises:
            TypeError: If the alarm is neither a selector nor a DRP
                address.
            XadcError: If the server could not read the threshold, for
                example because the DRP address is not an alarm register,
                or the device does not have the alarm.

        Examples:
            >>> dev.xadc_alarm(TEMPERATURE_UPPER).value  # degC
            >>> dev.xadc_alarm(VCCINT_LOWER).value       # V
        """
        addr = _xadc_alarm_address(alarm)

        try:
            request = skraft_client_pb2.FpgaXadcAlarmRequest(addr=addr)
            reply = self._stub.FpgaXadcAlarm(request)

            return XadcAlarm(addr, reply.value)
        except grpc.RpcError as e:
            raise XadcError(
                f"failed to read XADC alarm at DRP address {addr:#04x}: "
                f"{_rpc_detail(e)}"
            ) from e

    def set_xadc_alarm(
        self, alarm: XadcAlarmSelector | int, value: float
    ) -> None:
        """
        Set an XADC alarm threshold of the device.

        The value is in units of the International System of Units (SI):
        volts (V) for voltages and degrees Celsius (degC) for temperatures.
        The server converts it into the raw value of the alarm register, and
        reads the register back to verify the write. The server keeps the
        bits of the register that are not part of the threshold, for example
        the automatic shutdown enable of OT_LIMIT, or the hysteresis or
        window mode of TEMPERATURE_LOWER in UltraScale+ devices. Uses the
        FpgaXadcSetAlarm RPC.

        Caution: if the automatic shutdown is enabled, the device shuts down
        when the temperature is above OT_LIMIT.

        Parameters:
            alarm (XadcAlarmSelector | int): The selector of the threshold,
                or the DRP address of its alarm register.
            value (float): The threshold, in V or degC.

        Raises:
            TypeError: If the alarm is neither a selector nor a DRP
                address, or if the value is not a number.
            XadcError: If the server could not set the threshold, for
                example because the value is outside the range of the ADC,
                or the design does not allow writes through JTAG.

        Examples:
            >>> dev.set_xadc_alarm(TEMPERATURE_UPPER, 85.0)  # degC
            >>> dev.set_xadc_alarm(VCCINT_LOWER, 0.97)       # V
        """
        addr = _xadc_alarm_address(alarm)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(
                f"expected the value as a number, got {type(value).__name__}"
            )

        try:
            request = skraft_client_pb2.FpgaXadcSetAlarmRequest(
                addr=addr, value=value,
            )
            self._stub.FpgaXadcSetAlarm(request)
        except grpc.RpcError as e:
            raise XadcError(
                f"failed to set XADC alarm at DRP address {addr:#04x}: "
                f"{_rpc_detail(e)}"
            ) from e

    def xadc_flags(self) -> XadcFlags:
        """
        Read the state of the XADC alarms of the device.

        The server reads the flag register and decodes it. Uses the
        FpgaXadcFlags RPC.

        Returns:
            XadcFlags: The state of each alarm and of the JTAG access.

        Raises:
            XadcError: If the server could not read the flag register.

        Examples:
            >>> dev.xadc_flags().temperature  # True while ALM0 is on
        """
        try:
            reply = self._stub.FpgaXadcFlags(empty_pb2.Empty())
        except grpc.RpcError as e:
            raise XadcError(
                f"failed to read the XADC flags: {_rpc_detail(e)}"
            ) from e

        return XadcFlags(
            temperature=reply.temperature,
            vccint=reply.vccint,
            vccaux=reply.vccaux,
            over_temperature=reply.over_temperature,
            vccbram=reply.vccbram,
            vccpint=reply.vccpint,
            vccpaux=reply.vccpaux,
            vcco_ddr=reply.vcco_ddr,
            internal_reference=reply.internal_reference,
            jtag_read_only=reply.jtag_read_only,
            jtag_disabled=reply.jtag_disabled,
        )

    def read_xadc_register(self, register: XadcRegister | int) -> int:
        """
        Read an XADC register of the device.

        Only the flag register, the configuration registers and the alarm
        registers can be read, see XadcRegister. Uses the
        FpgaXadcReadRegister RPC.

        Parameters:
            register (XadcRegister | int): The register, or its DRP
                address.

        Returns:
            int: The raw 16-bit value of the register.

        Raises:
            TypeError: If the register is not an XadcRegister or an int.
            XadcError: If the server could not read the register, for
                example because the DRP address is not the flag register, or
                a configuration or alarm register.

        Examples:
            >>> dev.read_xadc_register(XadcRegister.CONFIG1)
            >>> dev.read_xadc_register(XadcRegister.FLAG) & 0x0001  # ALM0
        """
        addr = _xadc_register_address(register)

        try:
            request = skraft_client_pb2.FpgaXadcReadRegisterRequest(
                addr=addr,
            )
            reply = self._stub.FpgaXadcReadRegister(request)

            return reply.value
        except grpc.RpcError as e:
            raise XadcError(
                f"failed to read XADC register {addr:#04x}: "
                f"{_rpc_detail(e)}"
            ) from e

    def write_xadc_register(
        self, register: XadcRegister | int, value: int
    ) -> None:
        """
        Write a raw value into an XADC control register of the device.

        Only the configuration registers and the alarm registers can be
        written, see XadcRegister. The flag register is read only. UG480
        gives the meaning of each bit. Uses the FpgaXadcWriteRegister RPC.

        Parameters:
            register (XadcRegister | int): The register, or its DRP
                address.
            value (int): The raw 16-bit value to write.

        Raises:
            TypeError: If the register is not an XadcRegister or an int, or
                if the value is not an int.
            ValueError: If the value does not fit in 16 bits.
            XadcError: If the server could not write the register, for
                example because the DRP address is not a configuration or
                alarm register.

        Examples:
            >>> dev.write_xadc_register(XadcRegister.ALARM8, 0x5800)
        """
        addr = _xadc_register_address(register)
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(
                f"expected the value as int, got {type(value).__name__}"
            )
        if not 0 <= value <= 0xFFFF:
            raise ValueError(
                f"an XADC register holds 16 bits, got {value:#x}"
            )

        try:
            request = skraft_client_pb2.FpgaXadcWriteRegisterRequest(
                addr=addr, value=value,
            )
            self._stub.FpgaXadcWriteRegister(request)
        except grpc.RpcError as e:
            raise XadcError(
                f"failed to write XADC register {addr:#04x}: "
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
            FpgaDevice: The reserved device, with its serial number and
                part number. It can be used as a context manager so that
                the reservation is released automatically.

        Raises:
            DeviceReservationError: If the device could not be reserved.
                When no device matches, the error message lists the serial
                numbers of the connected devices.
        """
        try:
            self._stub.FpgaConnect(empty_pb2.Empty())
            reply = self._stub.FpgaSelectDevice(
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
        return FpgaDevice(self._stub, serial_number, reply.part_number)

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
