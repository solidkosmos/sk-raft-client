"""
Data types used by the SK-RAFT client.

Holds the options, design file settings and result types that the client
sends to and receives from the SK-RAFT server.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from typing import Optional

from . import skraft_client_pb2
from .exceptions import DesignFileError


# --------------------------------------------------------------------------- #
# Injection selection
# --------------------------------------------------------------------------- #
class TargetMemory(IntFlag):
    """
    The memories that can be selected for fault injection.

    The members are flags and can be combined. Random and exhaustive
    injection accept combined memories. An injection at one specific
    location accepts at most one storage element type (FF, LUTRAM or BRAM).

    Attributes:
        CRAM (TargetMemory): The whole configuration memory, with no
            further limit.
        ESSENTIAL_CRAM (TargetMemory): Only the essential configuration
            bits. Needs the essential bits (EBD) file.
        FF (TargetMemory): Flip-flop bits. Needs the logic location (LL)
            file.
        LUTRAM (TargetMemory): LUTRAM bits. Needs the logic location (LL)
            file.
        BRAM (TargetMemory): Block RAM bits. Needs the logic location (LL)
            file.
    """

    CRAM = 1 << 0
    ESSENTIAL_CRAM = 1 << 1
    FF = 1 << 2
    LUTRAM = 1 << 3
    BRAM = 1 << 4

    @property
    def required_design_files(self) -> tuple[str, ...]:
        """
        The design files that this selection depends on.

        Returns:
            tuple[str, ...]: The names of the Design fields that must be
                set. Empty if no design file is needed.
        """
        files: list[str] = []
        if self & TargetMemory.ESSENTIAL_CRAM:
            files.append("ebd")
        if self & (TargetMemory.FF | TargetMemory.LUTRAM | TargetMemory.BRAM):
            files.append("ll")
        return tuple(files)

class ReadbackOption(int, Enum):
    """
    The ways a full readback can be done.

    Attributes:
        READBACK (ReadbackOption): A plain readback of the configuration
            memory.
        READBACK_CAPTURE (ReadbackOption): A readback that first captures
            the current state of all changeable elements of the device.
    """
    READBACK = 0
    READBACK_CAPTURE = 1

class ScrubbingType(int, Enum):
    """
    The scrubbing mode.

    Attributes:
        READBACK (ScrubbingType): Standard scrubbing, without the essential
            bits information.
        ESSENTIAL (ScrubbingType): Scrubbing that also uses the essential
            bits (EBD) file to tell essential upsets from non-essential
            ones.
    """

    READBACK = 0
    ESSENTIAL = 1


class FaultType(int, Enum):
    """
    The fault model of a fault injection campaign.

    The values match the fault types that the server understands.

    Attributes:
        RANDOM (FaultType): Faults are injected at random locations.
        EXHAUSTIVE (FaultType): Faults are injected at every location in
            turn.
    """
    RANDOM = skraft_client_pb2.FPGA_FAULT_TYPE_RANDOM
    EXHAUSTIVE = skraft_client_pb2.FPGA_FAULT_TYPE_EXHAUSTIVE

class RegisterAddress(int, Enum):
    """
    The addresses of the configuration registers of the device, for
    FpgaDevice.read_register and FpgaDevice.write_register.

    They are copies of the register addresses of the SK-RAFT server: the
    ID of each register, shifted into the register address field (bit 13)
    of a type 1 packet header.

    Attributes:
        FAR (RegisterAddress): The frame address register.
        CRC (RegisterAddress): The cyclic redundancy check register.
        STATUS (RegisterAddress): The status register.
        CTRL0 (RegisterAddress): The control register 0.
        MASK (RegisterAddress): The masking register for CTRL0 and CTRL1.
        CMD (RegisterAddress): The command register.
        IDCODE (RegisterAddress): The device ID register.
        FDRI (RegisterAddress): The frame data register input, which
            takes the configuration data.
        FDRO (RegisterAddress): The frame data register output, which
            gives the readback data.
        CTRL1 (RegisterAddress): The control register 1.
        COR0 (RegisterAddress): The configuration option register 0.
        COR1 (RegisterAddress): The configuration option register 1.
    """

    FAR = 0x01 << 13
    CRC = 0x00 << 13
    STATUS = 0x07 << 13
    CTRL0 = 0x05 << 13
    MASK = 0x06 << 13
    CMD = 0x04 << 13
    IDCODE = 0x0C << 13
    FDRI = 0x02 << 13
    FDRO = 0x03 << 13
    CTRL1 = 0x18 << 13
    COR0 = 0x09 << 13
    COR1 = 0x0E << 13


@dataclass(frozen=True)
class Design:
    """
    The files of a design, as paths on the client computer.

    FpgaDevice.uploadDesignToServer uploads every file that is set. All
    files are optional. An operation that needs a file that is not set
    raises an error that names the missing file.

    Attributes:
        bit (Optional[str]): The bitstream, used to program the device.
        ebd (Optional[str]): The essential bits file.
        ll (Optional[str]): The logic location file, which locates the
            flip-flop, LUTRAM and BRAM bits.
        xdc (Optional[str]): The constraints file, which declares the
            pblocks.
        rbd (Optional[str]): The readback data file, used for self-test.
        msd (Optional[str]): The readback mask file, used for self-test.
    """

    bit: Optional[str] = None
    ebd: Optional[str] = None
    ll: Optional[str] = None
    xdc: Optional[str] = None
    rbd: Optional[str] = None
    msd: Optional[str] = None

    def require(self, *fields: str) -> None:
        """
        Check that the named design files are set.

        Parameters:
            *fields (str): The names of the design files to check.

        Raises:
            DesignFileError: If one or more of the named files are not set.
                The error message names the missing files.
        """
        missing = [f for f in fields if getattr(self, f) is None]
        if missing:
            raise DesignFileError(
                f"operation requires design file(s): {', '.join(missing)}"
            )



class FpgaFar:
    """
    A frame address split into its individual fields.

    This is the common base for the layouts of each device family.

    Attributes:
        raw (int): The original frame address.
        blocktype (int): The block type field.
        row_address (int): The row address field.
        column_address (int): The column address field.
        minor_address (int): The minor address field.
    """

    def __init__(self, raw: int, blocktype: int,
                 row_address: int, column_address: int, 
                 minor_address: int) -> None:
        """
        Create a decoded frame address.

        Parameters:
            raw (int): The original frame address.
            blocktype (int): The block type field.
            row_address (int): The row address field.
            column_address (int): The column address field.
            minor_address (int): The minor address field.
        """
        self.__raw = raw
        self.__blocktype      = blocktype
        self.__row_address    = row_address
        self.__column_address = column_address
        self.__minor_address  = minor_address

    @property
    def raw(self) -> int:
        """The original frame address."""
        return self.__raw

    @property
    def blocktype(self) -> int:
        """The block type field."""
        return self.__blocktype

    @property
    def row_address(self) -> int:
        """The row address field."""
        return self.__row_address

    @property
    def column_address(self) -> int:
        """The column address field."""
        return self.__column_address

    @property
    def minor_address(self) -> int:
        """The minor address field."""
        return self.__minor_address

class FpgaFar7series(FpgaFar):
    """
    A frame address in the 7 series layout.

    Has all the fields of FpgaFar, plus the top or bottom half field.

    Attributes:
        topbottom (int): Whether the frame is in the top or the bottom half
            of the device.
    """

    def __init__(self, raw: int, blocktype: int, topbottom: int, row_address: int, column_address: int, minor_address: int) -> None:
        """
        Create a decoded 7 series frame address.

        Parameters:
            raw (int): The original frame address.
            blocktype (int): The block type field.
            topbottom (int): The top or bottom half field.
            row_address (int): The row address field.
            column_address (int): The column address field.
            minor_address (int): The minor address field.
        """
        self.__topbottom = topbottom

        super().__init__(raw, blocktype, row_address, column_address, minor_address)

    @property
    def topbottom(self) -> int:
        """Whether the frame is in the top or the bottom half of the device."""
        return self.__topbottom

class FpgaFarUltraScale(FpgaFar):
    """
    A frame address in the UltraScale layout.

    Has the same fields as FpgaFar.
    """

    def __init__(self, raw: int, blocktype: int, row_address: int, column_address: int, minor_address: int) -> None:
        """
        Create a decoded UltraScale frame address.

        Parameters:
            raw (int): The original frame address.
            blocktype (int): The block type field.
            row_address (int): The row address field.
            column_address (int): The column address field.
            minor_address (int): The minor address field.
        """
        super().__init__(raw, blocktype, row_address, column_address, minor_address)

class FpgaPblockRange:
    """
    An inclusive range of indexes.

    Attributes:
        start (int): The first index of the range.
        end (int): The last index of the range. This index is included.
    """

    def __init__(self, start: int, end: int) -> None:
        """
        Create a range.

        Parameters:
            start (int): The first index of the range.
            end (int): The last index of the range.
        """
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
    """
    An area of a frame that a pblock occupies.

    Attributes:
        bit_range (FpgaPblockRange): The bit indexes that the area occupies
            in each of its words.
        word_range (FpgaPblockRange): The word indexes that the area
            occupies in the frame.
    """

    def __init__(self, bit_range: FpgaPblockRange,
                 word_range: FpgaPblockRange) -> None:
        """
        Create an area.

        Parameters:
            bit_range (FpgaPblockRange): The bit indexes inside each word.
            word_range (FpgaPblockRange): The word indexes inside the frame.
        """
        self.__bit_range = bit_range
        self.__word_range = word_range

    @property
    def bit_range(self) -> FpgaPblockRange:
        """The bit indexes that the area occupies in each of its words."""
        return self.__bit_range

    @property
    def word_range(self) -> FpgaPblockRange:
        """The word indexes that the area occupies in the frame."""
        return self.__word_range

class FpgaPblockFar:
    """
    One frame address that a pblock covers.

    Attributes:
        far (int): The frame address.
        occupied_area (list[FpgaPblockAreaRange]): The areas of this frame
            that the pblock occupies.
    """

    def __init__(self, far: int,
                 occupied_area: list[FpgaPblockAreaRange]) -> None:
        """
        Create a covered frame entry.

        Parameters:
            far (int): The frame address.
            occupied_area (list[FpgaPblockAreaRange]): The areas of the
                frame that the pblock occupies.
        """
        self.__far = far
        self.__occupied_area = occupied_area

    @property
    def far(self) -> int:
        """The frame address."""
        return self.__far

    @property
    def occupied_area(self) -> list[FpgaPblockAreaRange]:
        """The areas of this frame that the pblock occupies."""
        return self.__occupied_area

class FpgaPblock:
    """
    A pblock declared in the constraints (XDC) file.

    Each clause is kept as a plain string, so it can be passed directly to
    FpgaDevice.pblock_by_clause.

    Attributes:
        name (str): The name of the pblock, as written in the constraints.
        clauses (list[str]): The range clauses of the pblock.
    """

    def __init__(self, name: str, clauses: list[str]) -> None:
        """
        Create a pblock.

        Parameters:
            name (str): The name of the pblock.
            clauses (list[str]): The range clauses of the pblock.
        """
        self.__name = name
        self.__clauses = clauses

    @property
    def name(self) -> str:
        """The name of the pblock, as written in the constraints."""
        return self.__name

    @property
    def clauses(self) -> list[str]:
        """The range clauses of the pblock."""
        return self.__clauses

class FpgaWord:
    """
    A single 32-bit word of configuration data.

    The server sends words as plain numbers. This class wraps them for
    convenience.

    Attributes:
        value (int): The value of the word.
    """

    def __init__(self, value: int):
        """
        Create a word.

        Parameters:
            value (int): The 32-bit value of the word.
        """
        self.__value = value

    @property
    def value(self) -> int:
        """The value of the word."""
        return self.__value

class FpgaFrame:
    """
    A configuration frame.

    Attributes:
        far (int): The frame address of the frame.
        words (list[FpgaWord]): The words of the frame. The number of words
            depends on the device family.
    """

    def __init__(self, far: int, words: list[FpgaWord]):
        """
        Create a frame.

        Parameters:
            far (int): The frame address of the frame.
            words (list[FpgaWord]): The words of the frame.
        """
        self.__far = far
        self.__words = words

    @property
    def far(self) -> int:
        """The frame address of the frame."""
        return self.__far

    @property
    def words(self) -> list[FpgaWord]:
        """The words of the frame."""
        return self.__words

class BscanPrimitive:
    """
    A BSCAN USER register.

    The register number is checked when the object is created, so an
    invalid number is reported straight away rather than during a later
    read or write.

    Attributes:
        MIN_REGISTER (int): The lowest valid USER register number.
        MAX_REGISTER (int): The highest valid USER register number.
        user_register_id (int): The USER register number.
        size_in_bits (int): The width of the register, in bits.
    """

    MIN_REGISTER = 1
    MAX_REGISTER = 4

    def __init__(self, user_register_id: int, size_in_bits: int):
        """
        Create a USER register.

        Parameters:
            user_register_id (int): The USER register number. It must be
                between MIN_REGISTER and MAX_REGISTER.
            size_in_bits (int): The width of the register, in bits.

        Raises:
            ValueError: If the register number is outside the valid range.
        """
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
        """The USER register number."""
        return self.__user_register_id

    @property
    def size_in_bits(self) -> int:
        """The width of the register, in bits."""
        return self.__size_in_bits

    def shift_in(self, grpc_client, value: bytes,
                 readonly: bool = False) -> bytes:
        """
        Shift a value through the register and return what comes out.

        In read-only mode the register contents stay unchanged and the
        FpgaReadBscan RPC is used. Otherwise the value is written into the
        register through the FpgaWriteBscan RPC.

        Parameters:
            grpc_client (skraft_client_pb2_grpc.SKRaftFpgaStub): The gRPC
                stub of the server connection.
            value (bytes): The data to shift into the register.
            readonly (bool): If True, read the register without changing
                it.

        Returns:
            bytes: The data shifted out of the register.

        Raises:
            grpc.RpcError: If the server call fails.
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
    """
    A BSCAN USER register that is read and written as an integer.

    Attributes:
        primitive (BscanPrimitive): The USER register that this object uses.
    """

    def __init__(self, dev, user_register_id: int, size_in_bits: int):
        """
        Create a register handle for an attached device.

        Parameters:
            dev (FpgaDevice): The attached device that holds the register.
            user_register_id (int): The USER register number.
            size_in_bits (int): The width of the register, in bits.

        Raises:
            ValueError: If the register number is outside the valid range.
        """
        self.__dev = dev
        self.__primitive = BscanPrimitive(user_register_id, size_in_bits)

    @property
    def primitive(self) -> BscanPrimitive:
        """The USER register that this object uses."""
        return self.__primitive

    def write(self, value: int) -> None:
        """
        Write a value into the register.

        Parameters:
            value (int): The value to write. It must not be negative and
                must fit in the register.

        Raises:
            OverflowError: If the value is negative or too large for the
                register.
            BscanError: If the register could not be written.
        """
        self.__dev.write_bscan(self.__primitive, value)

    def read(self) -> int:
        """
        Read the current value of the register.

        Any bits above the width of the register are cleared.

        Returns:
            int: The value of the register.

        Raises:
            BscanError: If the register could not be read.
        """
        data = self.__dev.read_bscan(self.__primitive)
        mask = (1 << self.__primitive.size_in_bits) - 1
        return int.from_bytes(data, "big") & mask

