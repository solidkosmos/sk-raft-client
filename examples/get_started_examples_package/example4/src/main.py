"""Example 4 - BRAM injection: config bits, content, and ECC recovery.

A single RAMB36 used as 1K x 36. Each 36-bit word holds 24 data bits and
12 check bits: fabric logic around the BRAM protects each data byte with
its own Hamming SEC code (4 check bits per byte). This is not the BRAM's
built-in ECC. See README.md for the register map.

Part 1 injects Essential CRAM upsets into the block-type-0 frames of the
BRAM column the pblock covers. Those frames hold both the BRAM's own
configuration and the column's interconnect, including routing that only
passes through the region (EXCLUDE_PLACEMENT constrains placement, not
routing), so a hit may land in the BRAM, its surrounding logic, or
unrelated logic. Content frames (block type 1) are not targeted. The
stored words are then read back to see whether the memory still works.

Part 2 injects into the content frames themselves (block type 1,
TargetMemory.BRAM), then reads the memory back once with ECC correction
off and once with it on.

Both parts inject until Enter is pressed, so the fault count differs
per run. Upsets accumulate and are never corrected: stop Part 2 early
to see SEC fix single flips, or let it run to see bytes collect more
flips than it can correct.
"""

from __future__ import annotations

import time
import threading

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "210248781184"

# The design used throughout: a single BRAM behind an ECC read path.
# uploadDesignToServer() sends the files, 
# and the server stores them under the same relative path.
design = Design(
    bit="design_files/brams_top.bit",
    ebd="design_files/brams_top.ebd",
    ll ="design_files/brams_top.ll",
    xdc="design_files/board.xdc",
)

PBLOCK_BRAM = "pblock_stock_bram"

# BSCAN registers: (USER number, width in bits)
USER_CLK_EN = BscanPrimitive(1, 1)
USER_ADDRESS = BscanPrimitive(2, 16)
USER_DATA = BscanPrimitive(3, 24)
USER_ECC_READ_EN = BscanPrimitive(4, 1)

# effective bits of the address select
ADDRESS_BITS = 10
# 1024 words
DEPTH = 1 << ADDRESS_BITS

DATA_MASK = (1 << USER_DATA.size_in_bits) - 1

# Watches for the Enter key in the background, so it doesn't block the
# injection loop below. Press Enter any time to end the current part
# early.
stop = threading.Event()

# Start or stop the BRAM's clock through USER1. Frozen immediately
# before every injection below and resumed right after: doing
# it while the clock is running would leave the target circuit 
# mid-activity, and in an actual campaign the circuit could
# be unstable during the injection routine.
# This should be followed as a general guideline for all campaigns.
def enable_clock(dev, enabled: bool) -> None:
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)

# Select one BRAM address through USER2
def select(dev, address: int) -> None:
    dev.write_bscan(USER_ADDRESS, address)


# Write the data word into USER3. write_bscan leaves Shift-DR through
# Exit1-DR -> Update-DR, which the design treats as a write to the
# selected address.
def write_word(dev, value: int) -> None:
    dev.write_bscan(USER_DATA, value)


# Read the data word out of USER3. read_bscan leaves Shift-DR through
# Exit1-DR -> Pause-DR, skipping Update-DR, so the bits shifted in
# during the read are never written to the BRAM.
def read_word(dev) -> int:
    data = dev.read_bscan(USER_DATA)
    return int.from_bytes(data, "big") & DATA_MASK


# Enable or disable ECC correction through USER4. Check bits are
# computed and stored on every write regardless; this only switches
# correction on the read path.
def ecc_read_en(dev, enabled: bool) -> None:
    dev.write_bscan(USER_ECC_READ_EN, 1 if enabled else 0)


# Fill the whole BRAM with a known pattern
def fill_bram(dev) -> None:
    for address in range(DEPTH):
        select(dev, address)
        write_word(dev, (0xA5A5A5 ^ address) & DATA_MASK)
    print(f"Wrote {DEPTH} words into {PBLOCK_BRAM}.")


