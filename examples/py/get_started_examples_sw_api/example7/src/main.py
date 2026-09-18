"""Two campaigns, one design: a flip-flop shift register and a LUTRAM.

See README.md for the register map. USER1 only gates the shift register's
own clock; it has no bearing on the LUTRAM, which USER3/USER4 address
directly regardless of clock state.

Part 1 confines injection, for now, to the bits inside ``pblock_ff_sr_inst``
as declared in the XDC - flip-flop (.LL) based targeting is coming in a
later release; see ``ff_target_bits`` below. ``REPEATS`` trials each: run
the clock for ``RUN_S`` seconds, freeze it, inject one single-bit upset at
a random site, and run the clock for ``RUN_S`` seconds again. Upsets are
never reverted, so later trials build on whatever earlier ones left behind.

Part 2 needs no pblock: ``InjectionArea.LUTRAM`` already confines injection
to the LUTRAM bits the LL file names. A known pattern is written into every
word, ``LUT_INJECTIONS`` random LUTRAM bits are upset back to back, and
only then is the whole array read back and compared.

Neither part corrects what it injects; the device is re-programmed between
the two parts and again at the end.
"""

from __future__ import annotations

import random
import time

from reporting import (
    close_log,
    configure,
    detail,
    elapsed_since,
    emit,
    open_log,
    stage,
    warn,
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

# The pblock around the shift register, as named in the XDC. Confines
# Part 1 only; Part 2 (LUTRAM) needs no pblock.
PBLOCK = "pblock_ff_sr_inst"

# Part 1: flip-flop shift register. REPEATS single-bit-upset trials, each
# running the clock for RUN_S seconds before and after the injection.
REPEATS = 5
RUN_S = 2.0

# Part 2: LUTRAM. LUT_INJECTIONS random LUTRAM bits, injected back to back.
LUT_INJECTIONS = 20

LOG_PATH = "ff_lutram_injection.log"  # None disables the transcript
VERBOSE = False                       # True also prints per-bit/per-word detail

WORD_BITS = 32

# The design's generics, from the specification above.
SR_LEN = 8
LUT_ADDR_BITS = 4     # ceil(log2(10)): the address depth is 10, not 16
LUT_DEPTH = 10
LUT_DATA_LEN = 32

# The design's BSCAN USER registers.
USER_CLK_EN = BscanPrimitive(1, 1)
USER_SR = BscanPrimitive(2, SR_LEN)
USER_LUT_ADDR = BscanPrimitive(3, LUT_ADDR_BITS)
USER_LUT_DATA = BscanPrimitive(4, LUT_DATA_LEN)

SR_MASK = (1 << SR_LEN) - 1
LUT_DATA_MASK = (1 << LUT_DATA_LEN) - 1


# --------------------------------------------------------------------------- #
# Part 1: flip-flop shift register
# --------------------------------------------------------------------------- #
def set_clock(dev, enabled: bool) -> None:
    """Start or stop the shift register's clock through USER1."""
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)


def read_sr(dev) -> int:
    """Read the shift register's bits out of USER2."""
    return int.from_bytes(dev.read_bscan(USER_SR), "big") & SR_MASK


def area_bits(area):
    """Yield the ``(word_index, bit_index)`` pairs an occupied area covers.

    ``bit_range`` counts bits along the frame from its start, so bits 0 to 31
    are word 0, bits 32 to 63 are word 1, and so on.
    """
    for position in range(area.bit_range.start, area.bit_range.end + 1):
        yield position // WORD_BITS, position % WORD_BITS


def pblock_footprint(dev, name: str) -> set[tuple[int, int, int]]:
    """Every bit the named pblock of the XDC occupies."""
    for pblock in dev.pblocks():
        if pblock.name != name:
            continue
        footprint = {
            (frame.far, word, bit)
            for clause in pblock.clauses
            for frame in dev.pblock_by_clause(clause)
            for area in frame.occupied_area
            for word, bit in area_bits(area)
        }
        stage(f"{name}: {len(footprint)} bits in the footprint")
        return footprint
    raise SkraftError(f"{name} is not declared in {XDC}")


# Flip Flop (.LL) based targeting coming in a later release: the LL file's
# flip-flop sweep (dev.inject_exhaustive(InjectionArea.FLIP_FLOP)) would
# narrow this pblock's footprint down to only its true flip-flop bits, at
# the cost of upsetting every flip-flop in the design to report them
# (requiring a re-program before Part 1 could run). Until that lands here,
# confinement is by pblock alone.
def ff_target_bits(dev) -> list[tuple[int, int, int]]:
    """The flip-flop bits that lie inside the shift-register pblock."""
    sites = sorted(pblock_footprint(dev, PBLOCK))
    stage(f"{len(sites)} flip-flop bits are inside {PBLOCK}")
    for site in sites:
        detail(f"FAR={site[0]:#010x} word {site[1]} bit {site[2]}")
    return sites