class FpgaInjectionReport:
    """
    The result of an injection at one location.

    FpgaDevice.inject_at returns one report, and
    FpgaDevice.inject_exhaustive returns one for each location. For
    inject_at the server returns no details, so the report repeats the
    requested location and has no net name.

    Attributes:
        far (int): The frame address of the injection.
        word_index (int): The index of the word inside the frame.
        bit_index (int): The index of the bit inside the word.
        target (TargetMemory): The memory that was targeted.
        net_name (Optional[str]): The name of the affected net, or None if
            it is not known.
    """

    def __init__(self, far: int, word_index: int, bit_index: int,
                 target: TargetMemory, net_name: Optional[str] = None):
        """
        Create an injection report.

        Parameters:
            far (int): The frame address of the injection.
            word_index (int): The index of the word inside the frame.
            bit_index (int): The index of the bit inside the word.
            target (TargetMemory): The memory that was targeted.
            net_name (Optional[str]): The name of the affected net, if
                known.
        """
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__target = target
        self.__net_name = net_name

    @property
    def far(self) -> int:
        """The frame address of the injection."""
        return self.__far

    @property
    def word_index(self) -> int:
        """The index of the word inside the frame."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """The index of the bit inside the word."""
        return self.__bit_index

    @property
    def target(self) -> TargetMemory:
        """The memory that was targeted."""
        return self.__target

    @property
    def net_name(self) -> Optional[str]:
        """The name of the affected net, or None if it is not known."""
        return self.__net_name

class FpgaRandomInjectionReport:
    """
    The result of a single random injection.

    Returned by FpgaDevice.inject_random.

    Attributes:
        far (int): The frame address where the injection took place.
        word_index (int): The index of the word inside the frame.
        bit_index (int): The index of the bit inside the word.
        target (TargetMemory): The memory that received the injection.
        net_name (Optional[str]): The name of the net at the injection site
            when the upset hit a flip-flop, otherwise None.
    """

    def __init__(self, far: int, word_index: int, bit_index: int,
                 target: TargetMemory, net_name: Optional[str] = None):
        """
        Create a random injection report.

        Parameters:
            far (int): The frame address where the injection took place.
            word_index (int): The index of the word inside the frame.
            bit_index (int): The index of the bit inside the word.
            target (TargetMemory): The memory that received the injection.
            net_name (Optional[str]): The name of the net at the injection
                site, if known.
        """
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__target = target
        self.__net_name = net_name

    @property
    def far(self) -> int:
        """The frame address where the injection took place."""
        return self.__far

    @property
    def word_index(self) -> int:
        """The index of the word inside the frame."""
        return self.__word_index

    @property
    def bit_index(self) -> int:
        """The index of the bit inside the word."""
        return self.__bit_index

    @property
    def target(self) -> TargetMemory:
        """The memory that received the injection."""
        return self.__target

    @property
    def net_name(self) -> Optional[str]:
        """The name of the net at the injection site, or None."""
        return self.__net_name

class FpgaScrubWordSummary:
    """
    The details of one word that a scrubbing session affected.

    Attributes:
        far (int): The frame address of the affected frame.
        word_index (int): The index of the affected word.
        bit_index (int): The index of the affected bit.
        golden_word_value (int): The expected value of the word.
        erroneous_word_value (int): The value of the word that was found
            before the correction.
        ebd_word_value (int): The word at the same location in the
            essential bits (EBD) file.
        msd_word_value (int): The word at the same location in the readback
            mask (MSD) file.
        is_essential (bool): True if the affected bit is essential.
    """

    def __init__(self, far: int, word_index: int, bit_index: int,
                 golden_word_value: int, erroneous_word_value: int,
                 ebd_word_value: int, msd_word_value: int,
                 is_essential: bool):
        """
        Create a word summary.

        Parameters:
            far (int): The frame address of the affected frame.
            word_index (int): The index of the affected word.
            bit_index (int): The index of the affected bit.
            golden_word_value (int): The expected value of the word.
            erroneous_word_value (int): The value found before the
                correction.
            ebd_word_value (int): The matching word from the essential bits
                (EBD) file.
            msd_word_value (int): The matching word from the readback mask
                (MSD) file.
            is_essential (bool): True if the affected bit is essential.
        """
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
        """The frame address of the affected frame."""
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
        """The expected value of the word."""
        return self.__golden_word_value

    @property
    def erroneous_word_value(self) -> int:
        """The value of the word that was found before the correction."""
        return self.__erroneous_word_value

    @property
    def ebd_word_value(self) -> int:
        """The word at the same location in the essential bits file."""
        return self.__ebd_word_value

    @property
    def msd_word_value(self) -> int:
        """The word at the same location in the readback mask file."""
        return self.__msd_word_value

    @property
    def is_essential(self) -> bool:
        """True if the affected bit is essential."""
        return self.__is_essential

class FpgaScrubSummary:
    """
    The result of one scrub cycle in a scrubbing session.

    Attributes:
        scrub_cycle (int): The scrub cycle that this summary describes.
        correction_time_ms (int): The time spent correcting upsets, in
            milliseconds.
        idle_time_ms (int): The idle time in the cycle, in milliseconds.
        scrub_cycle_actual_duration_ms (int): The measured duration of the
            cycle, in milliseconds.
        word_summaries (list[FpgaScrubWordSummary]): The details of each
            word that the cycle affected.
    """

    def __init__(self, scrub_cycle: int, correction_time_ms: int,
                 idle_time_ms: int, scrub_cycle_actual_duration_ms: int,
                 word_summaries: list[FpgaScrubWordSummary]):
        """
        Create a scrub cycle summary.

        Parameters:
            scrub_cycle (int): The scrub cycle that this summary describes.
            correction_time_ms (int): The time spent correcting upsets, in
                milliseconds.
            idle_time_ms (int): The idle time in the cycle, in
                milliseconds.
            scrub_cycle_actual_duration_ms (int): The measured duration of
                the cycle, in milliseconds.
            word_summaries (list[FpgaScrubWordSummary]): The details of
                each affected word.
        """
        self.__scrub_cycle = scrub_cycle
        self.__correction_time_ms = correction_time_ms
        self.__idle_time_ms = idle_time_ms
        self.__scrub_cycle_actual_duration_ms = scrub_cycle_actual_duration_ms
        self.__word_summaries = word_summaries

    @property
    def scrub_cycle(self) -> int:
        """The scrub cycle that this summary describes."""
        return self.__scrub_cycle

    @property
    def correction_time_ms(self) -> int:
        """The time spent correcting upsets, in milliseconds."""
        return self.__correction_time_ms

    @property
    def idle_time_ms(self) -> int:
        """The idle time in the cycle, in milliseconds."""
        return self.__idle_time_ms

    @property
    def scrub_cycle_actual_duration_ms(self) -> int:
        """The measured duration of the cycle, in milliseconds."""
        return self.__scrub_cycle_actual_duration_ms

    @property
    def word_summaries(self) -> list[FpgaScrubWordSummary]:
        """The details of each word that the cycle affected."""
        return self.__word_summaries


class FpgaScrubReport:
    """
    The result of a completed scrubbing session.

    Returned by FpgaDevice.scrub.

    Attributes:
        scrub_summaries (list[FpgaScrubSummary]): One summary for each
            scrub cycle of the session.
    """

    def __init__(self, scrub_summaries: list[FpgaScrubSummary]):
        """
        Create a scrubbing report.

        Parameters:
            scrub_summaries (list[FpgaScrubSummary]): One summary for each
                scrub cycle.
        """
        self.__scrub_summaries = scrub_summaries

    @property
    def scrub_summaries(self) -> list[FpgaScrubSummary]:
        """One summary for each scrub cycle of the session."""
        return self.__scrub_summaries

@dataclass
class FpgaFiSession:
    """
    The settings of a fault injection campaign defined by the user.

    The shares of single bit, multiple bit and multiple cell upsets are
    percentages and must add up to 100. A campaign can only target the
    whole configuration memory or its essential bits, so storage element
    targets are not accepted. Both rules are checked when the object is
    created.

    Attributes:
        fault_type (FaultType): The fault model of the campaign.
        duration_ms (int): How long the campaign runs, in milliseconds.
        correction_time_ms (int): The correction time, in milliseconds.
        time_between_faults_ms (int): The time between consecutive faults,
            in milliseconds.
        sbu_percent (float): The share of single bit upsets, in percent.
        mbu_percent (float): The share of multiple bit upsets, in percent.
        mcu_percent (float): The share of multiple cell upsets, in percent.
        target (TargetMemory): The memory to inject into. Either CRAM or
            ESSENTIAL_CRAM.
        correct (bool): If True, injected faults are corrected.
        essential (bool): True if the campaign targets only essential bits.
            Worked out from target.
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
        """
        Check the campaign settings after the object is created.

        Raises:
            ValueError: If the upset shares do not add up to 100, or if the
                target is not CRAM or ESSENTIAL_CRAM.
        """
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
        """True if the campaign targets only essential bits."""
        return bool(self.target & TargetMemory.ESSENTIAL_CRAM)

