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
from google.protobuf import empty_pb2

import skraft_client_pb2
import skraft_client_pb2_grpc

class FpgaWordSummary:
    """
        FpgaWordSummary Defines the details for an infected word, after the
        completion of a fault injection session.
    """
    def __init__(self,
                 far: int,
                 word_index: int,
                 bit_index: int,
                 golden_word_value: int,
                 injected_word_value: int,
                 is_essential: bool):

        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__golden_word_value = golden_word_value
        self.__injected_word_value = injected_word_value
        self.__is_essential = is_essential

    @property
    def far(self) -> int:
        """
            @returns The Frame Address (FAR) of the infected word.
        """
        return self.__far

    @property
    def word_index(self) -> int:
        """
            @returns The Word Index of the infected word.
        """
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """
            @returns The Bit Index of the infected bit.
        """
        return self.__bit_index

    @property
    def golden_word_value(self) -> int:
        """
            @returns The word value before the injection.
        """
        return self.__golden_word_value

    @property
    def injected_word_value(self) -> int:
        """
            @returns The word value after the injection.
        """
        return self.__injected_word_value

    @property
    def is_essential(self) -> bool:
        """
            @returns Whether the infected word is essential.
        """
        return self.__is_essential

class FpgaFiCommon:
    """
        FpgaFiCommon Defines common routines that are used on both the
        FpgaFiSummary & FpgaFiSession classes.
    """
    def __init__(self,
                 fi_type: int,
                 duration: int,
                 correction_time: int,
                 time_between_faults: int,
                 sbu_percent: float,
                 mbu_percent: float,
                 mcu_percent: float,
                 essential: bool,
                 correct: bool):

        self.__type                = fi_type
        self.__duration            = duration
        self.__correction_time     = correction_time
        self.__time_between_faults = time_between_faults
        self.__sbu_percent         = sbu_percent
        self.__mbu_percent         = mbu_percent
        self.__mcu_percent         = mcu_percent
        self.__essential           = essential
        self.__correct             = correct

    @property
    def type(self) -> int:
        """
            @returns The fault injection type, .e.g. Random or Exhaustive.
        """
        return self.__type

    @property
    def duration(self) -> int:
        """
            @returns The duration of the fault injection session in (ms).
        """
        return self.__duration

    @property
    def correction_time(self) -> int:
        """
            @returns The time to wait before correcting a fault in (ms).
        """
        return self.__correction_time

    @property
    def time_between_faults(self) -> int:
        """
            @returns The time to wait between faults in (ms).
        """
        return self.__time_between_faults

    @property
    def sbu_percent(self) -> float:
        """
            @returns The Single Bit Upset percentage of the fault injection
            session.
        """
        return self.__sbu_percent

    @property
    def mbu_percent(self) -> float:
        """
            @returns The Multi Bit Upset percentage of the fault injection
            session.
        """
        return self.__mbu_percent

    @property
    def mcu_percent(self) -> float:
        """
            @returns The Multi Cell Upset percentage of the fault injection
            session.
        """
        return self.__mcu_percent

    @property
    def essential(self) -> bool:
        """
            @returns Whether the fault injection session if performed on
            essential bits.
        """
        return self.__essential

    @property
    def correct(self) -> bool:
        """
            @returns Whether the fault injection session should correct
            the injected bits.
        """
        return self.__correct

class FpgaFiSummary(FpgaFiCommon):
    """
        FpgaFiSummary defines the results returned from the SK-RAFT after the
        completion of a fault injection session.
    """
    def __init__(self,
                 fi_type: int,
                 duration: int,
                 correction_time: int,
                 time_between_faults: int,
                 sbu_percent: float,
                 mbu_percent: float,
                 mcu_percent: float,
                 essential: bool,
                 correct: bool,
                 word_summary: list[int]):

        super().__init__(fi_type,
                         duration,
                         correction_time,
                         time_between_faults ,
                         sbu_percent,
                         mbu_percent,
                         mcu_percent,
                         essential,
                         correct)
        self.__word_summary = word_summary

    @property
    def word_summary(self) -> list[int]:
        return self.__word_summary