# Read the whole BRAM and return (address, expected, value) for every
# word that doesn't match the known pattern
def check_bram(dev) -> list[tuple[int, int, int]]:
    corrupt = []
    # select() and read_word() are separate TAP scans, and the second
    # can't start until the first has finished. The gap is many TCK
    # cycles, far longer than the BRAM read latency plus the SEC decode,
    # so USER3 always captures the word at the newly selected address.
    for address in range(DEPTH):
        select(dev, address)
        value = read_word(dev)
        expected = (0xA5A5A5 ^ address) & DATA_MASK
        if value != expected:
            corrupt.append((address, expected, value))
    return corrupt


# Print every wrong word as expected vs. read bits, with the bit
# positions (0 = LSB) that no longer hold the value they were given
def print_wrong_words(words: list[tuple[int, int, int]]) -> None:
    if not words:
        return
    width = USER_DATA.size_in_bits
    print(f"{'ADDR':>6}  {'EXPECTED':<{width}}  {'READ':<{width}}  "
          f"FAULTY BITS")
    faulty_bits = 0
    for address, expected, value in words:
        flipped = [bit for bit in range(width)
                   if (expected ^ value) >> bit & 1]
        faulty_bits += len(flipped)
        print(f"{address:>6}  {expected:0{width}b}  {value:0{width}b}  "
              f"{', '.join(str(bit) for bit in flipped)}")
    print(f"{len(words)} words wrong, {faulty_bits} faulty bits in total.")

    
def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# One line per injected bit: where it landed (FAR, word, bit), then the
# FAR decoded into block type (0 = configuration, 1 = BRAM content),
# top/bottom half (for 7 Series devices), row, column and minor frame.
HIT_HEADER = "     #  FAR       WORD  BIT  BLK  TB  ROW  COL  MINOR"


def print_hit(dev, n: int, report) -> None:
    frame = dev.decode_far(report.far)
    print(f"{n:>6}  {report.far:08x}  {report.word_index:>4}  "
          f"{report.bit_index:>3}  {frame.blocktype!s:>3}  "
          f"{frame.topbottom!s:>2}  {frame.row_address!s:>3}  "
          f"{frame.column_address!s:>3}  {frame.minor_address!s:>5}")



