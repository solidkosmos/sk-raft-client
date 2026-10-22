# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example 5: BRAM readback and writeback. What a BRAM with the built-in ECC and no
output register outputs when SK-RAFT injects into its content.

The design has one RAMB36 (512 x 72: 64 data bits, 8 ECC bits) with the
built-in ECC encoder and decoder, and no output register. The read port
is always enabled. USER3 reads the BRAM outputs directly. Refer to
README.md for the register map.

Stage 1: fill the BRAM, select word 0, read. The word is correct.
Stage 2: stop the clock, read. The word is still correct.
Stage 3: inject into word 0, bit 0 (the clock is still stopped), read.
         The output is a wrong word.
Stage 4: start the clock, read. The word has bit 0 flipped, and SBITERR
         is 0.
"""

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BFD452A"

# BOARD is the board of your target device: "basys3" or "zedboard". The
# script reads the design files from
# hw/design_examples/<BOARD>/bram_readback_writeback_top/. Build them with
# create_project.tcl (see README.md). The paths are relative to src/. Run
# the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/bram_readback_writeback_top"

# The bitstream programs the device. The LL file gives the location of
# each BRAM content bit.
LL_FILE = f"{DESIGN_DIR}/bram_readback_writeback_top.ll"
design = Design(
    bit=f"{DESIGN_DIR}/bram_readback_writeback_top.bit",
    ll =LL_FILE,
)

# BSCAN registers: (USER number, width in bits)
USER_CLK_EN = BscanPrimitive(1, 1)
USER_ADDRESS = BscanPrimitive(2, 16)
USER_DATA = BscanPrimitive(3, 80)

# The BRAM has 512 words of 64 data bits.
DEPTH = 512


# The word that the script writes at each address is the address: word 0
# holds 0, word 1 holds 1, and so on.
def pattern(address: int) -> int:
    return address


# Find the location of a BRAM content bit in the LL file, for example
# "BIT0" (data bit 0 of word 0). Return the frame address (FAR), the word
# in the frame and the bit in the word.
def ll_bit(name: str) -> tuple[int, int, int]:
    with open(LL_FILE, encoding="ascii") as file:
        for line in file:
            fields = line.split()
            if fields[:1] == ["Bit"] and f"Ram=B:{name}" in fields:
                offset = int(fields[3])
                return int(fields[2], 16), offset // 32, offset % 32
    raise ValueError(f"Ram=B:{name} is not in {LL_FILE}")


# The table header and the format of each row.
ROW = "{:<34} {:<18}  {:<6}  {:<7}  {}"


def print_header() -> None:
    print(ROW.format("Stage", "Data", "Parity", "SBITERR",
                     "Data bits that differ from word 0"))


# Read the BRAM outputs through USER3 and print one row: the data, the
# ECC parity, SBITERR and the data bits that differ from the written word
# 0.
def read_word_0(dev, label: str) -> None:
    value = int.from_bytes(dev.read_bscan(USER_DATA), "big")
    data = value & (2**64 - 1)
    parity = (value >> 64) & 0xFF
    sbiterr = (value >> 72) & 1
    diff = [i for i in range(64) if ((data ^ pattern(0)) >> i) & 1]
    bits = ", ".join(str(i) for i in diff) if diff else "none"
    print(ROW.format(label, f"{data:#018x}", f"{parity:#04x}", sbiterr,
                     bits))


def main() -> None:
    far, word, bit = ll_bit("BIT0")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"Programmed {SERIAL_NUMBER}")
                print(f"Word 0 is written as {pattern(0):#018x}.")
                print()
                print_header()

                # Stage 1: start the clock, fill the BRAM, select word 0
                dev.write_bscan(USER_CLK_EN, 1)
                for address in range(DEPTH):
                    dev.write_bscan(USER_ADDRESS, address)
                    dev.write_bscan(USER_DATA, pattern(address))
                dev.write_bscan(USER_ADDRESS, 0)
                read_word_0(dev, "1  clock on, BRAM filled")

                # Stage 2: stop the clock
                dev.write_bscan(USER_CLK_EN, 0)
                read_word_0(dev, "2  clock stopped")

                # Stage 3: inject into word 0, bit 0. SK-RAFT reads the
                # content frame, flips the bit and writes the frame back.
                dev.inject_at(far, word, bit, TargetMemory.BRAM)
                read_word_0(dev, "3  bit 0 injected, clock stopped")

                # Stage 4: start the clock. The BRAM reads word 0 again.
                dev.write_bscan(USER_CLK_EN, 1)
                read_word_0(dev, "4  clock on")

                # Program the FPGA again to clear the upset.
                dev.programFPGA(design)
    except SkraftError as e:
        print(f"failed: {e}")


if __name__ == "__main__":
    main()
