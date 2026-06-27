#   Copyright(C) 2024 SOLIDKOSMOS S.A.
#   All rights reserved. Confidential Information.
#   (retain the full SolidKosmos notice here, as the other modules do)

"""SK-RAFT FPGA control client."""

from .skraft_fpga import SkraftFpga, FpgaDevice
from .datatypes import (
    ServerPath,
    DesignFiles,
    InjectionArea,
    InjectionType,
    BscanPrimitive,
    FpgaFrame,
    FpgaWord,
    FpgaFiSession,
    FpgaFiSummary,
    FpgaWordSummary,
    FpgaInjectionReport,
    FpgaRandomInjectionReport,
)
from .exceptions import (
    SkraftError,
    ConnectionFailedError,
    DeviceReservationError,
    DesignFileError,
    FrameAddressError,
    BscanError,
)

__all__ = [
    "SkraftFpga", "FpgaDevice",
    "ServerPath", "DesignFiles", "InjectionArea", "InjectionType",
    "BscanPrimitive", "FpgaFrame", "FpgaWord",
    "FpgaFiSession", "FpgaFiSummary", "FpgaWordSummary",
    "FpgaInjectionReport", "FpgaRandomInjectionReport",
    "SkraftError", "ConnectionFailedError", "DeviceReservationError",
    "DesignFileError", "FrameAddressError", "BscanError",
]

