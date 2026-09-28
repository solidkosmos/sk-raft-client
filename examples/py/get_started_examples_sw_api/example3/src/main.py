"""Example 3 - two campaigns, one design: a flip-flop shift register and
a LUTRAM.

See README.md for the register map. USER1 gates the clock of both the
shift register and the LUTRAM; USER3/USER4 address the LUTRAM.

Part 1 injects into the flip-flops inside ``pblock_ff_sr_inst``, through
``dev.inject_random(TargetMemory.FF, pblock=PBLOCK_SR)``; ``bit_count``
first confirms the pblock holds any.
Each trial: run the clock for 2 seconds, freeze it, read the shift
register before and after the upset, then resume the clock. Upsets are
never reverted, so later trials build on whatever earlier ones left
behind. Runs until Enter is pressed.

Part 2 confines injection the same way, through
``dev.inject_random(TargetMemory.LUTRAM, pblock=PBLOCK_LUTRAM)``. A known
pattern is written into every word and read back to confirm it
round-tripped, then LUTRAM upsets are injected one at a time, 0.5s apart,
until Enter is pressed, and only then is the whole array read back and
compared.
"""

from __future__ import annotations

import random
import threading
import time

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you are unsure of your target device's serial number
# you can check via the device_list() call 
DEVICE = "210183BFD452A"

# The design used throughout: a flip-flop shift register and a LUTRAM.
# uploadDesignToServer() sends the files, 
# and the server stores them under the same relative path.
design = Design(
    bit="design_files/ff_lut_top.bit",
    ll ="design_files/ff_lut_top.ll",
    xdc="design_files/board.xdc",
)

# The two pblocks under test, as named in the XDC
PBLOCK_SR = "pblock_ff_sr_inst"
PBLOCK_LUTRAM = "pblock_LUTRAM"

# The design's generics.
SR_LEN = 8
# 6 address bits -> 64 LUTRAM words
LUT_ADDR_BITS = 6
LUT_DEPTH = 64
LUT_DATA_LEN = 32

# BSCAN registers: (USER number, width in bits)
USER_CLK_EN = BscanPrimitive(1, 1)
USER_SR = BscanPrimitive(2, SR_LEN)
USER_LUT_ADDRESS = BscanPrimitive(3, LUT_ADDR_BITS)
USER_LUT_DATA = BscanPrimitive(4, LUT_DATA_LEN)

# Mask for BSCAN feeding/reading 
SR_MASK = (1 << SR_LEN) - 1
LUT_DATA_MASK = (1 << LUT_DATA_LEN) - 1

# Watches for the Enter key in the background, so it doesn't block the
# injection loop below. Press Enter any time to end the current part
# early.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# Start or stop the shift register's and the LUTRAM's clock through USER1
def enable_clock(dev, enabled: bool) -> None:
    # SK-RAFT: gate the clock enable
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)


# Read the shift register's bits out of USER2
def read_sr(dev) -> int:
    # SK-RAFT: read and unpack the shift register
    data = dev.read_bscan(USER_SR)
    return int.from_bytes(data, "big") & SR_MASK


# Select one LUTRAM address through USER3
def select(dev, address: int) -> None:
    # SK-RAFT: write the address
    dev.write_bscan(USER_LUT_ADDRESS, address)


# Write the word value into USER4
def write_word(dev, value: int) -> None:
    # SK-RAFT: write the data word
    dev.write_bscan(USER_LUT_DATA, value)


# Read the word back out of USER4
def read_word(dev) -> int:
    # SK-RAFT: read the data word
    data = dev.read_bscan(USER_LUT_DATA)
    return int.from_bytes(data, "big") & LUT_DATA_MASK


def main() -> None:
    print("Example 3: Flip-flop shift register and LUTRAM injection")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                dev.uploadDesignToServer(design)
                dev.programFPGA()
                print(f"Programmed {DEVICE}.")

                # Part 1: flip-flop shift register
                # Check if any FFs exist inside the set Pblock
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
                    # is a readback-modify-writeback of whole frames shared
                    # with neighbouring logic, and the server doesn't guard
                    # against user activity. Freeze the clock and keep the
                    # target idle while injecting, then resume.
                    enable_clock(dev, False)
                    before = read_sr(dev)

                    # SK-RAFT: flip one flip-flop bit
                    report = dev.inject_random(TargetMemory.FF, 
                                               pblock=PBLOCK_SR)

                    after = read_sr(dev)
                    # FAR/word/bit is the flip-flop's location in the LL
                    # file: the net it drives, i.e. the value it holds. How
                    # the server flips it is not shown here.
                    # BEFORE/AFTER show which of the 8 flip-flops changed.
                    # The flipped value is held, and once the clock resumes
                    # it travels down the feedback loop, visible on the
                    # LEDs and over BSCAN.
                    print(f"{n + 1:>6}  {report.far:08x}  "
                          f"{report.word_index:>4}  {report.bit_index:>3}  "
                          f"{before:08b}  {after:08b}")
                    n += 1

                    enable_clock(dev, True)


                print(f"Part 1: done after {n} trials.")

                print("Re-programming before Part 2.")
                dev.programFPGA()

                # Part 2: LUTRAM
                # Reprogramming resets USER1, and the LUTRAM's writes
                # need the gated clock, so enable it before the fill.
                enable_clock(dev, True)
                # Fill the memory array with a known pattern
                for address in range(LUT_DEPTH):
                    # select() and read_word() are separate TAP scans,
                    # and the second can't start until the first has finished.
                    select(dev, address)
                    write_word(dev, (0xA5A5A5A5 ^ address) & LUT_DATA_MASK)
                # Read every word back and check the write was successful
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
                # Freeze the clock (USER1 gates the LUTRAM too) before
                # injecting; see the guideline in Part 1.
                enable_clock(dev, False)

                print("     #  FAR       WORD  BIT")
                watch_for_enter()

                # Start injecting faults until 'Enter' is pressed
                n = 0
                while True:
                    if stop.is_set():
                        break
                    report = dev.inject_random(TargetMemory.LUTRAM, 
                                               pblock=PBLOCK_LUTRAM)
                    print(f"{n + 1:>6}  {report.far:08x}  "
                          f"{report.word_index:>4}  {report.bit_index:>3}")
                    # Pause to control number of injections
                    time.sleep(0.5)
                    n += 1

                print(f"Part 2: {n} upsets injected.")
                # Enable the clock in order to read the LUTRAM's contents
                enable_clock(dev, True)
                # Print the bits of every LUTRAM word, next to the value it
                # was given, and the bits that were corrupted.
                corrupt_words = 0
                corrupt_bits = 0
                print(f"{'ADDR':>6}  {'CORRECT':<{LUT_DATA_LEN}}  "
                      f"{'READ':<{LUT_DATA_LEN}}  CORRUPTED BITS")
                for address in range(LUT_DEPTH):
                    select(dev, address)
                    word = read_word(dev)
                    expected_word = (0xA5A5A5A5 ^ address) & LUT_DATA_MASK
                    # The bit positions (0 = LSB) that no longer hold the
                    # value they were given
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
                dev.programFPGA()
    except SkraftError as e:
        print(f"Example 3 failed: {e}")
    except KeyboardInterrupt:
        print(f"Interrupted.")

    print(f"Example 3 done.")

if __name__ == "__main__":
    main()
 