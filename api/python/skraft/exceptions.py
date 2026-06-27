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

"""Typed exception hierarchy for the SK-RAFT client.

Every error raised by the client derives from :class:`SkraftError`, so callers
can catch the whole family with one ``except`` or handle specific failures.
"""


class SkraftError(Exception):
    """Base class for every error raised by the SK-RAFT client."""


class ConnectionFailedError(SkraftError):
    """The connection to the SK-RAFT server could not be established, or
    communication with it was broken mid-operation."""


class DeviceReservationError(SkraftError):
    """A target FPGA device could not be reserved (absent through the selected
    programmer, or already in use by another process such as Vivado)."""


class DesignFileError(SkraftError):
    """A design file required by the requested operation was not loaded, or
    could not be read on the server."""


class FrameAddressError(SkraftError):
    """A Frame Address (FAR) was out of bounds or otherwise invalid."""


class BscanError(SkraftError):
    """A boundary-scan (BSCAN) operation failed."""

