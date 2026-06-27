from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FpgaBitCount(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class FpgaWord(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, values: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaFarListExtractRequest(_message.Message):
    __slots__ = ("bitstreamPath",)
    BITSTREAMPATH_FIELD_NUMBER: _ClassVar[int]
    bitstreamPath: str
    def __init__(self, bitstreamPath: _Optional[str] = ...) -> None: ...

class FpgaFarListExtractResult(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, values: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaFarListExcludeRequest(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, values: _Optional[_Iterable[int]] = ...) -> None: ...

class FpgaFrame(_message.Message):
    __slots__ = ("frameAddress", "words")
    FRAMEADDRESS_FIELD_NUMBER: _ClassVar[int]
    WORDS_FIELD_NUMBER: _ClassVar[int]
    frameAddress: int
    words: _containers.RepeatedCompositeFieldContainer[FpgaWord]
    def __init__(self, frameAddress: _Optional[int] = ..., words: _Optional[_Iterable[_Union[FpgaWord, _Mapping]]] = ...) -> None: ...

class FpgaReadbackDetail(_message.Message):
    __slots__ = ("frames",)
    FRAMES_FIELD_NUMBER: _ClassVar[int]
    frames: _containers.RepeatedCompositeFieldContainer[FpgaFrame]
    def __init__(self, frames: _Optional[_Iterable[_Union[FpgaFrame, _Mapping]]] = ...) -> None: ...

class FpgaReadbackTarget(_message.Message):
    __slots__ = ("startFrameAddress", "endFrameAddress")
    STARTFRAMEADDRESS_FIELD_NUMBER: _ClassVar[int]
    ENDFRAMEADDRESS_FIELD_NUMBER: _ClassVar[int]
    startFrameAddress: int
    endFrameAddress: int
    def __init__(self, startFrameAddress: _Optional[int] = ..., endFrameAddress: _Optional[int] = ...) -> None: ...

class FpgaDeviceDetails(_message.Message):
    __slots__ = ("devicePartNumber", "programmerPartNumber")
    DEVICEPARTNUMBER_FIELD_NUMBER: _ClassVar[int]
    PROGRAMMERPARTNUMBER_FIELD_NUMBER: _ClassVar[int]
    devicePartNumber: str
    programmerPartNumber: str
    def __init__(self, devicePartNumber: _Optional[str] = ..., programmerPartNumber: _Optional[str] = ...) -> None: ...

class FpgaBscanTarget(_message.Message):
    __slots__ = ("userRegisterId", "value", "usefulBits")
    USERREGISTERID_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    USEFULBITS_FIELD_NUMBER: _ClassVar[int]
    userRegisterId: int
    value: bytes
    usefulBits: int
    def __init__(self, userRegisterId: _Optional[int] = ..., value: _Optional[bytes] = ..., usefulBits: _Optional[int] = ...) -> None: ...

class FpgaBscanOutput(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: bytes
    def __init__(self, value: _Optional[bytes] = ...) -> None: ...

class FpgaInjectionTarget(_message.Message):
    __slots__ = ("frameAddress", "wordIndex", "bitIndex", "isFlipFlop", "isLutRam", "isBram", "netName")
    FRAMEADDRESS_FIELD_NUMBER: _ClassVar[int]
    WORDINDEX_FIELD_NUMBER: _ClassVar[int]
    BITINDEX_FIELD_NUMBER: _ClassVar[int]
    ISFLIPFLOP_FIELD_NUMBER: _ClassVar[int]
    ISLUTRAM_FIELD_NUMBER: _ClassVar[int]
    ISBRAM_FIELD_NUMBER: _ClassVar[int]
    NETNAME_FIELD_NUMBER: _ClassVar[int]
    frameAddress: int
    wordIndex: int
    bitIndex: int
    isFlipFlop: bool
    isLutRam: bool
    isBram: bool
    netName: str
    def __init__(self, frameAddress: _Optional[int] = ..., wordIndex: _Optional[int] = ..., bitIndex: _Optional[int] = ..., isFlipFlop: bool = ..., isLutRam: bool = ..., isBram: bool = ..., netName: _Optional[str] = ...) -> None: ...

class FpgaRandomInjectionReport(_message.Message):
    __slots__ = ("target",)
    TARGET_FIELD_NUMBER: _ClassVar[int]
    target: FpgaInjectionTarget
    def __init__(self, target: _Optional[_Union[FpgaInjectionTarget, _Mapping]] = ...) -> None: ...

class FpgaRandomInjectionOptions(_message.Message):
    __slots__ = ("includeEssential", "includeFlipFlops", "includeLutRams", "includeBrams")
    INCLUDEESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    INCLUDEFLIPFLOPS_FIELD_NUMBER: _ClassVar[int]
    INCLUDELUTRAMS_FIELD_NUMBER: _ClassVar[int]
    INCLUDEBRAMS_FIELD_NUMBER: _ClassVar[int]
    includeEssential: bool
    includeFlipFlops: bool
    includeLutRams: bool
    includeBrams: bool
    def __init__(self, includeEssential: bool = ..., includeFlipFlops: bool = ..., includeLutRams: bool = ..., includeBrams: bool = ...) -> None: ...

class FilePath(_message.Message):
    __slots__ = ("path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    path: str
    def __init__(self, path: _Optional[str] = ...) -> None: ...

class FpgaFiSession(_message.Message):
    __slots__ = ("type", "duration", "correctionTime", "timeBetweenFaults", "sbuPercent", "mbuPercent", "mcuPercent", "essential", "correct")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    CORRECTIONTIME_FIELD_NUMBER: _ClassVar[int]
    TIMEBETWEENFAULTS_FIELD_NUMBER: _ClassVar[int]
    SBUPERCENT_FIELD_NUMBER: _ClassVar[int]
    MBUPERCENT_FIELD_NUMBER: _ClassVar[int]
    MCUPERCENT_FIELD_NUMBER: _ClassVar[int]
    ESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    CORRECT_FIELD_NUMBER: _ClassVar[int]
    type: int
    duration: int
    correctionTime: int
    timeBetweenFaults: int
    sbuPercent: float
    mbuPercent: float
    mcuPercent: float
    essential: bool
    correct: bool
    def __init__(self, type: _Optional[int] = ..., duration: _Optional[int] = ..., correctionTime: _Optional[int] = ..., timeBetweenFaults: _Optional[int] = ..., sbuPercent: _Optional[float] = ..., mbuPercent: _Optional[float] = ..., mcuPercent: _Optional[float] = ..., essential: bool = ..., correct: bool = ...) -> None: ...

class FpgaWordSummary(_message.Message):
    __slots__ = ("far", "wordIndex", "bitIndex", "goldenWordValue", "injectedWordValue", "isEssential")
    FAR_FIELD_NUMBER: _ClassVar[int]
    WORDINDEX_FIELD_NUMBER: _ClassVar[int]
    BITINDEX_FIELD_NUMBER: _ClassVar[int]
    GOLDENWORDVALUE_FIELD_NUMBER: _ClassVar[int]
    INJECTEDWORDVALUE_FIELD_NUMBER: _ClassVar[int]
    ISESSENTIAL_FIELD_NUMBER: _ClassVar[int]
    far: int
    wordIndex: int
    bitIndex: int
    goldenWordValue: int
    injectedWordValue: int
    isEssential: bool
    def __init__(self, far: _Optional[int] = ..., wordIndex: _Optional[int] = ..., bitIndex: _Optional[int] = ..., goldenWordValue: _Optional[int] = ..., injectedWordValue: _Optional[int] = ..., isEssential: bool = ...) -> None: ...

class FpgaFiSummary(_message.Message):
    __slots__ = ("type", "duration", "correctionTime", "timeBetweenFaults", "wordSummary")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    CORRECTIONTIME_FIELD_NUMBER: _ClassVar[int]
    TIMEBETWEENFAULTS_FIELD_NUMBER: _ClassVar[int]
    WORDSUMMARY_FIELD_NUMBER: _ClassVar[int]
    type: int
    duration: int
    correctionTime: int
    timeBetweenFaults: int
    wordSummary: _containers.RepeatedCompositeFieldContainer[FpgaWordSummary]
    def __init__(self, type: _Optional[int] = ..., duration: _Optional[int] = ..., correctionTime: _Optional[int] = ..., timeBetweenFaults: _Optional[int] = ..., wordSummary: _Optional[_Iterable[_Union[FpgaWordSummary, _Mapping]]] = ...) -> None: ...
