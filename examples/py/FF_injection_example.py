# =========================================================
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
#
# Description:
#    Performs fault injection into a design containing a 16 bit Shift Register.
#    Each bit of the Shift Register is connected to one LED on the Basys3 board.
#    Below is the arrangement of Shift Register Bits to LEDs
#           - BIT 15 ---> LED0
#           - BIT 14 ---> LED1
#           - BIT 13 ---> LED2
#           - BIT 12 ---> LED3
#           - BIT 11 ---> LED4
#           - BIT 10 ---> LED5
#           - BIT  9 ---> LED6
#           - BIT  8 ---> LED7
#           - BIT  7 ---> LED8
#           - BIT  6 ---> LED9
#           - BIT  5 ---> LED10
#           - BIT  4 ---> LED11
#           - BIT  3 ---> LED12
#           - BIT  2 ---> LED13
#           - BIT  1 ---> LED14
#           - BIT  0 ---> LED15
#
# Fault Injection Expected Result:
#   The design should start with one LED light. When the clock of the Shift
#   Register is enabled, any lit LED will begin to move from right to left.
#   When a new fault is injected on the BIT 15, the respective LED, LED15,
#   will turn on, then after a freeze time, all the LEDs will start to move
#   in one direction.
#
# Methodology:
#   To inject a fault into a FlipFlop, the following procedure takes place:
#       1. Disable the clock (CLK) that changes the state of the Shift Register's
#          FlipFlops.
#       2. Inject a fault into the CRAM bit corresponding to the BIT15. This
#          info can be found into the .ll file, produced by the Vivado suite.
#       4. The LED0 should turn off/on depending on its previous state.
#       5. Wait for 5 seconds and enable the clock of the Shift Register again.
#       6. If the LED0 turned on after the injection, it will begin traveling
#          from right to left.
# =========================================================

import sys
sys.path.insert(1, '../../api/python')
from fpga import api as client
from fpga import datatypes
import time

def enable_clock(grpc_client: client.SkRaftFpga) -> None:
    """
        enable_clock enables the clock of the Shift Register, allowing the
        FlipFlops to change state.

        @param grpc_client: The gRPC client used to communicate with the target
        FPGA device.
    """
    bscan_user_1 = datatypes.BscanPrimitive(2, 1) # BSCAN USER 1 with 1-bit width. BscanPrimitive(#USER, #WIDTH).
    value = 0x01
    grpc_client.fpga_write_bscan(bscan_user_1, value)

def disable_clock(grpc_client: client.SkRaftFpga) -> None:
    """
        disable_clock disables the clock of the Shift Register, therefore
        freezing the design functionality temporary, in order to inject the
        next fault.

        @param grpc_client: The gRPC client used to communicate with the target
        FPGA device.
    """
    bscan_user_1 = datatypes.BscanPrimitive(2, 1)
    value = 0x00
    grpc_client.fpga_write_bscan(bscan_user_1, value)

if __name__ == "__main__":
    # Set up the SK-RAFT server connection details.
    dut = client.SkRaftFpga("127.0.0.1", 50052)
    
    # Initiate the communication with the SK-RAFT server.
    dut.establish_connection()
    # Try to connect to the desired device, using the desired programmer.
    # In this example device: XC7A35T-1CPG236C & programmer: FT2232H.
    dut.fpga_connect("XC7A35T-1CPG236C", "FT2232H")

    # Configure the bitstream path.
    dut.fpga_set_bit_file_path("/home/embeddedcat/Vivado/Vivado/2023.2/bin/flip_flop_test_basys/flip_flop_test_basys.runs/impl_1/tester.bit")
    # Program the configured device, using the previously declared bitstream.
    dut.fpga_program()

    enable_clock(dut)

    """
        Currupt 10 times FlipFlop[15] of SLICE_X5Y26.
        The respective line from *.ll file:
            - Bit  9797892 0x0040021f   1700 Block=SLICE_X5Y26 Latch=AQ Net=sr_OBUF[15]
                     ^         ^          ^
                   offset    frame       bit
                   from     address     offset
                   CRAM                  from
                   start                current
                                         frame
        Which means:
            - Frame: 0x0040021f
            - Word to inject: 1700 / 32 = floor(53.125)
            - Bit to inject: 1700 % 32 = 4
            
        Details:
            The Shift Register's 15th bit signal is located in FAR: 0x0040021f,
            Word: 53, Bit: 4.
    """
    for fault in range(10):
        """
            Inject a fault into the FAR: 0x0040021f, Word: 53, Bit: 4.
            signature:  fpga_bit_flip(self, far: int, word_index: int,
                                      bit_index: int, is_flip_flop: bool, 
                                      is_lutram: bool, is_bram: bool)
        """
        # Wait for 5 seconds before injecting the next fault.
        time.sleep(1)
        # Disable the clock to freeze the design.
        disable_clock(dut)
        dut.fpga_bit_flip(0x0040021f, 53, 4, True, False, False)
        # Wait for 5 before enabling the clock again.
        time.sleep(1)
        # Enable the design to allow the fault to propagate through the Shift
        # register.
        enable_clock(dut)
    
    # Close the target device.
    dut.fpga_close()