class FpgaFiWordSummary:
    """
    The details of one word that a campaign affected.

    Attributes:
        far (int): The frame address of the injected frame.
        word_index (int): The index of the injected word.
        bit_index (int): The index of the injected bit.
        golden_word_value (int): The value of the word before the
            injection.
        injected_word_value (int): The value of the word after the
            injection.
        is_essential (bool): True if the injected bit is essential.
    """

    def __init__(self, far: int, word_index: int, bit_index: int,
                 golden_word_value: int, injected_word_value: int,
                 is_essential: bool):
        """
        Create a word summary.

        Parameters:
            far (int): The frame address of the injected frame.
            word_index (int): The index of the injected word.
            bit_index (int): The index of the injected bit.
            golden_word_value (int): The value before the injection.
            injected_word_value (int): The value after the injection.
            is_essential (bool): True if the injected bit is essential.
        """
        self.__far = far
        self.__word_index = word_index
        self.__bit_index = bit_index
        self.__golden_word_value = golden_word_value
        self.__injected_word_value = injected_word_value
        self.__is_essential = is_essential

    @property
    def far(self) -> int:
        """The frame address of the injected frame."""
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
        """The value of the word before the injection."""
        return self.__golden_word_value

    @property
    def injected_word_value(self) -> int:
        """The value of the word after the injection."""
        return self.__injected_word_value

    @property
    def is_essential(self) -> bool:
        """True if the injected bit is essential."""
        return self.__is_essential

