from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FpgaFarModel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_7SERIES_FAR_MODEL: _ClassVar[FpgaFarModel]
    FPGA_ULTRASCALE_FAR_MODEL: _ClassVar[FpgaFarModel]

class FpgaFileType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_FILE_TYPE_UNSPECIFIED: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_RBD: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_MSD: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_EBD: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_LL: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_BIT: _ClassVar[FpgaFileType]
    FPGA_FILE_TYPE_XDC: _ClassVar[FpgaFileType]

class FpgaBitCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_BIT_CATEGORY_UNSPECIFIED: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_CRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_ESSENTIAL_CRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_BRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_FLIP_FLOP: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_LUTRAM: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_PBLOCK: _ClassVar[FpgaBitCategory]
    FPGA_BIT_CATEGORY_ESSENTIAL_PBLOCK: _ClassVar[FpgaBitCategory]

class FpgaTargetKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_TARGET_KIND_UNSPECIFIED: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_CRAM: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_FLIP_FLOP: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_LUTRAM: _ClassVar[FpgaTargetKind]
    FPGA_TARGET_KIND_BRAM: _ClassVar[FpgaTargetKind]

class FpgaFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FPGA_FAULT_TYPE_RANDOM: _ClassVar[FpgaFaultType]
    FPGA_FAULT_TYPE_EXHAUSTIVE: _ClassVar[FpgaFaultType]
FPGA_7SERIES_FAR_MODEL: FpgaFarModel
FPGA_ULTRASCALE_FAR_MODEL: FpgaFarModel
FPGA_FILE_TYPE_UNSPECIFIED: FpgaFileType
FPGA_FILE_TYPE_RBD: FpgaFileType
FPGA_FILE_TYPE_MSD: FpgaFileType
FPGA_FILE_TYPE_EBD: FpgaFileType
FPGA_FILE_TYPE_LL: FpgaFileType
FPGA_FILE_TYPE_BIT: FpgaFileType
FPGA_FILE_TYPE_XDC: FpgaFileType
FPGA_BIT_CATEGORY_UNSPECIFIED: FpgaBitCategory
FPGA_BIT_CATEGORY_CRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_ESSENTIAL_CRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_BRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_FLIP_FLOP: FpgaBitCategory
FPGA_BIT_CATEGORY_LUTRAM: FpgaBitCategory
FPGA_BIT_CATEGORY_PBLOCK: FpgaBitCategory
FPGA_BIT_CATEGORY_ESSENTIAL_PBLOCK: FpgaBitCategory
FPGA_TARGET_KIND_UNSPECIFIED: FpgaTargetKind
FPGA_TARGET_KIND_CRAM: FpgaTargetKind
FPGA_TARGET_KIND_FLIP_FLOP: FpgaTargetKind
FPGA_TARGET_KIND_LUTRAM: FpgaTargetKind
FPGA_TARGET_KIND_BRAM: FpgaTargetKind
FPGA_FAULT_TYPE_RANDOM: FpgaFaultType
FPGA_FAULT_TYPE_EXHAUSTIVE: FpgaFaultType

class FpgaDevice(_message.Message):
    __slots__ = ("part_number", "serial_number")
    PART_NUMBER_FIELD_NUMBER: _ClassVar[int]
    SERIAL_NUMBER_FIELD_NUMBER: _ClassVar[int]
    part_number: str
    serial_number: str
    def __init__(self, part_number: _Optional[str] = ..., serial_number: _Optional[str] = ...) -> None: ...

class FpgaDevicesResponse(_message.Message):
    __slots__ = ("devices",)
    DEVICES_FIELD_NUMBER: _ClassVar[int]
    devices: _containers.RepeatedCompositeFieldContainer[FpgaDevice]
    def __init__(self, devices: _Optional[_Iterable[_Union[FpgaDevice, _Mapping]]] = ...) -> None: ...

class FpgaPblock(_message.Message):
    __slots__ = ("name", "clauses")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CLAUSES_FIELD_NUMBER: _ClassVar[int]
    name: str
    clauses: _containers.RepeatedCompositeFieldContainer[FpgaPblockClause]
    def __init__(self, name: _Optional[str] = ..., clauses: _Optional[_Iterable[_Union[FpgaPblockClause, _Mapping]]] = ...) -> None: ...

class FpgaPblocks(_message.Message):
    __slots__ = ("pblocks",)
    PBLOCKS_FIELD_NUMBER: _ClassVar[int]
    pblocks: _containers.RepeatedCompositeFieldContainer[FpgaPblock]
    def __init__(self, pblocks: _Optional[_Iterable[_Union[FpgaPblock, _Mapping]]] = ...) -> None: ...

