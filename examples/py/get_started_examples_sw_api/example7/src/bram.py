"""One bit flip in the stock BRAM, and what it does to the data.

    USER1   16 bits   stock BRAM, address control   (read/write)
    USER3   64 bits   stock BRAM, data              (read/write)

Every address is written with its own value, so address 7 holds 7. That makes
the check trivial: whatever comes back should equal the address it came from.

The run has two halves. First every address is written and read, which proves
the memory is writable and the BSCAN path is sound; if that fails, nothing is
injected, because a fault means nothing on a memory that was already wrong.
Then one random bit is flipped inside the stock BRAM's pblock and the whole
memory is read again, every address and the full width of every word, so the
difference between the two reads is the fault and nothing else.

The fault is left in place. Re-program the device before running anything
else.
"""

from __future__ import annotations

import random
import time

from skraft import InjectionArea
from skraft.datatypes import BscanPrimitive, DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga


SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

DESIGN = "/home/embeddedcat/Desktop/skraft_examples_designs"
BITSTREAM = ServerPath(f"{DESIGN}/tester.bit")
LL = ServerPath(f"{DESIGN}/tester.ll")
XDC = ServerPath(f"{DESIGN}/tester.xdc")

PBLOCK = "pblock_ecc_bram"

USER_ADDRESS = BscanPrimitive(1, 16)
USER_DATA = BscanPrimitive(2, 64)

DEPTH = 512              # words in the memory
READ_FLAG = 1 << 15      # set in the address register to read, not write

WORD_BITS = 32
BRAM_BLOCK_TYPE = 1      # frames holding BRAM contents
DATA_MASK = (1 << USER_DATA.size_in_bits) - 1


def write_word(dev, address: int) -> None:
    """Write an address with its own value."""
    dev.write_bscan(USER_ADDRESS, address)
    dev.write_bscan(USER_DATA, address)


def read_word(dev, address: int) -> int:
    """Read one word back out of the data register."""
    dev.write_bscan(USER_ADDRESS, address | READ_FLAG)
    return int.from_bytes(dev.read_bscan(USER_DATA), "big") & DATA_MASK


def verify(dev) -> list[tuple[int, int]]:
    """Read every address of the memory and compare the whole 64-bit word.

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


def report(wrong: list[tuple[int, int]]) -> None:
    """Print every address that came back wrong."""
    print(f"{len(wrong)} of {DEPTH} addresses wrong")
    for address, value in wrong:
        print(f"  address {address:>3}  expected {address:#018x}  "
              f"read {value:#018x}  "
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

                for address in range(DEPTH):
                    write_word(dev, address)
                print(f"Wrote {DEPTH} addresses, each with its own value")

                wrong = verify(dev)
                if wrong:
                    report(wrong)
                    print("The memory does not hold what was written; "
                          "not injecting anything.")
                    return
                print(f"All {DEPTH} addresses read back correctly "
                      f"({USER_DATA.size_in_bits} bits each)")

                far, word, bit = flip_random_bit(dev)
                print(f"\nFlipped one bit in {PBLOCK}: "
                      f"FAR={far:#010x} word {word} bit {bit}")

                print(f"Checking all {DEPTH} addresses again")


                wrong = verify(dev)

                # read_word(dev, address)
                report(wrong)
                if not wrong:
                    print("The bit belongs to no address of this memory.")
                print("The fault is left in place; re-program the device "
                      "before running anything else.")
    except SkraftError as e:
        print(f"Failed: {e}")
    except KeyboardInterrupt:
        print("Interrupted")


if __name__ == "__main__":
    main()