class FpgaFiSummary:
    """
    The result of a completed fault injection campaign.

    The server only returns the list of affected words, so the number of
    injected and corrected faults is worked out on the client. If the server
    starts reporting these counts, they should be used instead.

    Attributes:
        session (FpgaFiSession): The settings that the campaign used.
        faults_injected (int): The total number of injected faults.
        corrected (int): The number of injected faults that were corrected.
        affected_words (list[FpgaFiWordSummary]): The details of each
            affected word.
    """

    def __init__(self, session: FpgaFiSession, faults_injected: int,
                 corrected: int, affected_words: list[FpgaFiWordSummary]):
        """
        Create a campaign summary.

        Parameters:
            session (FpgaFiSession): The settings that the campaign used.
            faults_injected (int): The total number of injected faults.
            corrected (int): The number of faults that were corrected.
            affected_words (list[FpgaFiWordSummary]): The details of each
                affected word.
        """
        self.__session = session
        self.__faults_injected = faults_injected
        self.__corrected = corrected
        self.__affected_words = affected_words

    @property
    def session(self) -> FpgaFiSession:
        """The settings that the campaign used."""
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


# --------------------------------------------------------------------------- #
# XADC
# --------------------------------------------------------------------------- #
class XadcSensorSelector:
    """
    An XADC sensor of the device, for FpgaDevice.xadc.

    The library defines a selector for each known sensor, for example VCCINT
    or TEMPERATURE, so selectors are not normally created by hand.

    Attributes:
        addr (int): The DRP address of the status register of the sensor.
    """

    def __init__(self, addr: int):
        """
        Create a sensor selector.

        Parameters:
            addr (int): The DRP address of the status register of the
                sensor.
        """
        self.__addr = addr

    @property
    def addr(self) -> int:
        """The DRP address of the status register of the sensor."""
        return self.__addr


