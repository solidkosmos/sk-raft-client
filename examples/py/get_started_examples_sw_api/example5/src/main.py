"""JTAG/BSCAN-driven adder: simplex versus TMR, compared bit-flip by bit-flip.

Two independent adders - a plain (``simplex``) adder and one built from
three replicated adders and a majority voter (``TMR``) - each with its own
BSCAN operand-write channel (USER1/USER2), so an upset can't corrupt both
adders' inputs through a shared path. That's a deliberate fix: an earlier,
single-channel version of this test found exactly that failure mode on real
hardware. See README.md for the register map and operand packing.

Each adder sits in its own pblock (``pblock_sngl_add``, ``pblock_tmr_add``),
resolved to essential bits the same way the rest of this suite confines a
pblock. Neither pblock sets ``CONTAIN_ROUTING``, so a bit inside one's
footprint can still belong to logic or routing shared with the other; with
separate operand channels, that overlap can no longer be a shared-input
effect, so when the *other* adder also goes wrong the campaign flags it per
trial rather than treating it as a plain pass/fail.

Two independent campaigns, one per pblock, each run ``REPEATS`` single-bit
trials: inject one upset at a random essential bit, apply a fresh random
operand pair and check both adders, then inject the same
``(far, word_index, bit_index)`` again to revert it (``FpgaBitFlip``
toggles, so hitting the same spot twice is a plain revert) before the next
trial starts. Nothing accumulates across trials or between campaigns.

The device is re-programmed between the two campaigns and once more at the
end, as a safety net rather than a necessity.
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
EBD = ServerPath(f"{DESIGN}/tester.ebd")
XDC = ServerPath(f"{DESIGN}/tester.xdc")

# The two pblocks under test, as named in the XDC.
PBLOCK_SIMPLEX = "pblock_sngl_add"
PBLOCK_TMR = "pblock_tmr_add"

# The design's op_len generic. Widens USER1/USER2 and, with the carry bit,
# USER3/USER4 if the design is rebuilt with a different value.
OP_LEN = 4

# How many single-bit inject/check/revert trials to run against each pblock.
REPEATS = 80

LOG_PATH = "adder_tmr_injection.log"  # None disables the transcript
VERBOSE = False

WORD_BITS = 32

# The design's BSCAN USER registers, from the specification above. USER1
# and USER2 each carry one adder's whole operand pair, packed as
# (operand B << OP_LEN) | operand A.
PAIR_LEN = OP_LEN * 2
USER_SIMPLEX_OPERANDS = BscanPrimitive(1, PAIR_LEN)
USER_TMR_OPERANDS = BscanPrimitive(2, PAIR_LEN)
USER_SIMPLEX_RESULT = BscanPrimitive(3, OP_LEN + 1)
USER_TMR_RESULT = BscanPrimitive(4, OP_LEN + 1)

RESULT_MASK = (1 << (OP_LEN + 1)) - 1
OP_MASK = (1 << OP_LEN) - 1

# How many random operand pairs check() applies per round.
NUM_TEST_VECTORS = 2


def find_pblock(dev, name: str):
    """Return the named pblock of the loaded XDC."""
    for pblock in dev.pblocks():
        if pblock.name == name:
            return pblock
    raise SkraftError(f"{name} is not declared in {XDC}")


def area_bits(area):
    """Yield the ``(word_index, bit_index)`` pairs an occupied area covers.

    ``bit_range`` counts bits along the frame from its start, so bits 0 to
    31 are word 0, bits 32 to 63 are word 1, and so on.
    """
    for position in range(area.bit_range.start, area.bit_range.end + 1):
        yield position // WORD_BITS, position % WORD_BITS


def pblock_bits(dev, pblock):
    """Yield ``(far, word_index, bit_index)`` for every CRAM bit of a pblock."""
    for clause in pblock.clauses:
        for frame in dev.pblock_by_clause(clause):
            for area in frame.occupied_area:
                for word, bit in area_bits(area):
                    yield frame.far, word, bit


def essential_bits_in(dev, fars: set[int]) -> set[tuple[int, int, int]]:
    """The essential bits of the given frames, from the EBD file."""
    bits = set()
    for frame in dev.essential_frames():
        if frame.far not in fars:
            continue
        for word_index, word in enumerate(frame.words):
            for bit in range(WORD_BITS):
                if (word.value >> bit) & 1:
                    bits.add((frame.far, word_index, bit))
    return bits


def target_bits(dev, pblock_name: str) -> list[tuple[int, int, int]]:
    """The essential bits of one adder's pblock: footprint intersected with
    the design's essential bits, so every upset lands on a bit that adder
    actually depends on."""
    pblock = find_pblock(dev, pblock_name)
    sites = sorted(set(pblock_bits(dev, pblock)))
    stage(f"{pblock_name}: {len(sites)} CRAM bits in the footprint")

    essential = essential_bits_in(dev, {far for far, _, _ in sites})
    sites = [site for site in sites if site in essential]
    stage(f"{pblock_name}: {len(sites)} of them are essential")
    return sites


def pack_operands(a: int, b: int) -> int:
    """Pack two raw operand patterns into one USER1/USER2-wide word: bits
    ``OP_LEN - 1`` down to ``0`` are operand A, bits ``PAIR_LEN - 1`` down
    to ``OP_LEN`` are operand B."""
    return (b << OP_LEN) | a


def apply_operands(dev, a: int, b: int) -> None:
    """Write the same operand pair, packed into one word each, into both
    adders' own operand registers."""
    packed = pack_operands(a, b)
    dev.write_bscan(USER_SIMPLEX_OPERANDS, packed)
    dev.write_bscan(USER_TMR_OPERANDS, packed)


