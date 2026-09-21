"""BRAM injection: write, verify, corrupt, and recover with ECC read.

A single block RAM. Its 24-bit data word is protected at byte level - the
block's ECC covers each of the three bytes on its own, not the word as one
24-bit codeword. See README.md for the register map.

Before touching the memory's contents, the script exercises the BRAM
primitive's own configuration. A block RAM's footprint spans two kinds of
frame: block type 1 holds the content the design initializes it with,
which is what the campaign below injects into; block type 0 holds the
primitive's own configuration (mode, width). ``config_areas()`` gathers the
latter and ``config_campaign()`` injects into them with
``InjectionArea.CRAM`` rather than ``BRAM``, since these are not content
bits, then re-programs immediately so this warm-up phase can't leave
anything for the rest of the run to trip over.

The run itself: every address is written with a pattern derived from itself
and read straight back to prove the memory and BSCAN path are sound, then
``INJECTIONS`` cumulative, uncorrected upsets are drawn from
``pblock_stock_bram``'s content frames, and the whole memory is read back
once with USER3 (ECC read) off and once with it on. A word that comes back
correct with ECC on but not off had exactly one bit wrong; one still wrong
with ECC on had more than one, or an upset that landed outside the memory's
data cells.

The faults are left in place. Re-program the device before running anything
else.
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

SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

DESIGN = "<DESIGN_PATH_ON_SERVER>"  # server-side folder holding this design's tester.* files
BITSTREAM = ServerPath(f"{DESIGN}/tester.bit")
LL = ServerPath(f"{DESIGN}/tester.ll")
XDC = ServerPath(f"{DESIGN}/tester.xdc")

PBLOCK = "pblock_stock_bram"

USER_ADDRESS = BscanPrimitive(1, 16)
USER_DATA = BscanPrimitive(2, 24)
USER_ECC_READ = BscanPrimitive(3, 1)

ADDRESS_BITS = 10                  # effective bits of the address select
DEPTH = 1 << ADDRESS_BITS          # 1024 words

INJECTIONS = 50                    # bit upsets injected, cumulative, uncorrected
CONFIG_INJECTIONS = 50             # same, for the config-bit warm-up phase

LOG_PATH = "bram_ecc_injection.log"  # None disables the transcript
VERBOSE = False

WORD_BITS = 32
BRAM_BLOCK_TYPE = 1                # frames holding BRAM contents
CLB_BLOCK_TYPE = 0                 # frames holding the BRAM's own config
DATA_MASK = (1 << USER_DATA.size_in_bits) - 1


def pattern(address: int) -> int:
    """The word the memory should hold at ``address``."""
    return (0xA5A5A5 ^ address) & DATA_MASK


def set_ecc_read(dev, enabled: bool) -> None:
    """Turn the ECC read path on or off through USER3."""
    dev.write_bscan(USER_ECC_READ, 1 if enabled else 0)


def select(dev, address: int) -> None:
    """Select one address through USER1, ahead of a read or a write."""
    dev.write_bscan(USER_ADDRESS, address)


def write_word(dev, address: int) -> None:
    """Select ``address`` and write its pattern into USER2."""
    select(dev, address)
    dev.write_bscan(USER_DATA, pattern(address))


def read_word(dev, address: int) -> int:
    """Select ``address`` and read the word back out of USER2."""
    select(dev, address)
    return int.from_bytes(dev.read_bscan(USER_DATA), "big") & DATA_MASK


def fill(dev) -> None:
    """Write the pattern into every word of the memory, address by address."""
    for address in range(DEPTH):
        write_word(dev, address)


def verify(dev) -> list[tuple[int, int, int]]:
    """Read every address of the memory and return the words that are wrong.

    Each entry is ``(address, expected, read)``.
    """
    wrong = []
    for address in range(DEPTH):
        value = read_word(dev, address)
        expected = pattern(address)
        if value != expected:
            wrong.append((address, expected, value))
    return wrong


def report(label: str, wrong: list[tuple[int, int, int]]) -> None:
    """Print every address that came back wrong, and what it holds instead."""
    stage(f"{label}: {len(wrong)} of {DEPTH} addresses wrong")
    for address, expected, value in wrong:
        emit(f"  address {address:>4}  expected {expected:#08x}  "
             f"read {value:#08x}  "
             f"{bin(expected ^ value).count('1')} bit(s) flipped")


def config_areas(dev) -> list[tuple[int, int, int]]:
    """The stock BRAM's areas in its own block type 0 frames.

    Block type 1 holds the BRAM's content, which is what
    :func:`pblock_areas` reads; block type 0 holds the general
    CLB/IO/CLK configuration of the primitive itself, such as its mode
    and width. Same pblock, the other block type.
    """
    pblock = next((p for p in dev.pblocks() if p.name == PBLOCK), None)
    if pblock is None:
        raise SkraftError(f"{PBLOCK} is not declared in {XDC}")

    areas = [(frame.far, area.bit_range.start, area.bit_range.end)
             for clause in pblock.clauses
             for frame in dev.pblock_by_clause(clause)
             if dev.decode_far(frame.far).blocktype == CLB_BLOCK_TYPE
             for area in frame.occupied_area]

    bits = sum(last - first + 1 for _, first, last in areas)
    frames = len({far for far, _, _ in areas})
    stage(f"{PBLOCK}: {bits} config bits over {frames} block type "
          f"{CLB_BLOCK_TYPE} frames")
    return areas


def flip_random_config_bit(dev, areas: list[tuple[int, int, int]]
                           ) -> tuple[int, int, int]:
    """Flip one bit picked at random from the stock BRAM's own
    configuration.

    Injected without the BRAM flag — ``InjectionArea.CRAM`` rather
    than ``InjectionArea.BRAM`` — since these are the primitive's own
    configuration bits, not its content.
    """
    far, first, last = random.choice(areas)
    word, bit = divmod(random.randint(first, last), WORD_BITS)
    dev.inject_at(far, word, bit, InjectionArea.CRAM)
    return far, word, bit


def config_campaign(dev, areas: list[tuple[int, int, int]]) -> None:
    """Inject ``CONFIG_INJECTIONS`` upsets into the pblock's own
    configuration, none of them corrected."""
    stage(f"Injecting {CONFIG_INJECTIONS} bit upsets into {PBLOCK}'s "
          f"own configuration (block type {CLB_BLOCK_TYPE}), none "
          f"corrected")
    emit("   #  FAR         WORD  BIT")
    for index in range(1, CONFIG_INJECTIONS + 1):
        far, word, bit = flip_random_config_bit(dev, areas)
        emit(f"{index:>4}  {far:#010x}  {word:>4}  {bit:>3}")


def pblock_areas(dev) -> list[tuple[int, int, int]]:
    """The stock BRAM's areas, read from its pblock.

    Each entry is ``(far, first_bit, last_bit)``. ``bit_range`` counts bits
    along the frame from its start, so a position inside the range divides
    into a word index and a bit inside that word, which is what
    ``inject_at`` takes.
    """
    pblock = next((p for p in dev.pblocks() if p.name == PBLOCK), None)
    if pblock is None:
        raise SkraftError(f"{PBLOCK} is not declared in {XDC}")

    areas = [(frame.far, area.bit_range.start, area.bit_range.end)
             for clause in pblock.clauses
             for frame in dev.pblock_by_clause(clause)
             if dev.decode_far(frame.far).blocktype == BRAM_BLOCK_TYPE
             for area in frame.occupied_area]

    bits = sum(last - first + 1 for _, first, last in areas)
    frames = len({far for far, _, _ in areas})
    stage(f"{PBLOCK}: {bits} bits over {frames} BRAM frames")
    return areas


def flip_random_bit(dev, areas: list[tuple[int, int, int]]
                    ) -> tuple[int, int, int]:
    """Flip one bit picked at random from inside the stock BRAM's areas."""
    far, first, last = random.choice(areas)
    word, bit = divmod(random.randint(first, last), WORD_BITS)
    dev.inject_at(far, word, bit, InjectionArea.BRAM)
    return far, word, bit


