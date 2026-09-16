"""BRAM injection: a plain block RAM against an ECC-protected one.

The design under test holds two block RAMs of the same size and contents, one
plain and one with the block's built-in ECC enabled:

    USER1    9 bits    stock BRAM, address control   (read/write)
    USER2    9 bits    ECC BRAM, address control     (read/write)
    USER3   64 bits    stock BRAM, data              (read/write)
    USER4   64 bits    ECC BRAM, data                (read/write)

Each memory sits in its own pblock in the XDC. ``dev.pblock_by_clause()``
gives the frames the pblock covers and, for each of them, the word and bit
range it occupies inside that frame. ``dev.decode_far()`` keeps the frames
holding BRAM contents, so each memory ends up with a list of areas that are
its own data and nothing else. An upset is drawn from inside one of those
ranges, never from the rest of the frame.

Each round is the same three steps:

    inject   one random bit in each memory
    check    every address of each memory, separately
    correct  both bits, by flipping them a second time

Correcting each round means every check sees exactly one fault per memory,
which is the case the block's ECC is built for. The stock BRAM reports its
upset. The ECC BRAM does not, because one flipped bit in a 64-bit word is
corrected as the word is read out.

The counts add up over the run, and the summary at the end is the point of
it: the same number of faults in each memory, and only one of them showing
them.
"""

from __future__ import annotations

import random
import time

from reporting import (
    close_log,
    configure,
    elapsed_since,
    emit,
    open_log,
    stage,
)
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

# How many rounds to run. Each round flips a bit in both memories, checks
# every address of both, and flips the bits back.
INJECTIONS = 2

LOG_PATH = "bram_injection.log"  # None disables the transcript
VERBOSE = False

WORD_BITS = 32
BRAM_BLOCK_TYPE = 1  # frames holding BRAM contents


class Memory:
    """One of the two block RAMs: how to reach it, and where it sits."""

    def __init__(self, name: str, address: int, data: int, pblock: str):
        self.name = name
        self.address = BscanPrimitive(address, 16)
        self.data = BscanPrimitive(data, 64)
        self.pblock = pblock
        self.areas: list[tuple[int, int, int]] = []


MEMORIES = (
    Memory("stock BRAM", 1, 3, "pblock_stock_bram"),
    Memory("ECC BRAM", 2, 4, "pblock_ecc_bram"),
)

DEPTH = 512
DATA_MASK = (1 << 64) - 1


def pattern(address: int) -> int:
    """The word both memories should hold at ``address``."""
    return (0xA5A5A5A5A5A5A5A5 ^ address) & DATA_MASK


def fill(dev, memory: Memory) -> None:
    """Write the pattern into every word of one memory."""
    for address in range(DEPTH):
        dev.write_bscan(memory.address, address)
        dev.write_bscan(memory.data, pattern(address))

def read_word(dev, memory: Memory, address: int) -> int:
    """Read the word at ``address`` back out of the data register."""
    dev.write_bscan(memory.address, address | 0x1 << 10)
    return int.from_bytes(dev.read_bscan(memory.data), "big") & DATA_MASK


def pblock_areas(dev, memory: Memory) -> list[tuple[int, int, int]]:
    """The areas of one memory, read from its pblock.

    Each entry is ``(far, first_bit, last_bit)``. ``bit_range`` counts bits
    along the frame from its start, so a position inside the range divides
    into a word index and a bit inside that word, which is what
    ``inject_at`` takes.
    """
    pblock = next((p for p in dev.pblocks() if p.name == memory.pblock), None)
    if pblock is None:
        raise SkraftError(f"{memory.pblock} is not declared in {XDC}")

    areas = [(frame.far, area.bit_range.start, area.bit_range.end)
             for clause in pblock.clauses
             for frame in dev.pblock_by_clause(clause)
             if dev.decode_far(frame.far).blocktype == BRAM_BLOCK_TYPE
             for area in frame.occupied_area]

    bits = sum(last - first + 1 for _, first, last in areas)
    frames = len({far for far, _, _ in areas})
    stage(f"{memory.name}: {bits} bits over {frames} BRAM frames in "
          f"{memory.pblock}")
    return areas


def flip_random_bit(dev, memory: Memory) -> tuple[int, int, int]:
    """Flip one bit picked at random from inside the memory's areas."""
    far, first, last = random.choice(memory.areas)
    word, bit = divmod(random.randint(first, last), WORD_BITS)
    dev.inject_at(far, word, bit, InjectionArea.BRAM)
    return far, word, bit


def check(dev, memory: Memory) -> list[tuple[int, int, int]]:
    """Read every address of one memory and return the words that are wrong.

    Each entry is ``(address, expected, read)``.
    """
    wrong = []
    for address in range(DEPTH):
        value = read_word(dev, memory, address)
        if value != pattern(address):
            wrong.append((address, pattern(address), value))
    return wrong


def campaign(dev, started: float) -> dict[str, int]:
    """Inject, check and correct, ``INJECTIONS`` times over.

    Returns the total number of wrong words each memory reported.
    """
    stage(f"{INJECTIONS} rounds: inject in both memories, check every "
          f"address of both, correct both")
    emit("   #  MEMORY      FAR         WORD  BIT  ERRORS  ELAPSED")

    totals = {memory.name: 0 for memory in MEMORIES}
    for index in range(1, INJECTIONS + 1):
        upsets = {memory.name: flip_random_bit(dev, memory)
                  for memory in MEMORIES}

        for memory in MEMORIES:
            wrong = check(dev, memory)
            totals[memory.name] += len(wrong)

            far, word, bit = upsets[memory.name]
            emit(f"{index:>4}  {memory.name:<10}  {far:#010x}  {word:>4}  "
                 f"{bit:>3}  {len(wrong):>6}  {elapsed_since(started):>7}")
            for address, expected, value in wrong:
                emit(f"        address {address:>3}  "
                     f"expected {expected:#018x}  read {value:#018x}  "
                     f"{bin(expected ^ value).count('1')} bit(s) flipped")

        for memory in MEMORIES:
            # Flipping the same bit again restores it.
            far, word, bit = upsets[memory.name]
            dev.inject_at(far, word, bit, InjectionArea.BRAM)

    return totals


def main() -> None:
    configure(verbose=VERBOSE)
    open_log(LOG_PATH)
    started = time.perf_counter()
    try:
        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ll=LL, xdc=XDC))
                dev.program()
                stage(f"Programmed {DEVICE}")

                for memory in MEMORIES:
                    memory.areas = pblock_areas(dev, memory)
                    fill(dev, memory)
                stage(f"Both memories filled with {DEPTH} words")

                errors = campaign(dev, started)

                stage(f"Summary after {INJECTIONS} upsets in each memory:")
                for memory in MEMORIES:
                    emit(f"  {memory.name:<12} {errors[memory.name]:>4} "
                         f"errors")

                stage("Every upset was corrected, so the device is left as "
                      "it was programmed")
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
