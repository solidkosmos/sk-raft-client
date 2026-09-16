"""One bit flip in the BRAM, read back with ECC off and then on.

    USER1   16 bits   address, of which the low 10 bits are the address
    USER2   24 bits   data
    USER3    1 bit    ECC read enable

Every address is written with its own value, so address 7 holds 7. That makes
the check trivial: whatever comes back should equal the address it came from.

The run has three parts. First every address is written and read back with
ECC disabled, which proves the memory is writable and the BSCAN path is
sound; if that fails, nothing is injected, because a fault means nothing on a
memory that was already wrong.

Then one random bit is flipped inside the BRAM's pblock, and the whole memory
is read twice: once with ECC read enable off, which shows the damage as it
sits in the cells, and once with it on, which shows what the block's ECC
makes of it. A single-bit fault should appear in the first read and be gone
from the second. That pair of reads is the point of the run.

The fault is left in place. Re-program the device before running anything
else.
"""

from __future__ import annotations

import random

from skraft import InjectionArea
from skraft.datatypes import BscanPrimitive, DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

DESIGN = "/home/embeddedcat/Desktop/skraft_examples_designs/bram"
BITSTREAM = ServerPath(f"{DESIGN}/tester.bit")
LL = ServerPath(f"{DESIGN}/tester.ll")
XDC = ServerPath(f"{DESIGN}/tester.xdc")

PBLOCK = "pblock_stock_bram"

USER_ADDRESS = BscanPrimitive(1, 16)
USER_DATA = BscanPrimitive(2, 24)
USER_ECC_READ = BscanPrimitive(3, 1)

ADDRESS_BITS = 10        # effective bits of the address register
DEPTH = 1 << ADDRESS_BITS
# READ_FLAG = 1 << ADDRESS_BITS   # set in the address register to read

WORD_BITS = 32
BRAM_BLOCK_TYPE = 1      # frames holding BRAM contents
DATA_MASK = (1 << USER_DATA.size_in_bits) - 1


def set_ecc_read(dev, enabled: bool) -> None:
    """Turn the ECC read path on or off through USER3."""
    dev.write_bscan(USER_ECC_READ, 1 if enabled else 0)

def write_word(dev, address: int) -> None:
    """Write an address with its own value."""
    dev.write_bscan(USER_ADDRESS, address)
    dev.write_bscan(USER_DATA, address)


def read_word(dev, address: int) -> int:
    """Read one word back out of the data register."""
    dev.write_bscan(USER_ADDRESS, address) # | READ_FLAG)
    return int.from_bytes(dev.read_bscan(USER_DATA), "big") & DATA_MASK


def verify(dev) -> list[tuple[int, int]]:
    """Read every address of the memory and compare the whole word.

    No address is skipped and no part of a word is ignored, so a flipped bit
    anywhere in the memory is caught. Each entry of the result is
    ``(address, read)``.
    """
    wrong = []
    for address in range(DEPTH):
        value = read_word(dev, address)
        if value != address:
            wrong.append((address, value))
    return wrong


def report(label: str, wrong: list[tuple[int, int]]) -> None:
    """Print every address that came back wrong."""
    print(f"{label}: {len(wrong)} of {DEPTH} addresses wrong")
    for address, value in wrong:
        print(f"  address {address:>4}  expected {address:#08x}  "
              f"read {value:#08x}  "
              f"{bin(address ^ value).count('1')} bit(s) flipped")


def flip_random_bit(dev) -> tuple[int, int, int]:
    """Flip one bit picked at random from inside the pblock.

    ``pblock_by_clause`` gives the frames the pblock covers and the bit range
    it occupies in each; ``decode_far`` keeps the frames holding BRAM
    contents. ``bit_range`` counts bits along the frame, so a position inside
    it divides into a word index and a bit inside that word.
    """
    pblock = next((p for p in dev.pblocks() if p.name == PBLOCK), None)
    if pblock is None:
        raise SkraftError(f"{PBLOCK} is not declared in {XDC}")

    areas = [(frame.far, area.bit_range.start, area.bit_range.end)
             for clause in pblock.clauses
             for frame in dev.pblock_by_clause(clause)
             if dev.decode_far(frame.far).blocktype == BRAM_BLOCK_TYPE
             for area in frame.occupied_area]

    far, first, last = random.choice(areas)
    word, bit = divmod(random.randint(first, last), WORD_BITS)
    dev.inject_at(far, word, bit, InjectionArea.BRAM)
    return far, word, bit


def main() -> None:
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            print(f"Connected, server version {client.version()}")
            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ll=LL, xdc=XDC))
                dev.program()
                print(f"Programmed {DEVICE}")

                set_ecc_read(dev, False)
                for address in range(DEPTH):
                    write_word(dev, address)
                print(f"Wrote {DEPTH} addresses, each with its own value")

                wrong = verify(dev)
                if wrong:
                    report("Before injection", wrong)
                    print("The memory does not hold what was written; "
                          "not injecting anything.")
                    return
                print(f"All {DEPTH} addresses read back correctly "
                      f"({USER_DATA.size_in_bits} bits each)")

                for i in range(100):
                    far, word, bit = flip_random_bit(dev)
                    print(f"\nFlipped one bit in {PBLOCK}: "
                      f"FAR={far:#010x} word {word} bit {bit}")

                print(f"\nChecking all {DEPTH} addresses with ECC read off")
                set_ecc_read(dev, False)
                raw = verify(dev)
                report("ECC off", raw)

                print(f"\nChecking all {DEPTH} addresses with ECC read on")
                set_ecc_read(dev, True)
                corrected = verify(dev)
                report("ECC on", corrected)

                if raw and not corrected:
                    print("\nThe fault is in the cells and the ECC read "
                          "path corrects it.")
                elif raw and corrected:
                    print("\nThe ECC read path did not correct it: more than "
                          "one bit of that word is wrong, or ECC is not "
                          "enabled in the design.")
                elif not raw:
                    print("\nThe bit belongs to no address of this memory.")

                print("The fault is left in place; re-program the device "
                      "before running anything else.")
    except SkraftError as e:
        print(f"Failed: {e}")
    except KeyboardInterrupt:
        print("Interrupted")


if __name__ == "__main__":
    main()
