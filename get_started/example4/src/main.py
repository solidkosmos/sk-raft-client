# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example 4: BRAM injection into configuration bits and content, and ECC
recovery.

The design uses a single RAMB36 as a 1K x 36 memory. Each 36-bit word
holds 24 data bits and 12 check bits. Fabric logic around the BRAM
protects each data byte with its own Hamming SEC code (4 check bits for
each byte). This protection is not the built-in ECC of the BRAM. Refer to
README.md for the register map.

Part 1 injects essential CRAM upsets into the configuration frames (block
type 0) of the BRAM column that the pblock covers. These frames hold the
configuration of the BRAM and the interconnect of the column. The
interconnect includes routing that only goes through the region
(EXCLUDE_PLACEMENT constrains placement, not routing). Thus, an upset can
hit the BRAM, the logic around the BRAM, or unrelated logic. Part 1 does
not target the content frames (block type 1).

After the injections, the script reads back the stored words to find if
the memory still operates correctly.

Part 2 injects upsets into the content frames (block type 1,
TargetMemory.BRAM). Then the script reads back the memory two times: one
time with ECC correction off and one time with ECC correction on.

Both parts inject upsets until you press Enter. Thus, the number of
upsets is different for each run. The upsets accumulate, and the script
does not correct them. Stop Part 2 early to see SEC correct single
flipped bits. Or, let Part 2 continue to see bytes that collect more
flipped bits than SEC can correct.
"""

from __future__ import annotations

import time
import threading

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BFD452A"

# The design for both parts: a single BRAM behind an ECC read path.
# The script gives all four files at the start:
#   The bitstream (.bit): to program the device.
#   The EBD file (.ebd): to find which bits are essential.
#   The XDC file (.xdc): to find the pblocks.
#   The LL file (.ll): to find the BRAM/FF/LUTRAM bits that the design uses.
# uploadDesignToServer() sends the files to the server. The client sends
# only the file name of each path, not the directory.
#
# BOARD is the board of your target device: "basys3" or "zedboard", or
# the name of your own board (see hw/README.md). The script reads the
# design files from hw/design_examples/<BOARD>/brams_top/. Extract
# design_examples.zip there, or build the design with create_project.tcl.
# The paths are relative to src/. Run the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/brams_top"

design = Design(
    bit=f"{DESIGN_DIR}/brams_top.bit",
    ebd=f"{DESIGN_DIR}/brams_top.ebd",
    ll =f"{DESIGN_DIR}/brams_top.ll",
    xdc=f"{DESIGN_DIR}/board.xdc",
)

PBLOCK_BRAM = "pblock_stock_bram"

# BSCAN registers: (USER number, width in bits)
USER_CLK_EN = BscanPrimitive(1, 1)
USER_ADDRESS = BscanPrimitive(2, 16)
USER_DATA = BscanPrimitive(3, 24)
USER_ECC_READ_EN = BscanPrimitive(4, 1)

# The design uses only the 10 low bits of the 16-bit USER2 register.
ADDRESS_BITS = 10
# The BRAM has 1024 words.
DEPTH = 1 << ADDRESS_BITS

DATA_MASK = (1 << USER_DATA.size_in_bits) - 1

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop the
# current part early.
stop = threading.Event()

# Start or stop the BRAM clock through USER1. The script stops the clock
# immediately before each injection below and starts it again immediately
# after. If the clock operates during an injection, the target circuit
# is active when the upset occurs. In a real campaign, the circuit can
# be unstable during the injection routine.
# Use this procedure as a general guideline for all campaigns.
def enable_clock(dev, enabled: bool) -> None:
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)

# Select one BRAM address through USER2.
def select(dev, address: int) -> None:
    dev.write_bscan(USER_ADDRESS, address)


# Write the data word into USER3. write_bscan leaves Shift-DR through
# Exit1-DR -> Update-DR. For the design, this TAP path is a write to the
# selected address.
def write_word(dev, value: int) -> None:
    dev.write_bscan(USER_DATA, value)


# Read the data word from USER3. read_bscan leaves Shift-DR through
# Exit1-DR -> Pause-DR and does not go through Update-DR. Thus, the
# design does not write the bits that the read shifts in to the BRAM.
def read_word(dev) -> int:
    data = dev.read_bscan(USER_DATA)
    return int.from_bytes(data, "big") & DATA_MASK


# Start or stop ECC correction through USER4. The design always
# calculates and stores the check bits on each write. USER4 controls
# only the correction on the read path.
def ecc_read_en(dev, enabled: bool) -> None:
    dev.write_bscan(USER_ECC_READ_EN, 1 if enabled else 0)


# Write a known pattern to all words of the BRAM.
def fill_bram(dev) -> None:
    for address in range(DEPTH):
        select(dev, address)
        write_word(dev, (0xA5A5A5 ^ address) & DATA_MASK)
    print(f"Wrote {DEPTH} words into {PBLOCK_BRAM}.")


# Read all words of the BRAM. Return (address, expected, value) for each
# word that is different from the known pattern.
def check_bram(dev) -> list[tuple[int, int, int]]:
    corrupt = []
    # select() and read_word() are separate TAP scans. The second scan
    # cannot start before the first scan is done. The gap between the
    # scans is many TCK cycles. This gap is much longer than the BRAM read
    # latency plus the SEC decode time. Thus, USER3 always captures the
    # word at the new address.
    for address in range(DEPTH):
        select(dev, address)
        value = read_word(dev)
        expected = (0xA5A5A5 ^ address) & DATA_MASK
        if value != expected:
            corrupt.append((address, expected, value))
    return corrupt


# Print each wrong word as the expected bits and the read bits. Also print
# the bit positions (0 = LSB) that changed from the written value.
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


# The script prints one line for each injected bit. The line shows the
# location of the bit (FAR, word, bit). Then the line shows the block type
# from the decoded FAR (0 = configuration, 1 = BRAM content).
HIT_HEADER = "     #  FAR       WORD  BIT  BLK_TYPE"


def print_hit(dev, n: int, report) -> None:
    frame = dev.decode_far(report.far)
    print(f"{n:>6}  {report.far:08x}  {report.word_index:>4}  "
          f"{report.bit_index:>3}  {frame.blocktype!s:>3}  ")



def main() -> int:
    print("Example 4: BRAM injection, config bits, content, and ECC "
          "recovery")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                # Setup the SEED for deterministic behaviour. 
                dev.configure_seed(0)

                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"Programmed {SERIAL_NUMBER}.")
                enable_clock(dev, True)

                # Part 1: inject upsets into the configuration frames
                # (block type 0) of the BRAM column, not into its content.
                # Then program the FPGA again, so no upset from Part 1
                # stays in Part 2.
                print("Exercising the stock BRAM's own configuration "
                      "before touching its contents.")
                # Note: this count is the size of the set that inject_random
                # selects from. The set contains the essential bits in the
                # block type 0 frames of the pblock.
                bram_config_bits = dev.bit_count(TargetMemory.ESSENTIAL_CRAM, 
                                                 pblock=PBLOCK_BRAM)
                print(f"BRAM Config bit count = "
                      f"{bram_config_bits}")  
                time.sleep(1)

                # USER4 resets to 0 (correction off). The script writes 0 to
                # USER4 anyway, so that the code shows the state.
                # Read the raw data (no correction) for the round-trip check.
                ecc_read_en(dev, False)
                # Fill the memory array with known words.
                print("Writing known words in the BRAM...")
                fill_bram(dev)
                # Make sure that each word reads back correctly before the
                # example continues.
                print("Checking if all words round-trip...")
                wrong = len(check_bram(dev))
                if wrong:
                    print(f"{wrong} of {DEPTH} addresses did not "
                          f"round-trip; not injecting anything.")
                    return 1
                print(f"All {DEPTH} addresses read back correctly.")

                print("Press enter to stop injecting")
                time.sleep(1)
                # Inject upsets until you press Enter.
                print(f"Injecting Essential CRAM bit upsets into "
                      f"{PBLOCK_BRAM}'s configuration frames (block type 0), "
                      f"none corrected.")
                # Each upset is a readback-modify-writeback of a full frame.
                # Keep the BRAM idle during the injection (refer to the
                # guideline in Part 2).
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
                # Scan the memory to count the wrong words.
                errors = len(check_bram(dev))
                # A wrong read-back shows that an upset hit the BRAM or its
                # access path. The read-back cannot show which of the two,
                # because the frames also hold interconnect.
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
                dev.programFPGA(design)
                enable_clock(dev, True)

                # When the script programs the FPGA again, USER4 resets to 0.
                # Thus, the correction is off again. The script does not do the
                # round-trip check again. The check in Part 1 showed that the
                # BRAM write/read path is stable.

                # BRAM content: fill the memory with known words.
                print("Writing known words in the BRAM...")
                fill_bram(dev)
                # Note: this count is the size of the set that inject_random
                # selects from. The set contains all data bits and check
                # bits of the BRAM (1K x 36 words).
                # The upsets below accumulate. The script does not correct
                # them.
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
                    # readback-modify-writeback of a full frame of block
                    # type 1. That frame holds bits of more than one BRAM in
                    # the column. The server does not protect against user
                    # traffic. Thus, keep all BRAMs in the target frames
                    # idle (no reads or writes) during the injection.
                    enable_clock(dev, False)
                    report = dev.inject_random(TargetMemory.BRAM, 
                                               pblock=PBLOCK_BRAM)
                    enable_clock(dev, True)
                    print_hit(dev, n + 1, report)
                    time.sleep(0.3)
                    n += 1

                print(f"Injected {n} BRAM Content faults.")  
                print("Reading the whole memory with ECC read off.")
                # Scan the memory to find the wrong words.
                err_words = check_bram(dev)
                print(f"ECC off: {len(err_words)} of {DEPTH} addresses wrong.")
                print_wrong_words(err_words)
                print("-" * 80)
                # Start the ECC correction on the read path.
                ecc_read_en(dev, True)
                print("Reading the whole memory again with ECC read "
                      "on.")
                # Scan the memory to find the wrong words.
                corrupt_w_ecc = check_bram(dev)
                print(f"ECC on: {len(corrupt_w_ecc)} of {DEPTH} addresses "
                      f"wrong.")
                print_wrong_words(corrupt_w_ecc)

                # The read path gives only the corrected data, with no error
                # flag. With ECC off, flipped check bits do not show. With
                # ECC on, SEC masks a single flipped check bit. SEC cannot
                # detect two or more flipped bits in one byte. Then SEC can
                # change a bit that is correct. This adds an error and
                # does not remove one.
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

                print("Re-programming to clear the device.")
                dev.programFPGA(design)
             
    except SkraftError as e:
        print(f"Example 4 failed: {e}")
        return 1
    except KeyboardInterrupt:
        print(f"Interrupted.")
        return 130

    print(f"Example 4 done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