def campaign(dev, areas: list[tuple[int, int, int]]) -> None:
    """Inject ``INJECTIONS`` upsets into the pblock, none of them corrected."""
    stage(f"Injecting {INJECTIONS} bit upsets into {PBLOCK}, none corrected")
    emit("   #  FAR         WORD  BIT")
    for index in range(1, INJECTIONS + 1):
        far, word, bit = flip_random_bit(dev, areas)
        emit(f"{index:>4}  {far:#010x}  {word:>4}  {bit:>3}")


def main() -> None:
    configure(verbose=VERBOSE)
    open_log(LOG_PATH)
    stage("Example 7: BRAM injection, config bits, content, and ECC recovery")
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

                stage("Exercising the stock BRAM's own configuration "
                      "before touching its contents")
                config_campaign(dev, config_areas(dev))

                write_word(dev, 0)
                sanity = read_word(dev, 0)
                if sanity == pattern(0):
                    stage(f"Address 0 still round-trips correctly "
                          f"({sanity:#08x}) after the config upsets")
                else:
                    stage(f"Address 0 no longer round-trips after the "
                          f"config upsets: wrote {pattern(0):#08x}, "
                          f"read {sanity:#08x}")

                stage("Re-programming to clear the config upsets "
                      "before the content campaign")
                dev.program()

                set_ecc_read(dev, False)
                fill(dev)
                stage(f"Wrote {DEPTH} words into {PBLOCK}")

                wrong = verify(dev)
                if wrong:
                    report("Before injection", wrong)
                    stage("The memory does not hold what was written; not "
                          "injecting anything.")
                    return
                stage(f"All {DEPTH} addresses read back correctly "
                      f"({USER_DATA.size_in_bits} bits each)")

                areas = pblock_areas(dev)
                campaign(dev, areas)

                stage("Reading the whole memory with ECC read off")
                raw = verify(dev)
                report("ECC off", raw)

                stage("Driving USER3 high to enable the ECC read path")
                set_ecc_read(dev, True)

                stage("Reading the whole memory again with ECC read on")
                corrected = verify(dev)
                report("ECC on", corrected)

                stage(f"Summary: {len(raw)} of {DEPTH} addresses wrong with "
                      f"ECC off, {len(corrected)} still wrong with ECC on")
                if raw and not corrected:
                    stage("Every corrupted word came back clean: single-bit "
                          "faults only, and the ECC read path caught all of "
                          "them.")
                elif corrected:
                    stage(f"{len(corrected)} address(es) stayed wrong: more "
                          f"than one bit flipped in that word.")
                else:
                    stage("None of the upsets landed in a stored word.")

                stage("The faults are left in place; re-program the device "
                      "before running anything else")
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