def main() -> None:
    print("Example 4: BRAM injection, config bits, content, and ECC "
          "recovery")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                dev.uploadDesignToServer(design)
                dev.programFPGA()
                print(f"Programmed {DEVICE}.")
                enable_clock(dev, True)

                # Part 1: upset the BRAM column's configuration frames
                # (block type 0), not its content, then re-program so
                # nothing here carries into Part 2.
                print("Exercising the stock BRAM's own configuration "
                      "before touching its contents.")
                # Informational: size of the population inject_random picks from
                # (essential bits in the pblock's block-type-0 frames).
                bram_config_bits = dev.bit_count(TargetMemory.ESSENTIAL_CRAM, 
                                                 pblock=PBLOCK_BRAM)
                print(f"BRAM Config bit count = "
                      f"{bram_config_bits}")  
                time.sleep(1)

                # USER4 resets to 0 (correction off); written anyway to be
                # explicit.
                # Read raw data (no correction) for the round-trip check.
                ecc_read_en(dev, False)
                # Fill the memory array with known words
                print("Writing known words in the BRAM...")
                fill_bram(dev)
                # Check if every word round-trips before 
                # continuing the example
                print("Checking if all words round-trip...")
                wrong = len(check_bram(dev))
                if wrong:
                    print(f"{wrong} of {DEPTH} addresses did not "
                          f"round-trip; not injecting anything.")
                    return
                print(f"All {DEPTH} addresses read back correctly.")

                print("Press enter to stop injecting")
                time.sleep(1)
                #Start injecting until enter is pressed 
                print(f"Injecting Essential CRAM bit upsets into "
                      f"{PBLOCK_BRAM}'s configuration frames (block type 0), "
                      f"none corrected.")
                # Each upset is a readback-modify-writeback of a whole
                # frame; keep the BRAM idle while injecting (see Part 2's
                # guideline).
                print(HIT_HEADER)
                watch_for_enter()
                n = 0
                while True:
                    if stop.is_set():
                        break
                    enable_clock(dev, False)
                    report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                                               pblock=PBLOCK_BRAM)
                    enable_clock(dev, True)
                    print_hit(dev, n + 1, report)
                    time.sleep(0.3)
                    n += 1

                print(f"Injected {n} Essential CRAM faults.")
                # Scan the memory to check for corruption count
                errors = len(check_bram(dev))
                # A wrong read-back shows the BRAM or its access path was
                # hit; it can't say which, since the frames also carry
                # interconnect.
                if errors == DEPTH:
                    print(f"All {DEPTH} addresses read back wrong: the BRAM "
                          f"or its access path no longer works.")
                elif errors:
                    print(f"{errors} of {DEPTH} addresses read back wrong.")
                else:
                    print("All words still read back correctly: the upsets "
                          "hit bits this read/write path doesn't depend on.")
                print("Re-programming to clear the config upsets "
                      "before the content campaign.")
                dev.programFPGA()
                enable_clock(dev, True)

                # Reprogramming resets USER4 to 0, so correction is off
                # again. The round-trip check isn't repeated: Part 1's check
                # already showed the BRAM write/read path is stable.

                # BRAM Content: Fill the memory with known words
                print("Writing known words in the BRAM...")
                fill_bram(dev)
                # Informational: size of the population inject_random picks
                # from (every data and check bit of the BRAM's 1K x 36 words).
                # Upsets below accumulate and are never corrected.
                bram_content_bits = dev.bit_count(TargetMemory.BRAM,
                                                  pblock=PBLOCK_BRAM)
                print(f"BRAM Content bit count = {bram_content_bits}")
                
                print("Press enter to stop injecting")
                time.sleep(1)
                print(f"Injecting BRAM Content bit upsets into "
                      f"{PBLOCK_BRAM}, none corrected.")
                print(HIT_HEADER)
                watch_for_enter()
                n = 0
                while True:
                    if stop.is_set():
                        break
                    # Injection guideline: each content upset is a
                    # readback-modify-writeback of a whole block-type-1
                    # frame, and that frame spans bits of several BRAMs in
                    # the column. The server doesn't protect against user
                    # traffic, so keep every BRAM in the targeted frames
                    # idle (no reads or writes) while injecting.
                    enable_clock(dev, False)
                    report = dev.inject_random(TargetMemory.BRAM, 
                                               pblock=PBLOCK_BRAM)
                    enable_clock(dev, True)
                    print_hit(dev, n + 1, report)
                    time.sleep(0.3)
                    n += 1

                print(f"Injected {n} BRAM Content faults.")  
                print("Reading the whole memory with ECC read off.")
                # Scan the memory to check for erroneous words
                err_words = check_bram(dev)
                print(f"ECC off: {len(err_words)} of {DEPTH} addresses wrong.")
                print_wrong_words(err_words)
                print("-" * 80)
                # Enable ECC read
                ecc_read_en(dev, True)
                print("Reading the whole memory again with ECC read "
                      "on.")
                # Scan the memory to check for corrupt words
                corrupt_w_ecc = check_bram(dev)
                print(f"ECC on: {len(corrupt_w_ecc)} of {DEPTH} addresses "
                      f"wrong.")
                print_wrong_words(corrupt_w_ecc)

                # Only corrected data comes back, with no error flag. Flips
                # in check bits never show with ECC off, and a single one is
                # masked with ECC on. SEC can't detect two or more flips in
                # one byte: it may "correct" the wrong bit and add an error
                # instead of removing one.
                wrong_ecc_off = {address for address, _, _ in err_words}
                wrong_ecc_on = {address for address, _, _ in corrupt_w_ecc}
                if not wrong_ecc_on:
                    print("ECC on: every word read back correctly. Single "
                          "flips were corrected; flips in check bits were "
                          "masked.")
                else:
                    print(f"ECC on: {len(wrong_ecc_on)} address(es) still wrong - "
                          f"at least one byte had two or more flips, which "
                          f"SEC can't correct.")
                    new = wrong_ecc_on - wrong_ecc_off
                    if new:
                        print(f"{len(new)} of them read correctly with ECC "
                              f"off: the flips were in check bits and the "
                              f"decoder mis-corrected a data bit.")

                print("The faults are left in place; re-program the "
                      "device before running anything else.")
             
    except SkraftError as e:
        print(f"Example 4 failed: {e}")
    except KeyboardInterrupt:
        print(f"Interrupted.")

    print(f"Example 4 done.")  

if __name__ == "__main__":
    main()