def read_result(dev, register: BscanPrimitive) -> int:
    """Read a sum, with its carry bit, out of USER3 or USER4."""
    return int.from_bytes(dev.read_bscan(register), "big") & RESULT_MASK


def check(dev) -> tuple[int, int]:
    """Apply ``NUM_TEST_VECTORS`` random operand pairs and return how many
    each adder got wrong.

    The same operand pair is written to both adders' own channels, so they
    always see identical inputs; the two results are read back separately.
    Returns ``(simplex_failures, tmr_failures)``.
    """
    simplex_failures = 0
    tmr_failures = 0
    for _ in range(NUM_TEST_VECTORS):
        a = random.randint(0, OP_MASK)
        b = random.randint(0, OP_MASK)
        expected = (a + b) & RESULT_MASK
        apply_operands(dev, a, b)
        if read_result(dev, USER_SIMPLEX_RESULT) != expected:
            simplex_failures += 1
        if read_result(dev, USER_TMR_RESULT) != expected:
            tmr_failures += 1
    return simplex_failures, tmr_failures


def campaign(dev, label: str, pblock_name: str,
             sites: list[tuple[int, int, int]], watching: str,
             started: float) -> int:
    """Run ``REPEATS`` independent single-bit trials against ``pblock_name``.

    Each trial injects one upset at a random essential bit, checks both
    adders, then injects at that exact same ``(far, word_index, bit_index)``
    again to flip the bit back before the next trial starts. Returns how
    many trials left the adder named by ``watching`` (``"simplex"`` or
    ``"tmr"``) wrong.
    """
    stage(f"{label}: running {REPEATS} single-bit inject/check/revert "
          f"trials against {pblock_name} ({len(sites)} essential bits), "
          f"watching the {watching} adder")
    emit("   #  FAR         WORD  BIT  SIMPLEX  TMR    ELAPSED")

    wrong_watched = 0
    for index in range(1, REPEATS + 1):
        far, word_index, bit_index = random.choice(sites)

        dev.inject_at(far, word_index, bit_index, InjectionArea.ESSENTIAL_CRAM)
        simplex_failures, tmr_failures = check(dev)
        dev.inject_at(far, word_index, bit_index, InjectionArea.ESSENTIAL_CRAM)

        emit(f"{index:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{simplex_failures}/{NUM_TEST_VECTORS}      "
             f"{tmr_failures}/{NUM_TEST_VECTORS}  "
             f"{elapsed_since(started):>7}")

        own_failures = simplex_failures if watching == "simplex" else tmr_failures
        other_failures = tmr_failures if watching == "simplex" else simplex_failures

        if own_failures:
            wrong_watched += 1
        if other_failures:
            warn(f"trial {index} in {pblock_name}: the other adder also "
                 f"went wrong; the two adders have independent operand "
                 f"write channels, so this is routing shared between the "
                 f"two adders' own logic rather than a shared operand "
                 f"feed (CONTAIN_ROUTING is not set)")

    stage(f"{label}: {wrong_watched} of {REPEATS} trial(s) left the "
          f"{watching} adder wrong in {pblock_name}")
    return wrong_watched


def main() -> None:
    configure(verbose=VERBOSE, warning_noun="anomalies",
              warning_hint="see the injection log for the detail")
    open_log(LOG_PATH)
    stage("Example 5: JTAG/BSCAN-driven adder, simplex vs. TMR, single-bit upsets")
    started = time.perf_counter()
    try:
        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ebd=EBD, xdc=XDC))
                dev.program()
                stage(f"Programmed {DEVICE}")

                simplex_failures, tmr_failures = check(dev)
                if simplex_failures or tmr_failures:
                    raise SkraftError(
                        "one or both adders are wrong right after "
                        "programming: check the USER register ids and "
                        "widths")
                stage("Both adders are correct before any injection")

                simplex_sites = target_bits(dev, PBLOCK_SIMPLEX)
                wrong_simplex = campaign(dev, "Simplex", PBLOCK_SIMPLEX,
                                         simplex_sites, "simplex", started)

                stage(f"Re-programming to clear {PBLOCK_SIMPLEX} before "
                      f"testing the TMR adder")
                dev.program()

                tmr_sites = target_bits(dev, PBLOCK_TMR)
                wrong_tmr = campaign(dev, "TMR", PBLOCK_TMR, tmr_sites,
                                     "tmr", started)

                stage(f"Re-programming {DEVICE} as a final safety net")
                dev.program()

                stage(f"{wrong_simplex} of {REPEATS} trial(s) in "
                      f"{PBLOCK_SIMPLEX} left the simplex adder wrong")
                stage(f"{wrong_tmr} of {REPEATS} trial(s) in {PBLOCK_TMR} "
                      f"left the TMR adder wrong")
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