class FpgaFiSession(FpgaFiCommon):
    """
        FpgaFiSession defines the user-defined options that can be used
        during a fault injection session.
    """
    def __init__(self,
                 fi_type: int,
                 duration: int,
                 correction_time: int,
                 time_between_faults: int,
                 sbu_percent: float,
                 mbu_percent: float,
                 mcu_percent: float,
                 essential: bool,
                 correct: bool):

        super().__init__(fi_type,
                         duration,
                         correction_time,
                         time_between_faults,
                         sbu_percent,
                         mbu_percent,
                         mcu_percent,
                         essential,
                         correct)

    @FpgaFiCommon.type.setter
    def type(self, fi_type: int):
        """
            Configures the type of the session, .e.g. Exhaustive, Random.

            @param fi_type: int The type of the session
        """
        self.__type = fi_type

    @FpgaFiCommon.duration.setter
    def duration(self, duration: int):
        """
            Configures the duration of the session in ms.

            @param duration(ms): int The duration of the session in (ms).
        """
        self.__duration = duration

    @FpgaFiCommon.correct.setter
    def correction_time(self, correction_time: int):
        """
           Configures the correction time for each fault.

           @param correction_time(ms): int The correction time for each injected
           fault in (ms).
        """
        self.__correction_time = correction_time

    @FpgaFiCommon.time_between_faults.setter
    def time_between_faults(self, time_between_faults: int):
        """
            Configures the time between each fault in (ms).

            @param time_between_faults(ms): int The idle time between each fault.
            in (ms).
        """
        self.__time_between_faults = time_between_faults

    @FpgaFiCommon.sbu_percent.setter
    def sbu_percent(self, sbu_percent: float):
        """
            Configures the number of Single Bit Upsets that should be injected
            while in the fault injection session.

            @param sbu_percent: float The percentage of Single Bit Upsets.
        """
        self.__sbu_percent = sbu_percent

    @FpgaFiCommon.mbu_percent.setter
    def mbu_percent(self, mbu_percent: float):
        """
            Configures the number of Multi Bit Upsets that should be injected
            while in the fault injection session.

            @param mbu_percent: float The percentage of Multi Bit Upsets.
        """
        self.__mbu_percent = mbu_percent

    @FpgaFiCommon.mcu_percent.setter
    def mcu_percent(self, mcu_percent: float):
        """
            Configures the number of Multi Cell Upsets that should be injected
            while in the fault injection session.

            @param mcu_percent: float The percentage of Multi Cell Upsets.
        """
        self.__mcu_percent = mcu_percent

    @FpgaFiCommon.essential.setter
    def essential(self, essential: bool):
        """
            Configures whether the fault injection session should be performed
            on essential bits.

            @param essential: bool True if the fault injection session should
            be performed on essential bits.
        """
        self.__essential = essential

    @FpgaFiCommon.correct.setter
    def correct(self, correct: bool):
        """
            Configures whether the faults must be corrected.

            @param correct: bool True if each injected fault should be corrected.
        """
        self.__correct = correct

class FpgaRandomInjectionReport:
    """
        FpgaRandomInjectionReport defines the results from the SK-RAFT after the
        completion of a single random fault injection..
    """
    def __init__(self, far: int, word_index, bit_index: bool, is_flip_flop: bool,
                 is_lut_ram: bool, is_bram: bool):
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__is_flip_flop = is_flip_flop
        self.__is_lut_ram = is_lut_ram
        self.__is_bram = is_bram

    @property
    def far(self):
        """
            @returns the Frame Address (FAR) where the fault injection takes
            place.
        """
        return self.__far

    @property
    def word_index(self):
        """
            @returns the Word Index where the fault injection takes place.
        """
        return self.__word_index

    @property
    def is_flip_flop(self):
        """
            @returns Whether the fault injection was injected in a Flip Flop
            element.
        """
        return self.__is_flip_flop

    @property
    def is_lut_ram(self):
        """
            @returns Whether the fault injection was injected in a Lut ram
            element.
        """
        return self.__is_lut_ram

    @property
    def is_bram(self):
        """
            @returns Whether the fault injection was injected in a Bram element.
        """
        return self.__is_bram

class FpgaWord:
    """
        FpgaWord represents an FPGA word. It consists of a 32bit value.
    """
    def __init__(self, value: int):
        self.__value = value

    @property
    def value(self) -> int:
        """
            @returns the value of the word.
        """
        return self.__value

class FpgaFrame:
    """
        FpgaFrame represents an FPGA frame. It consists of a list of words
        and a Frame Address (FAR).
    """
    def __init__(self, far: int, words: list[FpgaWord]):
        self.__far = far
        self.__words = words

    @property
    def far(self) -> int:
        """
            @returns The Frame Address (FAR) of the frame.
        """
        return self.__far

    @property
    def word_value(self) -> list[FpgaWord]:
        """
            @returns The Word Values of the frame.
        """
        return self.__words


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

    def fpga_write_bscan(self, user_register_id: int, value: bytes,
                         useful_bits: int) -> bytes:
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
            if user_register_id < 0 or user_register_id > 4:
                raise RuntimeError(f"User_register_id must be between 0 and 4")

            request = skraft_client_pb2.FpgaBscanTarget(
                userRegisterId=user_register_id,
                value=value,
                usefulBits=useful_bits
            )

            reply = self.__grpc_client.fpgaWriteBscan(request)
            return bytes(reply.value)
        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to write bscan register "
                               f"{user_register_id}.")

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
                             include_brams: bool) -> FpgaRandomInjectionReport:
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

            return FpgaRandomInjectionReport(
                reply.target.frameAdress,
                reply.target.wordIndex,
                reply.target.bitIndex,
                reply.target.isFlipFlop,
                reply.target.isLutRam,
                reply.target.isBram
            )

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to perform random bit flip operation.")

    def fpga_fault_injection(self, fi_session: FpgaFiSession) -> FpgaFiSummary:
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
                    FpgaWordSummary(
                        word_summary.far,
                        word_summary.wordIndex,
                        word_summary.bitIndex,
                        word_summary.goldenWordValue,
                        word_summary.injectedWordValue,
                        word_summary.isEssential
                    )
                )

            return FpgaFiSummary(
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

    def fpga_readback(self, start_far: int, end_far: int) -> list[FpgaFrame]:
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
            frames: list[FpgaFrame] = []

            request = skraft_client_pb2.FpgaReadbackTarget(
                startFrameAddress=start_far,
                endFrameAddress=end_far,
            )
            reply = (
                self.__grpc_client.fpgaReadback(request))

            for frame in reply.frames:
                curr_words: list[FpgaWord] = []
                for value in frame.words.values:
                    curr_words.append(FpgaWord(value))

                frames.append(FpgaFrame(
                    frame.frameAddress,
                    curr_words,
                ))

            return frames

        except grpc.RpcError as e:
            raise RuntimeError(f"Failed to read frames from FPGA device. "
                               f"Start FAR: {start_far}, End FAR: {end_far}.")