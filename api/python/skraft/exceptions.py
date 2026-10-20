# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024-2026 SOLIDKOSMOS S.A.

"""Typed exception hierarchy for the SK-RAFT client.

All errors that the client raises derive from :class:`SkraftError`. Thus,
callers can catch all of these errors with one ``except``, or handle specific
failures.
"""


class SkraftError(Exception):
    """The base class for all errors that the SK-RAFT client raises."""


class ConnectionFailedError(SkraftError):
    """The connection to the SK-RAFT server failed, or the communication with
    the server stopped during an operation."""


class DeviceReservationError(SkraftError):
    """The reservation of a target FPGA device failed. The device is not
    available through the selected programmer, or another process (for
    example, Vivado) uses the device."""


class DesignFileError(SkraftError):
    """A design file that the requested operation must have is not loaded, or
    the read or upload of a design file failed."""


class FrameAddressError(SkraftError):
    """A frame address (FAR) is out of range or is not valid."""


class BscanError(SkraftError):
    """A boundary-scan (BSCAN) operation failed."""


class XadcError(SkraftError):
    """The read of an XADC sensor failed."""