def ff_campaign(dev, sites: list[tuple[int, int, int]], started: float
                ) -> None:
    """Run, freeze, inject one bit, and run again, ``REPEATS`` times.

    Each trial: let the clock run for ``RUN_S`` seconds, stop it, upset one
    random site, then let it run for ``RUN_S`` seconds more before the next
    trial. Upsets are never reverted, so later trials run against whatever
    earlier ones left in the register.
    """
    stage(f"Part 1: {REPEATS} single-bit upsets, {RUN_S}s of clock either "
          f"side of each freeze")
    emit("   #  FAR         WORD  BIT  BEFORE  AFTER  CHANGED   ELAPSED")

    set_clock(dev, True)
    for index in range(1, REPEATS + 1):
        time.sleep(RUN_S)
        set_clock(dev, False)
        before = read_sr(dev)

        far, word_index, bit_index = random.choice(sites)
        dev.inject_at(far, word_index, bit_index, InjectionArea.FLIP_FLOP)

        after = read_sr(dev)
        changed = before ^ after
        if not changed:
            warn(f"Part 1, injection {index}: FAR={far:#010x} word "
                 f"{word_index} bit {bit_index} left USER2 at {after:#04x}")

        emit(f"{index:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{before:#04x}    {after:#04x}   {changed:#04x}      "
             f"{elapsed_since(started):>7}")

        set_clock(dev, True)
        time.sleep(RUN_S)
        set_clock(dev, False)

    stage(f"Part 1: done after {REPEATS} trials")


# --------------------------------------------------------------------------- #
# Part 2: LUTRAM
# --------------------------------------------------------------------------- #
def select(dev, address: int) -> None:
    """Select one LUTRAM address through USER3."""
    dev.write_bscan(USER_LUT_ADDR, address)


def write_word(dev, address: int, value: int) -> None:
    """Select ``address`` and write its value into USER4."""
    select(dev, address)
    dev.write_bscan(USER_LUT_DATA, value)


def read_word(dev, address: int) -> int:
    """Select ``address`` and read the word back out of USER4."""
    select(dev, address)
    return int.from_bytes(dev.read_bscan(USER_LUT_DATA), "big") & LUT_DATA_MASK


def pattern(address: int) -> int:
    """The word this run expects to find at ``address``.

    Alternating bits, so a single upset anywhere in the word shows up, and a
    different value per address, so a mis-addressed read is visible too.
    """
    return (0xA5A5A5A5 ^ address) & LUT_DATA_MASK


def fill_memory(dev) -> None:
    """Write the pattern into every LUTRAM word.

    Unlike the shift register, the LUTRAM does not depend on any clock, so
    nothing here touches USER1.
    """
    for address in range(LUT_DEPTH):
        write_word(dev, address, pattern(address))
    detail(f"wrote {LUT_DEPTH} words")


def read_memory(dev) -> list[int]:
    """Read every LUTRAM word back through USER4."""
    return [read_word(dev, address) for address in range(LUT_DEPTH)]


def corrupted(state: list[int]) -> list[tuple[int, int, int]]:
    """The words of ``state`` that differ from the pattern.

    Each entry is ``(address, correct_word, erroneous_word)``.
    """
    return [(address, pattern(address), state[address])
            for address in range(LUT_DEPTH)
            if state[address] != pattern(address)]


def lut_campaign(dev) -> None:
    """Upset ``LUT_INJECTIONS`` random LUTRAM bits back to back.

    No reads happen between injections; the whole array is read back and
    compared only once every injection has landed.
    """
    stage(f"Part 2: {LUT_INJECTIONS} random LUTRAM upsets, not corrected")
    for index in range(1, LUT_INJECTIONS + 1):
        upset = dev.inject_random(InjectionArea.LUTRAM)
        detail(f"injection {index}: FAR={upset.far:#010x} word "
               f"{upset.word_index} bit {upset.bit_index} "
               f"{upset.net_name or ''}")

    report_lut(read_memory(dev))


def report_lut(state: list[int]) -> None:
    """List every LUTRAM word that no longer holds the value it was given."""
    bad = corrupted(state)
    stage(f"Part 2: {len(bad)}/{LUT_DEPTH} words are corrupted")
    if not bad:
        return

    emit("  ADDR  CORRECT     ERRONEOUS   DIFFERING BITS")
    for address, correct, erroneous in bad:
        emit(f"  {address:>4}  {correct:#010x}  {erroneous:#010x}  "
             f"{correct ^ erroneous:#010x}")


def main() -> None:
    configure(verbose=VERBOSE, warning_noun="silent upsets",
              warning_hint="see the injection log for the detail")
    open_log(LOG_PATH)
    stage("Example 7: Flip-flop shift register and LUTRAM injection")
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

                stage("--- Part 1: flip-flop shift register ---")
                sites = ff_target_bits(dev)
                if not sites:
                    stage("Nothing to inject in Part 1: no flip-flop of the "
                          "LL file falls inside the pblock. Check that the "
                          "XDC, the LL and the bitstream belong together.")
                    return

                ff_campaign(dev, sites, started)

                stage("Re-programming before Part 2")
                dev.program()

                stage("--- Part 2: LUTRAM ---")
                fill_memory(dev)
                wrong = corrupted(read_memory(dev))
                if wrong:
                    stage("The LUTRAM does not hold what was written; not "
                          "injecting anything. Check USER3/USER4 register "
                          "ids and widths.")
                    return
                stage(f"All {LUT_DEPTH} LUTRAM words read back correctly")

                lut_campaign(dev)

                stage("Both parts leave the device corrupted; re-programming "
                      "as a final safety net")
                dev.program()
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
