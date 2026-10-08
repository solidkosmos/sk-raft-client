# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024-2026 SOLIDKOSMOS S.A.

"""SK-RAFT FPGA control client."""

from .skraft_fpga import FpgaDevice, SkraftFpga
from .datatypes import (
    Bscan,
    BscanPrimitive,
    Design,
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
    ReadbackOption,
    RegisterAddress,
    ScrubbingType,
    TargetMemory,
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
    "Bscan",
    "BscanPrimitive",
    "Design",
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
    "ReadbackOption",
    "RegisterAddress",
    "ScrubbingType",
    "TargetMemory",
    "BscanError",
    "ConnectionFailedError",
    "DesignFileError",
    "DeviceReservationError",
    "FrameAddressError",
    "SkraftError",
]