class XadcSensor:
    """
    The value of an XADC sensor, as read by FpgaDevice.xadc.

    The value is in units of the International System of Units (SI): volts
    (V) for voltages and degrees Celsius (degC) for temperatures.

    Attributes:
        addr (int): The DRP address of the status register that was read.
        value (float): The value of the sensor, in V or degC.
    """

    def __init__(self, addr: int, value: float):
        """
        Create a sensor value.

        Parameters:
            addr (int): The DRP address of the status register that was
                read.
            value (float): The value of the sensor, in V or degC.
        """
        self.__addr = addr
        self.__value = value

    @property
    def addr(self) -> int:
        """The DRP address of the status register that was read."""
        return self.__addr

    @property
    def value(self) -> float:
        """The value of the sensor, in V or degC."""
        return self.__value


# The XADC sensors of the 7 series FPGAs and SoCs, at the DRP
# addresses of their status registers (UG480, Status Registers). The sensors
# of the Processing System (PS) supplies, VCCPINT, VCCPAUX and VCCO_DDR
TEMPERATURE = XadcSensorSelector(0x00)  # degC
VCCINT = XadcSensorSelector(0x01)  # V
VCCAUX = XadcSensorSelector(0x02)  # V
VREFP = XadcSensorSelector(0x04)  # V
VREFN = XadcSensorSelector(0x05)  # V
VCCBRAM = XadcSensorSelector(0x06)  # V
VCCPINT = XadcSensorSelector(0x0D)  # V
VCCPAUX = XadcSensorSelector(0x0E)  # V
VCCO_DDR = XadcSensorSelector(0x0F)  # V

