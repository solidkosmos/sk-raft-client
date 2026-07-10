#   Copyright(C) 2024 SOLIDKOSMOS S.A.
#   All rights reserved. Confidential Information.
#   (retain the full SolidKosmos notice here, as the other modules do)
"""SK-RAFT FPGA control client."""

from .skraft_fpga import FpgaDevice, SkraftFpga
from .datatypes import (
    BscanPrimitive,
    DesignFiles,
    FaultType,
    FpgaFiSession,
    FpgaFiSummary,
    FpgaFrame,
    FpgaInjectionReport,
    FpgaRandomInjectionReport,
    FpgaScrubReport,
    FpgaScrubSummary,
    FpgaScrubWordSummary,
    FpgaWord,
    FpgaFiWordSummary,
    InjectionArea,
    ScrubbingType,
    ServerPath,
)
from .exceptions import (
    BscanError,
    ConnectionFailedError,
    DesignFileError,
    DeviceReservationError,
    FrameAddressError,
    SkraftError,
)

__all__ = [
    "SkraftFpga",
    "FpgaDevice",
    "BscanPrimitive",
    "DesignFiles",
    "FaultType",
    "FpgaFiSession",
    "FpgaFiSummary",
    "FpgaFrame",
    "FpgaInjectionReport",
    "FpgaRandomInjectionReport",
    "FpgaScrubReport",
    "FpgaScrubSummary",
    "FpgaScrubWordSummary",
    "FpgaWord",
    "FpgaFiWordSummary",
    "InjectionArea",
    "ScrubbingType",
    "ServerPath",
    "BscanError",
    "ConnectionFailedError",
    "DesignFileError",
    "DeviceReservationError",
    "FrameAddressError",
    "SkraftError",
]
