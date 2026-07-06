from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FpgaFileType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_FILE_TYPE_UNSPECIFIED: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_RBD: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_MSD: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_EBD: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_LL: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_BIT: _ClassVar[FpgaFileType]

class FpgaBitCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_BIT_CATEGORY_UNSPECIFIED: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_CRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_ESSENTIAL_CRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_BRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_FLIP_FLOP: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_LUTRAM: _ClassVar[FpgaBitCategory]

class FpgaTargetKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_TARGET_KIND_UNSPECIFIED: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_CRAM: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_FLIP_FLOP: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_LUTRAM: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_BRAM: _ClassVar[FpgaTargetKind]

class FpgaFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_FAULT_TYPE_UNSPECIFIED: _ClassVar[FpgaFaultType]
    FPGA_FAULT_TYPE_SBU: _ClassVar[FpgaFaultType]
    FPGA_FAULT_TYPE_MBU: _ClassVar[FpgaFaultType]
    FPGA_FAULT_TYPE_MCU: _ClassVar[FpgaFaultType]
    FPGA_FAULT_TYPE_MIXED: _ClassVar[FpgaFaultType]
FPGA_FILE_TYPE_UNSPECIFIED: FpgaFileType
FPGA_FILE_TYPE_RBD: FpgaFileType
FPGA_FILE_TYPE_MSD: FpgaFileType
FPGA_FILE_TYPE_EBD: FpgaFileType
FPGA_FILE_TYPE_LL: FpgaFileType
FPGA_FILE_TYPE_BIT: FpgaFileType
FPGA_BIT_CATEGORY_UNSPECIFIED: FpgaBitCategory
FPGA_BIT_CATEGORY_CRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_ESSENTIAL_CRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_BRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_FLIP_FLOP: FpgaBitCategory
FPGA_BIT_CATEGORY_LUTRAM: FpgaBitCategory
FPGA_TARGET_KIND_UNSPECIFIED: FpgaTargetKind
FPGA_TARGET_KIND_CRAM: FpgaTargetKind
FPGA_TARGET_KIND_FLIP_FLOP: FpgaTargetKind
FPGA_TARGET_KIND_LUTRAM: FpgaTargetKind
FPGA_TARGET_KIND_BRAM: FpgaTargetKind
FPGA_FAULT_TYPE_UNSPECIFIED: FpgaFaultType
FPGA_FAULT_TYPE_SBU: FpgaFaultType
FPGA_FAULT_TYPE_MBU: FpgaFaultType
FPGA_FAULT_TYPE_MCU: FpgaFaultType
FPGA_FAULT_TYPE_MIXED: FpgaFaultType

class FpgaDeviceDetails(_message.Message):
    __slots__ = ("device_part_number", "programmer_part_number")
    DEVICE_PART_NUMBER_FIELD_NUMBER: _ClassVar[int]
    PROGRAMMER_PART_NUMBER_FIELD_NUMBER: _ClassVar[int]
    device_part_number: str
    programmer_part_number: str
    def __init__(self, device_part_number: _Optional[str] = ..., programmer_part_number: _Optional[str] = ...) -> None: ...

class FpgaDesignFilePathRequest(_message.Message):
    __slots__ = ("type", "path")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    type: FpgaFileType
    path: str
    def __init__(self, type: _Optional[_Union[FpgaFileType, str]] = ..., path: _Optional[str] = ...) -> None: ...

class FpgaBitCountRequest(_message.Message):
    __slots__ = ("category",)
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    category: FpgaBitCategory
    def __init__(self, category: _Optional[_Union[FpgaBitCategory, str]] = ...) -> None: ...