# The maximum and minimum values that the XADC sensors recorded since
# power-up or the last XADC reset.
MAX_TEMPERATURE = XadcSensorSelector(0x20)  # degC
MAX_VCCINT = XadcSensorSelector(0x21)  # V
MAX_VCCAUX = XadcSensorSelector(0x22)  # V
MAX_VCCBRAM = XadcSensorSelector(0x23)  # V
MIN_TEMPERATURE = XadcSensorSelector(0x24)  # degC
MIN_VCCINT = XadcSensorSelector(0x25)  # V
MIN_VCCAUX = XadcSensorSelector(0x26)  # V
MIN_VCCBRAM = XadcSensorSelector(0x27)  # V
MAX_VCCPINT = XadcSensorSelector(0x28)  # V
MAX_VCCPAUX = XadcSensorSelector(0x29)  # V
MAX_VCCO_DDR = XadcSensorSelector(0x2A)  # V
MIN_VCCPINT = XadcSensorSelector(0x2C)  # V
MIN_VCCPAUX = XadcSensorSelector(0x2D)  # V
MIN_VCCO_DDR = XadcSensorSelector(0x2E)  # V


class XadcRegister(int, Enum):
    """
    The XADC registers, at their DRP addresses, for
    FpgaDevice.read_xadc_register and FpgaDevice.write_xadc_register.

    Only the flag register, the configuration registers and the alarm
    registers are accessible. The flag register is read only. The values are
    raw 16-bit contents. UG480 (Status Registers, Control Registers) gives the
    meaning of each bit, and the ADC transfer functions give the codes of the
    alarm thresholds. The thresholds of the Processing System (PS) supplies
    exist only in Zynq-7000 SoCs.

    The flag register shows the state of the alarms. Bit 0 is ALM0
    (temperature), bit 1 is ALM1 (VCCINT), bit 2 is ALM2 (VCCAUX), bit 3 is
    OT (over-temperature), bit 4 is ALM3 (VCCBRAM), and bits 5 to 7 are ALM4
    to ALM6 (VCCPINT, VCCPAUX, VCCO_DDR). In the default sequencer mode
    (CONFIG1), only OT operates. Bits 9 to 11 are REF, JTGR and JTGD.

    Caution: the four least significant bits of ALARM3 select the automatic
    shutdown at the over-temperature (OT) limit. The value 0011b enables it.

    Attributes:
        FLAG (XadcRegister): Flag register (3Fh), read only.
        CONFIG0 (XadcRegister): Configuration register 0 (40h).
        CONFIG1 (XadcRegister): Configuration register 1 (41h).
        CONFIG2 (XadcRegister): Configuration register 2 (42h).
        ALARM0 (XadcRegister): Temperature upper threshold (50h).
        ALARM1 (XadcRegister): VCCINT upper threshold (51h).
        ALARM2 (XadcRegister): VCCAUX upper threshold (52h).
        ALARM3 (XadcRegister): Over-temperature (OT) limit (53h).
        ALARM4 (XadcRegister): Temperature lower threshold (54h).
        ALARM5 (XadcRegister): VCCINT lower threshold (55h).
        ALARM6 (XadcRegister): VCCAUX lower threshold (56h).
        ALARM7 (XadcRegister): Over-temperature (OT) reset (57h).
        ALARM8 (XadcRegister): VCCBRAM upper threshold (58h).
        ALARM9 (XadcRegister): VCCPINT upper threshold (59h), Zynq-7000
            only.
        ALARM10 (XadcRegister): VCCPAUX upper threshold (5Ah), Zynq-7000
            only.
        ALARM11 (XadcRegister): VCCO_DDR upper threshold (5Bh), Zynq-7000
            only.
        ALARM12 (XadcRegister): VCCBRAM lower threshold (5Ch).
        ALARM13 (XadcRegister): VCCPINT lower threshold (5Dh), Zynq-7000
            only.
        ALARM14 (XadcRegister): VCCPAUX lower threshold (5Eh), Zynq-7000
            only.
        ALARM15 (XadcRegister): VCCO_DDR lower threshold (5Fh), Zynq-7000
            only.
    """

    FLAG = 0x3F
    CONFIG0 = 0x40
    CONFIG1 = 0x41
    CONFIG2 = 0x42
    ALARM0 = 0x50
    ALARM1 = 0x51
    ALARM2 = 0x52
    ALARM3 = 0x53
    ALARM4 = 0x54
    ALARM5 = 0x55
    ALARM6 = 0x56
    ALARM7 = 0x57
    ALARM8 = 0x58
    ALARM9 = 0x59
    ALARM10 = 0x5A
    ALARM11 = 0x5B
    ALARM12 = 0x5C
    ALARM13 = 0x5D
    ALARM14 = 0x5E
    ALARM15 = 0x5F
