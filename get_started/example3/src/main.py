# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example 3: two campaigns on one design, a flip-flop shift register and
a LUTRAM.

Refer to README.md for the register map. USER1 starts and stops the clock
of the shift register and of the LUTRAM. USER3 and USER4 give access to
the LUTRAM (address and data).

Part 1 injects upsets into the flip-flops in ``pblock_ff_sr_inst``, with
``dev.inject_random(TargetMemory.FF, pblock=PBLOCK_SR)``. Before this, the
script uses ``bit_count`` to make sure that the pblock contains
flip-flops.

Each trial runs the clock for 2 s and then stops the clock. The script
reads the shift register before and after the upset. Then the script
starts the clock again. The script does not correct the upsets, so each
trial starts from the state that the earlier trials left. Part 1
continues until you press Enter.

Part 2 limits the injection to a pblock in the same way, with
``dev.inject_random(TargetMemory.LUTRAM, pblock=PBLOCK_LUTRAM)``. The
script writes a known pattern into each word. Then the script reads back
each word to make sure that the pattern is correct. Then the script
injects LUTRAM upsets one at a time, with 0.5 s between them, until you
press Enter. Then the script reads back the full array and compares it
with the pattern.
"""

from __future__ import annotations

import random
import threading
import time

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BA251CA"

# The design for both parts: a flip-flop shift register and a LUTRAM.
# The script gives all three files at the start:
#   The bitstream (.bit): to program the device.
#   The XDC file (.xdc): to find the pblocks.
#   The LL file (.ll): to find the BRAM/FF/LUTRAM bits that the design uses.
# uploadDesignToServer() sends the files to the server. The client sends
# only the file name of each path, not the directory.
#
# BOARD is the board of your target device: "basys3" or "zedboard", or
# the name of your own board (see hw/README.md). The script reads the
# design files from hw/design_examples/<BOARD>/ff_lut_top/. Extract
# design_examples.zip there, or build the design with create_project.tcl.
# The paths are relative to src/. Run the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/ff_lut_top"

design = Design(
    bit=f"{DESIGN_DIR}/ff_lut_top.bit",
    ll =f"{DESIGN_DIR}/ff_lut_top.ll",
    xdc=f"{DESIGN_DIR}/board.xdc",
)

# The two pblocks to test, with the names from the XDC file.
PBLOCK_SR = "pblock_ff_sr_inst"
PBLOCK_LUTRAM = "pblock_LUTRAM"

# The generics of the design. If you build the design again with
# different values, set these constants to the same values.
SR_LEN = 8
# 6 address bits give 64 LUTRAM words.
LUT_ADDR_BITS = 6
LUT_DEPTH = 64
LUT_DATA_LEN = 32

# BSCAN registers: (USER number, width in bits)
USER_CLK_EN = BscanPrimitive(1, 1)
USER_SR = BscanPrimitive(2, SR_LEN)
USER_LUT_ADDRESS = BscanPrimitive(3, LUT_ADDR_BITS)
USER_LUT_DATA = BscanPrimitive(4, LUT_DATA_LEN)

# Masks for the values that the script writes to and reads from BSCAN.
SR_MASK = (1 << SR_LEN) - 1
LUT_DATA_MASK = (1 << LUT_DATA_LEN) - 1

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop the
# current part early.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# Start or stop the clock of the shift register and the LUTRAM through USER1.
def enable_clock(dev, enabled: bool) -> None:
    # SK-RAFT: set the clock enable bit.
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)


# Read the bits of the shift register from USER2.
def read_sr(dev) -> int:
    # SK-RAFT: read the shift register. Then unpack the bits.
    data = dev.read_bscan(USER_SR)
    return int.from_bytes(data, "big") & SR_MASK


# Select one LUTRAM address through USER3.
def select(dev, address: int) -> None:
    # SK-RAFT: write the address.
    dev.write_bscan(USER_LUT_ADDRESS, address)


# Write the word value into USER4.
def write_word(dev, value: int) -> None:
    # SK-RAFT: write the data word.
    dev.write_bscan(USER_LUT_DATA, value)


# Read back the word from USER4.
def read_word(dev) -> int:
    # SK-RAFT: read the data word.
    data = dev.read_bscan(USER_LUT_DATA)
    return int.from_bytes(data, "big") & LUT_DATA_MASK


def main() -> None:
    print("Example 3: Flip-flop shift register and LUTRAM injection")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                # Setup the SEED for deterministic behaviour. 
                dev.configure_seed(0)

                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"Programmed {SERIAL_NUMBER}.")

                # Part 1: flip-flop shift register.
                # Make sure that the selected pblock contains flip-flops.
                bits = dev.bit_count(TargetMemory.FF, pblock=PBLOCK_SR)
                print(f"Part 1: {bits} flip-flop bits inside "
                      f"{PBLOCK_SR}.")
                if bits == 0:
                    print("Nothing to inject in Part 1: no flip-flop of "
                          "the LL file falls inside the pblock. Check "
                          "that the XDC, the LL and the bitstream "
                          "belong together.")
                    return

                print(f"Press Enter to move on.")
                print("     #  FAR       WORD  BIT  BEFORE    AFTER")
                watch_for_enter()

                enable_clock(dev, True)
                n = 0
                while True:
                    if stop.is_set():
                        break

                    time.sleep(2)
                    # Injection guideline (application memory): each upset
                    # is a readback-modify-writeback of full frames. These
                    # frames also hold adjacent logic. The server does
                    # not protect against user activity. Thus, stop the
                    # clock during the injection. This keeps the target idle.
                    # Then start the clock again.
                    enable_clock(dev, False)
                    before = read_sr(dev)

                    # SK-RAFT: flip one flip-flop bit.
                    report = dev.inject_random(TargetMemory.FF,
                                               pblock=PBLOCK_SR)

                    after = read_sr(dev)
                    # FAR/word/bit is the location of the flip-flop in the
                    # LL file. This location is the bit of the net that the
                    # flip-flop drives. This bit is the value that the
                    # flip-flop holds.
                    # This script does not show how the server flips the bit.
                    # BEFORE/AFTER show which of the 8 flip-flops changed.
                    # The flip-flop holds the flipped value. When the clock
                    # starts again, the value moves along the feedback
                    # loop. You can see the value on the LEDs and through
                    # BSCAN.
                    print(f"{n + 1:>6}  {report.far:08x}  "
                          f"{report.word_index:>4}  {report.bit_index:>3}  "
                          f"{before:08b}  {after:08b}")
                    n += 1

                    enable_clock(dev, True)


                print(f"Part 1: done after {n} trials.")

                print("Re-programming before Part 2.")
                dev.programFPGA(design)

                # Part 2: LUTRAM.
                # When the script programs the FPGA again, USER1 resets to
                # 0. The LUTRAM writes operate only when the gated clock
                # runs. Thus, start the clock before the fill.
                enable_clock(dev, True)
                # Fill the memory array with a known pattern.
                for address in range(LUT_DEPTH):
                    # select() and write_word() are separate TAP scans.
                    # The second scan cannot start before the first scan is
                    # done. Thus, no delay is necessary between them.
                    select(dev, address)
                    write_word(dev, (0xA5A5A5A5 ^ address) & LUT_DATA_MASK)
                # Read back each word and make sure that the write was
                # successful.
                for address in range(LUT_DEPTH):
                    select(dev, address)
                    word = read_word(dev)
                    expected_word = (0xA5A5A5A5 ^ address) & LUT_DATA_MASK
                    if word != expected_word:
                        print(f"Part 2: address {address} reads "
                              f"{word:#010x}, expected {expected_word:#010x}; "
                              f"not injecting anything. Check USER3/USER4 "
                              f"register ids and widths.")
                        return
                

                print(f"Part 2: all {LUT_DEPTH} LUTRAM words read back "
                      f"correctly. Injecting random upsets, not "
                      f"corrected - press Enter to move on.")
                bits = dev.bit_count(TargetMemory.LUTRAM, pblock=PBLOCK_LUTRAM)
                print(f"Part 2: {bits} LUTRAM bits inside "
                      f"{PBLOCK_LUTRAM}.")
                # Stop the clock before the injection (USER1 also gates the
                # LUTRAM). Refer to the guideline in Part 1.
                enable_clock(dev, False)

                print("     #  FAR       WORD  BIT")
                watch_for_enter()

                # Inject upsets until you press Enter.
                n = 0
                while True:
                    if stop.is_set():
                        break
                    report = dev.inject_random(TargetMemory.LUTRAM, 
                                               pblock=PBLOCK_LUTRAM)
                    print(f"{n + 1:>6}  {report.far:08x}  "
                          f"{report.word_index:>4}  {report.bit_index:>3}")
                    # Wait 0.5 s to control the number of injections.
                    time.sleep(0.5)
                    n += 1

                print(f"Part 2: {n} upsets injected.")
                # Start the clock to read the contents of the LUTRAM.
                enable_clock(dev, True)
                # Print the bits of each LUTRAM word, the value that the
                # script wrote to the word, and the corrupted bits.
                corrupt_words = 0
                corrupt_bits = 0
                print(f"{'ADDR':>6}  {'CORRECT':<{LUT_DATA_LEN}}  "
                      f"{'READ':<{LUT_DATA_LEN}}  CORRUPTED BITS")
                for address in range(LUT_DEPTH):
                    select(dev, address)
                    word = read_word(dev)
                    expected_word = (0xA5A5A5A5 ^ address) & LUT_DATA_MASK
                    # The bit positions (0 = LSB) that changed from the
                    # written value.
                    flipped = [bit for bit in range(LUT_DATA_LEN)
                               if (word ^ expected_word) >> bit & 1]
                    print(f"{address:>6}  {expected_word:0{LUT_DATA_LEN}b}  "
                          f"{word:0{LUT_DATA_LEN}b}  "
                          f"{', '.join(str(bit) for bit in flipped) or '-'}")
                    if flipped:
                        corrupt_words += 1
                        corrupt_bits += len(flipped)
                print(f"Part 2: {corrupt_words}/{LUT_DEPTH} words are "
                      f"corrupted, {corrupt_bits} bits in total.")

                print("Re-programming to clear the device.")
                dev.programFPGA(design)
    except SkraftError as e:
        print(f"Example 3 failed: {e}")
    except KeyboardInterrupt:
        print(f"Interrupted.")

    print(f"Example 3 done.")

if __name__ == "__main__":
    main()
 