class FpgaBitCount(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class FpgaBitCounts(_message.Message):
    __slots__ = ("cram_bits", "essential_cram_bits", "bram_bits", "flip_flop_bits", "lutram_bits")
    CRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    ESSENTIAL_CRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    BRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    FLIP_FLOP_BITS_FIELD_NUMBER: _ClassVar[int]
    LUTRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    cram_bits: int
    essential_cram_bits: int
    bram_bits: int
    flip_flop_bits: int
    lutram_bits: int
    def __init__(self, cram_bits: _Optional[int] = ..., essential_cram_bits: _Optional[int] = ..., bram_bits: _Optional[int] = ..., flip_flop_bits: _Optional[int] = ..., lutram_bits: _Optional[int] = ...) -> None: ...

class FpgaScrubSession(_message.Message):
    __slots__ = ("scrub_cycle", "duration_ms", "id")
    SCRUB_CYCLE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    scrub_cycle: int
    duration_ms: int
    id: str
    def __init__(self, scrub_cycle: _Optional[int] = ..., duration_ms: _Optional[int] = ..., id: _Optional[str] = ...) -> None: ...

class FpgaScrubSummary(_message.Message):
    __slots__ = ("scrub_cycle", "correction_time_ms", "idle_time_ms", "scrub_cycle_actual_duration_ms", "word_summaries")
    SCRUB_CYCLE_FIELD_NUMBER: _ClassVar[int]
    CORRECTION_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    IDLE_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    SCRUB_CYCLE_ACTUAL_DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    WORD_SUMMARIES_FIELD_NUMBER: _ClassVar[int]
    scrub_cycle: int
    correction_time_ms: int
    idle_time_ms: int
    scrub_cycle_actual_duration_ms: int
    word_summaries: _containers.RepeatedCompositeFieldContainer[FpgaScrubWordSummary]
    def __init__(self, scrub_cycle: _Optional[int] = ..., correction_time_ms: _Optional[int] = ..., idle_time_ms: _Optional[int] = ..., scrub_cycle_actual_duration_ms: _Optional[int] = ..., word_summaries: _Optional[_Iterable[_Union[FpgaScrubWordSummary, _Mapping]]] = ...) -> None: ...

class FpgaScrubReport(_message.Message):
    __slots__ = ("scrub_summaries",)
    SCRUB_SUMMARIES_FIELD_NUMBER: _ClassVar[int]
    scrub_summaries: _containers.RepeatedCompositeFieldContainer[FpgaScrubSummary]
    def __init__(self, scrub_summaries: _Optional[_Iterable[_Union[FpgaScrubSummary, _Mapping]]] = ...) -> None: ...

class FpgaScrubWordSummary(_message.Message):
    __slots__ = ("far", "word_index", "bit_index", "golden_word_value", "erroneous_word_value", "ebd_word_value", "msd_word_value", "is_essential")
    FAR_FIELD_NUMBER: _ClassVar[int]
    WORD_INDEX_FIELD_NUMBER: _ClassVar[int]
    BIT_INDEX_FIELD_NUMBER: _ClassVar[int]
    GOLDEN_WORD_VALUE_FIELD_NUMBER: _ClassVar[int]
    ERRONEOUS_WORD_VALUE_FIELD_NUMBER: _ClassVar[int]
    EBD_WORD_VALUE_FIELD_NUMBER: _ClassVar[int]
    MSD_WORD_VALUE_FIELD_NUMBER: _ClassVar[int]
    IS_ESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    far: int
    word_index: int
    bit_index: int
    golden_word_value: int
    erroneous_word_value: int
    ebd_word_value: int
    msd_word_value: int
    is_essential: bool
    def __init__(self, far: _Optional[int] = ..., word_index: _Optional[int] = ..., bit_index: _Optional[int] = ..., golden_word_value: _Optional[int] = ..., erroneous_word_value: _Optional[int] = ..., ebd_word_value: _Optional[int] = ..., msd_word_value: _Optional[int] = ..., is_essential: bool = ...) -> None: ...

class FpgaFarListExtractRequest(_message.Message):
    __slots__ = ("bitstream_path",)
    BITSTREAM_PATH_FIELD_NUMBER: _ClassVar[int]
    bitstream_path: str
    def __init__(self, bitstream_path: _Optional[str] = ...) -> None: ...

class FpgaFarListExtractResponse(_message.Message):
    __slots__ = ("fars",)
    FARS_FIELD_NUMBER: _ClassVar[int]
    fars: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, fars: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaFarListExcludeRequest(_message.Message):
    __slots__ = ("fars",)
    FARS_FIELD_NUMBER: _ClassVar[int]
    fars: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, fars: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaReadbackTarget(_message.Message):
    __slots__ = ("start_frame_address", "end_frame_address")
    START_FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    END_FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    start_frame_address: int
    end_frame_address: int
    def __init__(self, start_frame_address: _Optional[int] = ..., end_frame_address: _Optional[int] = ...) -> None: ...

class FpgaFrame(_message.Message):
    __slots__ = ("frame_address", "words")
    FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WORDS_FIELD_NUMBER: _ClassVar[int]
    frame_address: int
    words: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, frame_address: _Optional[int] = ..., words: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaReadbackDetail(_message.Message):
    __slots__ = ("frames",)
    FRAMES_FIELD_NUMBER: _ClassVar[int]
    frames: _containers.RepeatedCompositeFieldContainer[FpgaFrame]
    def __init__(self, frames: _Optional[_Iterable[_Union[FpgaFrame, _Mapping]]] = ...) -> None: ...

class FpgaBscanTarget(_message.Message):
    __slots__ = ("user_register_id", "value", "useful_bits")
    USER_REGISTER_ID_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    USEFUL_BITS_FIELD_NUMBER: _ClassVar[int]
    user_register_id: int
    value: bytes
    useful_bits: int
    def __init__(self, user_register_id: _Optional[int] = ..., value: _Optional[bytes] = ..., useful_bits: _Optional[int] = ...) -> None: ...

class FpgaBscanOutput(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: bytes
    def __init__(self, value: _Optional[bytes] = ...) -> None: ...

class FpgaInjectionTarget(_message.Message):
    __slots__ = ("frame_address", "word_index", "bit_index", "kind", "net_name")
    FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WORD_INDEX_FIELD_NUMBER: _ClassVar[int]
    BIT_INDEX_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    NET_NAME_FIELD_NUMBER: _ClassVar[int]
    frame_address: int
    word_index: int
    bit_index: int
    kind: FpgaTargetKind
    net_name: str
    def __init__(self, frame_address: _Optional[int] = ..., word_index: _Optional[int] = ..., bit_index: _Optional[int] = ..., kind: _Optional[_Union[FpgaTargetKind, str]] = ..., net_name: _Optional[str] = ...) -> None: ...

class FpgaRandomInjectionOptions(_message.Message):
    __slots__ = ("include_essential", "include_flip_flops", "include_lutrams", "include_brams")
    INCLUDE_ESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_FLIP_FLOPS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_LUTRAMS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_BRAMS_FIELD_NUMBER: _ClassVar[int]
    include_essential: bool
    include_flip_flops: bool
    include_lutrams: bool
    include_brams: bool
    def __init__(self, include_essential: bool = ..., include_flip_flops: bool = ..., include_lutrams: bool = ..., include_brams: bool = ...) -> None: ...

class FpgaRandomInjectionReport(_message.Message):
    __slots__ = ("target",)
    TARGET_FIELD_NUMBER: _ClassVar[int]
    target: FpgaInjectionTarget
    def __init__(self, target: _Optional[_Union[FpgaInjectionTarget, _Mapping]] = ...) -> None: ...

class FpgaFiSession(_message.Message):
    __slots__ = ("type", "duration_ms", "correction_time_ms", "time_between_faults_ms", "sbu_percent", "mbu_percent", "mcu_percent", "essential", "correct")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    CORRECTION_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    TIME_BETWEEN_FAULTS_MS_FIELD_NUMBER: _ClassVar[int]
    SBU_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MBU_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MCU_PERCENT_FIELD_NUMBER: _ClassVar[int]
    ESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    CORRECT_FIELD_NUMBER: _ClassVar[int]
    type: FpgaFaultType
    duration_ms: int
    correction_time_ms: int
    time_between_faults_ms: int
    sbu_percent: float
    mbu_percent: float
    mcu_percent: float
    essential: bool
    correct: bool
    def __init__(self, type: _Optional[_Union[FpgaFaultType, str]] = ..., duration_ms: _Optional[int] = ..., correction_time_ms: _Optional[int] = ..., time_between_faults_ms: _Optional[int] = ..., sbu_percent: _Optional[float] = ..., mbu_percent: _Optional[float] = ..., mcu_percent: _Optional[float] = ..., essential: bool = ..., correct: bool = ...) -> None: ...

class FpgaFiWordSummary(_message.Message):
    __slots__ = ("far", "word_index", "bit_index", "golden_word_value", "injected_word_value", "is_essential")
    FAR_FIELD_NUMBER: _ClassVar[int]
    WORD_INDEX_FIELD_NUMBER: _ClassVar[int]
    BIT_INDEX_FIELD_NUMBER: _ClassVar[int]
    GOLDEN_WORD_VALUE_FIELD_NUMBER: _ClassVar[int]
    INJECTED_WORD_VALUE_FIELD_NUMBER: _ClassVar[int]
    IS_ESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    far: int
    word_index: int
    bit_index: int
    golden_word_value: int
    injected_word_value: int
    is_essential: bool
    def __init__(self, far: _Optional[int] = ..., word_index: _Optional[int] = ..., bit_index: _Optional[int] = ..., golden_word_value: _Optional[int] = ..., injected_word_value: _Optional[int] = ..., is_essential: bool = ...) -> None: ...

class FpgaFiSummary(_message.Message):
    __slots__ = ("type", "duration_ms", "correction_time_ms", "time_between_faults_ms", "word_summaries")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    CORRECTION_TIME_MS_FIELD_NUMBER: _ClassVar[int]
    TIME_BETWEEN_FAULTS_MS_FIELD_NUMBER: _ClassVar[int]
    WORD_SUMMARIES_FIELD_NUMBER: _ClassVar[int]
    type: FpgaFaultType
    duration_ms: int
    correction_time_ms: int
    time_between_faults_ms: int
    word_summaries: _containers.RepeatedCompositeFieldContainer[FpgaFiWordSummary]
    def __init__(self, type: _Optional[_Union[FpgaFaultType, str]] = ..., duration_ms: _Optional[int] = ..., correction_time_ms: _Optional[int] = ..., time_between_faults_ms: _Optional[int] = ..., word_summaries: _Optional[_Iterable[_Union[FpgaFiWordSummary, _Mapping]]] = ...) -> None: ...
