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

import grpc
from . import datatypes
from google.protobuf import empty_pb2

from . import skraft_client_pb2
from . import skraft_client_pb2_grpc

class SkRaftFpga:
    """
        SkRaftFpga defines various routines leveraged for manipulating an FPGA
        device.
    """
    def __init__(self, ip: str, port: int):
        self.__conn = None
        self.__grpc_client = None

        self.__ip = ip
        self.__port = port

    def establish_connection(self):
        """
            establish_connection Initiates the communication, over the network,
            from the gRPC client to gRPC server.
        """
        try:
            self.__conn = grpc.insecure_channel('%s:%d' % (self.__ip,
                                                           self.__port))
            self.__grpc_client = skraft_client_pb2_grpc.SKRaftFpgaStub(
                                                            self.__conn)
        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to connect to gRPC server at "
                               f"{self.__ip}:{self.__port} {e}")

    def fpga_connect(self, device_part_number: str, programmer_part_number: str):
        """
            fpga_connect Initiates the communication with the target FPGA device
            specified by the @device_part_number. It communicates with the
            device using the programmer specific by @programmer_part_number.

            @param device_part_number: str The device part number.
            @param programmer_part_number: str The programmer part number.
        """
        try:
            request = skraft_client_pb2.FpgaDeviceDetails(
                devicePartNumber=device_part_number,
                programmerPartNumber=programmer_part_number
            )

            self.__grpc_client.fpgaConnect(request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to connect to the target FPGA device.")

    def fpga_close(self):
        """
            fpga_close terminates the communication with the target FPGA device
            used during the execution of the client.
        """
        try:
            empty_request = empty_pb2.Empty()
            self.__grpc_client.fpgaClose(empty_request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to close FPGA connection.")

    def fpga_set_rbd_file_path(self, rbd_path: str):
        """
            fpga_set_rbd_file_path configures the path of the RBD file.

            @param rbd_path: str The path to the RBD file, relative to
            the filesystem of the machine where the gRPC server (SK-RAFT)
            is running.
        """
        try:
            request = skraft_client_pb2.FilePath(path=rbd_path)

            self.__grpc_client.fpgaSetRbdFilePath(request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed configure RBD file path.")

    def fpga_set_msd_file_path(self, msd_path: str):
        """
            fpga_set_ebd_file_path configures the path of the MSD file.

            @param msd_path: str The path to the MSD file, relative to
            the filesystem of the machine where the gRPC server (SK-RAFT)
            is running.
        """
        try:
            request = skraft_client_pb2.FilePath(path=msd_path)

            self.__grpc_client.fpgaSetMsdFilePath(request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to configure MSD file path.")

    def fpga_set_ebd_file_path(self, ebd_path: str):
        """
            fpga_set_ebd_file_path configures the path of the EBD
            file.

            @param ebd_path: str The path to the EBD file, relative to
            the filesystem of the machine where the gRPC server (SK-RAFT)
            is running.
        """
        try:
            request = skraft_client_pb2.FilePath(path=ebd_path)

            self.__grpc_client.fpgaSetEbdFilePath(request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to configure EBD file path.")

    def fpga_set_bit_file_path(self, bit_path: str):
        """
            fpga_set_bit_file_path configures the path of the bitstream
            file.

            @param bit_path: str The path to the bitstream file, relative to
            the filesystem of the machine where the gRPC server (SK-RAFT)
            is running.
        """
        try:
            request = skraft_client_pb2.FilePath(path=bit_path)

            self.__grpc_client.fpgaSetBitFilePath(request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to configure bit file path.")

    def fpga_write_bscan(self, bscan: datatypes.BscanPrimitive, value: bytes, userful_bits) -> bytes:
        """
            fpga_write_bscan perform a write operation on user register
            @user_register_id. The @user_register_id take as value an integer
            in that belong in the [0,4] interval.

            @param user_register_id: int The user register to write. Allowed values
            are integers in the interval [0,4].
            @param value: The value to write on the selected register.
            @returns The contents previously present in the selected user
            register.
        """
        try:
            return bscan.shift_in(self.__grpc_client, value, userful_bits)
        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to write bscan register "
                               f"{bscan.user_register_id}.")

    def fpga_bit_flip(self, far: int, word_index: int, bit_index: int,
                      is_flip_flop: bool, is_lut_ram: bool, is_bram: bool):
        """
            fpga_bit_flip inserts a single bit upset in the FPGA by inverting
            the value of a user-defined bit position in the Configuration
            Memory (CRAM).

            @param far: int The frame address (FAR) in which the fault should
            be injected.
            @param word_index: int The word index in which the fault should
            be injected.
            @param bit_index: int The bit index in which the fault should be
            injected.
            @return None
        """
        try:
            request = skraft_client_pb2.FpgaInjectionTarget(
                frameAddress=far,
                wordIndex=word_index,
                bitIndex=bit_index,
                isFlipFlop=is_flip_flop,
                isLutRam=is_lut_ram,
                isBram=is_bram
            )
            self.__grpc_client.fpgaBitFlip(request)
        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to perform bit flip operation.")

    def fpga_random_bit_flip(self, include_essential: bool,
                             include_flip_flops: bool, include_lut_rams: bool,
                             include_brams: bool) -> datatypes.FpgaRandomInjectionReport:
        """
            fpga_random_bit_flip inserts a single random bit into the FPGA
            memory. Provided with the necessary flags this function can
            inject faults in both the Configuration Layer (CRAM) or in
            Application layer. In Configuration layer, provided with the
            respective flag, it can inject faults only on essential bits.
            In Application layer, provided with the respective flags, it
            can perform the injection on Flip Flops, Lut Rams and Brams.

            @param include_essential: bool The flag indicating whether to
            include ONLY essential bits in the random injection.
            @param include_flip_flops: bool The flag indicating whether to
            include Flip Flops in the random injection.
            @param include_lut_rams: bool The flag indicating whether to
            include LUT RAMs in the random injection.
            @param include_brams: bool The flag indicating whether to
            include Brams in the random injection.
        """
        try:
            request = skraft_client_pb2.FpgaRandomInjectionOptions(
                includeEssential=include_essential,
                includeFlipFlops=include_flip_flops,
                includeLutRams=include_lut_rams,
                includeBrams=include_brams
            )
            reply = self.__grpc_client.fpgaRandomInjectionOptions(request)

            return datatypes.FpgaRandomInjectionReport(
                reply.target.frameAdress,
                reply.target.wordIndex,
                reply.target.bitIndex,
                reply.target.isFlipFlop,
                reply.target.isLutRam,
                reply.target.isBram
            )

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to perform random bit flip operation.")

    def fpga_fault_injection(self, fi_session: datatypes.FpgaFiSession) -> datatypes.FpgaFiSummary:
        """
            fpa_fault_injection initiates a fault injection session, using
            the user-defined options specified in FpgaFiSession.

            @param fi_session: FpgaFiSession It contains the user-defined
            options for the fault injection session.
            @return FpgaFiSummary A summary that contains the various faults
            and other useful information about the completed fault injection
            session.
        """
        try:
            request = skraft_client_pb2.FpgaFiSession(
                type=fi_session.type,
                duration=fi_session.duration,
                correctionTime=fi_session.correction_time,
                timeBetweenFaults=fi_session.time_between_faults,
                sbuPercent=fi_session.sbu_percent,
                mbuPercent=fi_session.mbu_percent,
                mcuPercent=fi_session.mcu_percent,
                essential=fi_session.essential,
                correct=fi_session.correct
            )
            reply = self.__grpc_client.fpgaFaultInjection(request)

            words_summary: list = []

            for word_summary in reply.wordSummary:
                words_summary.append(
                    datatypes.FpgaWordSummary(
                        word_summary.far,
                        word_summary.wordIndex,
                        word_summary.bitIndex,
                        word_summary.goldenWordValue,
                        word_summary.injectedWordValue,
                        word_summary.isEssential
                    )
                )

            return datatypes.FpgaFiSummary(
                reply.type,
                reply.duration,
                reply.correctionTime,
                reply.timeBetweenFaults,
                fi_session.sbu_percent,
                fi_session.mbu_percent,
                fi_session.mcu_percent,
                fi_session.essential,
                fi_session.correct,
                words_summary
            )

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to perform fault injections.")

    def fpga_program(self):
        """
            fpga_program program the target FPGA device using the bitstream
            file provided via the fpga_set_bit_file_path().
        """
        try:
            empty_request = empty_pb2.Empty()
            self.__grpc_client.fpgaProgram(empty_request)

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to program the target fpga device.")

    def fpga_readback(self, start_far: int, end_far: int) -> list[datatypes.FpgaFrame]:
        """
            fpga_readback reads a range of frames starting from start_far and
            ending at end_far.

            @param start_far: The Frame Address (FAR) from which the read should
            start.
            @param end_far: The Frame Address (FAR) from which the read should
            stop.
            @return A list of frames objects.
        """
        if start_far > end_far:
            raise RuntimeError(
                f"start_far must be smaller than end_far but {start_far}.")

        try:
            frames: list[datatypes.FpgaFrame] = []

            request = skraft_client_pb2.FpgaReadbackTarget(
                startFrameAddress=start_far,
                endFrameAddress=end_far,
            )
            reply = (
                self.__grpc_client.fpgaReadback(request))

            for frame in reply.frames:
                curr_words: list[datatypes.FpgaWord] = []
                for value in frame.words.values:
                    curr_words.append(datatypes.FpgaWord(value))

                frames.append(datatypes.FpgaFrame(
                    frame.frameAddress,
                    curr_words,
                ))

            return frames

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to read frames from FPGA device. "
                               f"Start FAR: {start_far}, End FAR: {end_far}.")