class FpgaPblockClause(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: str
    def __init__(self, value: _Optional[str] = ...) -> None: ...

class FpgaPblockRange(_message.Message):
    __slots__ = ("to",)
    FROM_FIELD_NUMBER: _ClassVar[int]
    TO_FIELD_NUMBER: _ClassVar[int]
    to: int
    def __init__(self, to: _Optional[int] = ..., **kwargs) -> None: ...

class FpgaPblockAreaRange(_message.Message):
    __slots__ = ("bit_range", "word_range")
    BIT_RANGE_FIELD_NUMBER: _ClassVar[int]
    WORD_RANGE_FIELD_NUMBER: _ClassVar[int]
    bit_range: FpgaPblockRange
    word_range: FpgaPblockRange
    def __init__(self, bit_range: _Optional[_Union[FpgaPblockRange, _Mapping]] = ..., word_range: _Optional[_Union[FpgaPblockRange, _Mapping]] = ...) -> None: ...

class FpgaPblockFar(_message.Message):
    __slots__ = ("far", "occupied_area")
    FAR_FIELD_NUMBER: _ClassVar[int]
    OCCUPIED_AREA_FIELD_NUMBER: _ClassVar[int]
    far: int
    occupied_area: _containers.RepeatedCompositeFieldContainer[FpgaPblockAreaRange]
    def __init__(self, far: _Optional[int] = ..., occupied_area: _Optional[_Iterable[_Union[FpgaPblockAreaRange, _Mapping]]] = ...) -> None: ...

class FpgaPblockFars(_message.Message):
    __slots__ = ("fars",)
    FARS_FIELD_NUMBER: _ClassVar[int]
    fars: _containers.RepeatedCompositeFieldContainer[FpgaPblockFar]
    def __init__(self, fars: _Optional[_Iterable[_Union[FpgaPblockFar, _Mapping]]] = ...) -> None: ...

class FpgaFarDecodeRequest(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class FpgaFarDecodeResponse(_message.Message):
    __slots__ = ("far_model", "block_type", "top_bottom", "row_address", "column_address", "minor_address")
    FAR_MODEL_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TYPE_FIELD_NUMBER: _ClassVar[int]
    TOP_BOTTOM_FIELD_NUMBER: _ClassVar[int]
    ROW_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    COLUMN_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    MINOR_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    far_model: FpgaFarModel
    block_type: int
    top_bottom: int
    row_address: int
    column_address: int
    minor_address: int
    def __init__(self, far_model: _Optional[_Union[FpgaFarModel, str]] = ..., block_type: _Optional[int] = ..., top_bottom: _Optional[int] = ..., row_address: _Optional[int] = ..., column_address: _Optional[int] = ..., minor_address: _Optional[int] = ...) -> None: ...

class FpgaReadRegisterRequest(_message.Message):
    __slots__ = ("addr",)
    ADDR_FIELD_NUMBER: _ClassVar[int]
    addr: int
    def __init__(self, addr: _Optional[int] = ...) -> None: ...

class FpgaWriteRegisterRequest(_message.Message):
    __slots__ = ("addr", "value")
    ADDR_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    addr: int
    value: int
    def __init__(self, addr: _Optional[int] = ..., value: _Optional[int] = ...) -> None: ...

class FpgaRegisterContent(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class VersionDetails(_message.Message):
    __slots__ = ("version",)
    VERSION_FIELD_NUMBER: _ClassVar[int]
    version: str
    def __init__(self, version: _Optional[str] = ...) -> None: ...

class FpgaDeviceDetails(_message.Message):
    __slots__ = ("device_serial_number",)
    DEVICE_SERIAL_NUMBER_FIELD_NUMBER: _ClassVar[int]
    device_serial_number: str
    def __init__(self, device_serial_number: _Optional[str] = ...) -> None: ...

class FpgaDesignFileInfo(_message.Message):
    __slots__ = ("type", "relative_path", "compression", "size", "sha256")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_PATH_FIELD_NUMBER: _ClassVar[int]
    COMPRESSION_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    type: FpgaFileType
    relative_path: str
    compression: str
    size: int
    sha256: str
    def __init__(self, type: _Optional[_Union[FpgaFileType, str]] = ..., relative_path: _Optional[str] = ..., compression: _Optional[str] = ..., size: _Optional[int] = ..., sha256: _Optional[str] = ...) -> None: ...

class UploadDesignFileRequest(_message.Message):
    __slots__ = ("info", "chunk")
    INFO_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    info: FpgaDesignFileInfo
    chunk: bytes
    def __init__(self, info: _Optional[_Union[FpgaDesignFileInfo, _Mapping]] = ..., chunk: _Optional[bytes] = ...) -> None: ...

class FpgaDesignFileResponse(_message.Message):
    __slots__ = ("stored_path", "bytes_written", "sha256")
    STORED_PATH_FIELD_NUMBER: _ClassVar[int]
    BYTES_WRITTEN_FIELD_NUMBER: _ClassVar[int]
    SHA256_FIELD_NUMBER: _ClassVar[int]
    stored_path: str
    bytes_written: int
    sha256: str
    def __init__(self, stored_path: _Optional[str] = ..., bytes_written: _Optional[int] = ..., sha256: _Optional[str] = ...) -> None: ...

class FpgaBitCountRequest(_message.Message):
    __slots__ = ("category", "pblock_name")
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    PBLOCK_NAME_FIELD_NUMBER: _ClassVar[int]
    category: FpgaBitCategory
    pblock_name: str
    def __init__(self, category: _Optional[_Union[FpgaBitCategory, str]] = ..., pblock_name: _Optional[str] = ...) -> None: ...

class FpgaBitCount(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class FpgaBitCounts(_message.Message):
    __slots__ = ("cram_bits", "essential_cram_bits", "bram_bits", "flip_flop_bits", "lutram_bits", "pblock_bits", "pblock_essential_bits")
    CRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    ESSENTIAL_CRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    BRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    FLIP_FLOP_BITS_FIELD_NUMBER: _ClassVar[int]
    LUTRAM_BITS_FIELD_NUMBER: _ClassVar[int]
    PBLOCK_BITS_FIELD_NUMBER: _ClassVar[int]
    PBLOCK_ESSENTIAL_BITS_FIELD_NUMBER: _ClassVar[int]
    cram_bits: int
    essential_cram_bits: int
    bram_bits: int
    flip_flop_bits: int
    lutram_bits: int
    pblock_bits: int
    pblock_essential_bits: int
    def __init__(self, cram_bits: _Optional[int] = ..., essential_cram_bits: _Optional[int] = ..., bram_bits: _Optional[int] = ..., flip_flop_bits: _Optional[int] = ..., lutram_bits: _Optional[int] = ..., pblock_bits: _Optional[int] = ..., pblock_essential_bits: _Optional[int] = ...) -> None: ...

class FpgaScrubSession(_message.Message):
    __slots__ = ("scrub_cycle", "duration_ms", "essential", "id")
    SCRUB_CYCLE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    ESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    scrub_cycle: int
    duration_ms: int
    essential: bool
    id: str
    def __init__(self, scrub_cycle: _Optional[int] = ..., duration_ms: _Optional[int] = ..., essential: bool = ..., id: _Optional[str] = ...) -> None: ...

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

class FpgaFarListResponse(_message.Message):
    __slots__ = ("fars",)
    FARS_FIELD_NUMBER: _ClassVar[int]
    fars: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, fars: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaReadbackTarget(_message.Message):
    __slots__ = ("start_frame_address", "end_frame_address", "capture")
    START_FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    END_FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    CAPTURE_FIELD_NUMBER: _ClassVar[int]
    start_frame_address: int
    end_frame_address: int
    capture: bool
    def __init__(self, start_frame_address: _Optional[int] = ..., end_frame_address: _Optional[int] = ..., capture: bool = ...) -> None: ...

class FpgaFrame(_message.Message):
    __slots__ = ("frame_address", "words")
    FRAME_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    WORDS_FIELD_NUMBER: _ClassVar[int]
    frame_address: int
    words: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, frame_address: _Optional[int] = ..., words: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaFrames(_message.Message):
    __slots__ = ("frames",)
    FRAMES_FIELD_NUMBER: _ClassVar[int]
    frames: _containers.RepeatedCompositeFieldContainer[FpgaFrame]
    def __init__(self, frames: _Optional[_Iterable[_Union[FpgaFrame, _Mapping]]] = ...) -> None: ...

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

class FpgaInjectionOptions(_message.Message):
    __slots__ = ("essentials", "include_flip_flops", "include_lutrams", "include_brams", "include_pblock", "pblock_name")
    ESSENTIALS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_FLIP_FLOPS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_LUTRAMS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_BRAMS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_PBLOCK_FIELD_NUMBER: _ClassVar[int]
    PBLOCK_NAME_FIELD_NUMBER: _ClassVar[int]
    essentials: bool
    include_flip_flops: bool
    include_lutrams: bool
    include_brams: bool
    include_pblock: bool
    pblock_name: str
    def __init__(self, essentials: bool = ..., include_flip_flops: bool = ..., include_lutrams: bool = ..., include_brams: bool = ..., include_pblock: bool = ..., pblock_name: _Optional[str] = ...) -> None: ...

class FpgaSingleInjectionReport(_message.Message):
    __slots__ = ("target",)
    TARGET_FIELD_NUMBER: _ClassVar[int]
    target: FpgaInjectionTarget
    def __init__(self, target: _Optional[_Union[FpgaInjectionTarget, _Mapping]] = ...) -> None: ...

class FpgaExhaustiveInjectionReport(_message.Message):
    __slots__ = ("targets", "injected_bit_count")
    TARGETS_FIELD_NUMBER: _ClassVar[int]
    INJECTED_BIT_COUNT_FIELD_NUMBER: _ClassVar[int]
    targets: _containers.RepeatedCompositeFieldContainer[FpgaInjectionTarget]
    injected_bit_count: int
    def __init__(self, targets: _Optional[_Iterable[_Union[FpgaInjectionTarget, _Mapping]]] = ..., injected_bit_count: _Optional[int] = ...) -> None: ...

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
