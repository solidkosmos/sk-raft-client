from PIL.Image import frombytes

from . import skraft_client_pb2

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

class BscanPrimitive:
    def __init__(self, user_register_id: int, size_in_bits: int):
        if user_register_id < 0 or user_register_id > 4:
            raise RuntimeError(f"User_register_id must be between 0 and 4")

        self.__user_register_id = user_register_id
        self.__size_in_bits = size_in_bits

    @property
    def user_register_id(self) -> int:
        return self.__user_register_id

    @property
    def size_in_bits(self) -> int:
        return self.__size_in_bits

    def shift_in(self, grpc_client, value: bytes) -> bytes:
        request = skraft_client_pb2.FpgaBscanTarget(
            userRegisterId=self.__user_register_id,
            value=value,
            usefulBits=self.__size_in_bits
        )

        reply = grpc_client.fpgaWriteBscan(request)
        return bytes(reply.value)

