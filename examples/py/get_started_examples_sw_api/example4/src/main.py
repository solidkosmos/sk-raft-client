"""Example 4 - program the device, then compare simplex vs. TMR adders under bit upsets."""

import argparse
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

DEFAULT_RANDOM_INJECTIONS = 50
SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

# The two pblocks under test, as named in the XDC.
PBLOCK_SIMPLEX = "pblock_sngl_add"
PBLOCK_TMR = "pblock_tmr_add"

# The design's op_len generic. Widens USER1/USER2 and, with the carry bit,
# USER3/USER4 if the design is rebuilt with a different value.
OP_LEN = 4

LOG_PATH = "adder_tmr_injection.log"  # None disables the transcript
VERBOSE = False

WORD_BITS = 32

# The design's BSCAN USER registers. USER1 and USER2 each carry one adder's
# whole operand pair, packed as (operand B << OP_LEN) | operand A.
PAIR_LEN = OP_LEN * 2
USER_SIMPLEX_OPERANDS = BscanPrimitive(1, PAIR_LEN)
USER_TMR_OPERANDS = BscanPrimitive(2, PAIR_LEN)
USER_SIMPLEX_RESULT = BscanPrimitive(3, OP_LEN + 1)
USER_TMR_RESULT = BscanPrimitive(4, OP_LEN + 1)

RESULT_MASK = (1 << (OP_LEN + 1)) - 1
OP_MASK = (1 << OP_LEN) - 1

# How many random operand pairs check() applies per round.
NUM_TEST_VECTORS = 2


# CLI flags: bitstream/EBD/XDC paths, all/essential of each pblock,
# random[N]/exhaustive mode, accumulative/non-accumulative revert.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Program the device, then compare simplex vs. TMR "
                    "adders under single-bit upsets.")
    parser.add_argument(
        "--program", metavar="BITSTREAM_PATH", required=True,
        help="Server-side path to the .bit file to program before "
             "injecting.")
    parser.add_argument(
        "--ebd", metavar="EBD_PATH", required=True,
        help="Server-side path to the .ebd file.")
    parser.add_argument(
        "--xdc", metavar="XDC_PATH", required=True,
        help="Server-side path to the .xdc file declaring both pblocks.")

    area = parser.add_mutually_exclusive_group()
    area.add_argument(
        "--all", action="store_true",
        help="Target the whole footprint of each pblock, not just its "
             "essential bits.")
    area.add_argument(
        "--essential", action="store_true",
        help="Target only the essential bits of each pblock, from the EBD "
             "(default).")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--random", nargs="?", type=int, const=DEFAULT_RANDOM_INJECTIONS,
        default=DEFAULT_RANDOM_INJECTIONS, metavar="N",
        help=f"Run N single-bit trials against each pblock (default: "
             f"{DEFAULT_RANDOM_INJECTIONS}; this is also the default "
             f"mode).")
    mode.add_argument(
        "--exhaustive", action="store_true",
        help="Sweep every targeted bit of each pblock once; N from "
             "--random has no effect.")

    accumulation = parser.add_mutually_exclusive_group()
    accumulation.add_argument(
        "--accumulative", action="store_true",
        help="Leave each upset in place after checking, so faults "
             "accumulate across trials (default).")
    accumulation.add_argument(
        "--non-accumulative", action="store_true",
        help="Undo each upset right after checking, so every trial is "
             "independent.")

    return parser.parse_args()


# Return the named pblock of the loaded XDC.
def find_pblock(dev, name: str):
    for pblock in dev.pblocks():  # SK-RAFT: pblocks declared in the loaded XDC
        if pblock.name == name:
            return pblock
    raise SkraftError(f"{name} is not declared in the XDC")


# Yield the (word_index, bit_index) pairs an occupied area covers.
def area_bits(area):
    for position in range(area.bit_range.start, area.bit_range.end + 1):
        yield position // WORD_BITS, position % WORD_BITS


# Yield (far, word_index, bit_index) for every CRAM bit of a pblock.
def pblock_bits(dev, pblock):
    for clause in pblock.clauses:
        for frame in dev.pblock_by_clause(clause):  # SK-RAFT: clause -> frames + occupied areas
            for area in frame.occupied_area:
                for word, bit in area_bits(area):
                    yield frame.far, word, bit


# The essential bits of the given frames, from the EBD file.
def essential_bits_in(dev, fars: set[int]) -> set[tuple[int, int, int]]:
    bits = set()
    for frame in dev.essential_frames():  # SK-RAFT: EBD-derived essential-bit frames
        if frame.far not in fars:
            continue
        for word_index, word in enumerate(frame.words):
            for bit in range(WORD_BITS):
                if (word.value >> bit) & 1:
                    bits.add((frame.far, word_index, bit))
    return bits


# Bits inside one pblock this run may inject into - its whole footprint, or
# just the essential ones, per --all/--essential. Confined to this pblock alon.
def target_bits(dev, pblock_name: str, essential_only: bool) -> list[tuple[int, int, int]]:
    pblock = find_pblock(dev, pblock_name)
    sites = sorted(set(pblock_bits(dev, pblock)))
    stage(f"{pblock_name}: {len(sites)} CRAM bits in the footprint")

    if not essential_only:
        return sites

    essential = essential_bits_in(dev, {far for far, _, _ in sites})
    sites = [site for site in sites if site in essential]
    stage(f"{pblock_name}: {len(sites)} of them are essential")
    return sites


# Pack two raw operand patterns into one USER1/USER2-wide word.
def pack_operands(a: int, b: int) -> int:
    return (b << OP_LEN) | a


# Write the same operand pair, packed, into both adders' own registers.
def apply_operands(dev, a: int, b: int) -> None:
    packed = pack_operands(a, b)
    dev.write_bscan(USER_SIMPLEX_OPERANDS, packed)  # SK-RAFT: simplex operand channel
    dev.write_bscan(USER_TMR_OPERANDS, packed)       # SK-RAFT: TMR operand channel


# Read a sum, with its carry bit, out of USER3 or USER4.
def read_result(dev, register: BscanPrimitive) -> int:
    return int.from_bytes(dev.read_bscan(register), "big") & RESULT_MASK  # SK-RAFT: read a result register


# Apply NUM_TEST_VECTORS random operand pairs; return (simplex_failures, tmr_failures).
def check(dev) -> tuple[int, int]:
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


# The coordinates a campaign will visit: every site once if exhaustive,
# otherwise `count` random picks (with replacement) from that pblock's sites.
def trial_coordinates(sites, exhaustive: bool, count: int):
    if exhaustive:
        yield from sites
    else:
        for _ in range(count):
            yield random.choice(sites)


# Run inject/check[/revert] trials against one pblock's own site list.
# Returns (trials that left `watching`'s adder wrong, trials run).
def campaign(dev, label: str, pblock_name: str, sites: list[tuple[int, int, int]],
             watching: str, area: InjectionArea, accumulative: bool,
             exhaustive: bool, count: int, started: float) -> tuple[int, int]:
    coordinates = list(trial_coordinates(sites, exhaustive, count))
    stage(f"{label}: running {len(coordinates)} single-bit trials against "
          f"{pblock_name} ({len(sites)} candidate bits), watching the "
          f"{watching} adder")
    emit("   #  FAR         WORD  BIT  SIMPLEX  TMR    ELAPSED")

    wrong_watched = 0
    for index, (far, word_index, bit_index) in enumerate(coordinates, start=1):
        dev.inject_at(far, word_index, bit_index, area)  # SK-RAFT: toggle this bit
        simplex_failures, tmr_failures = check(dev)
        if not accumulative:
            dev.inject_at(far, word_index, bit_index, area)  # toggle back

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

    stage(f"{label}: {wrong_watched} of {len(coordinates)} trial(s) left "
          f"the {watching} adder wrong in {pblock_name}")
    return wrong_watched, len(coordinates)


# Connect, program the device, then run both campaigns, each confined to its own pblock.
def main() -> None:
    args = parse_args()
    essential_only = not args.all
    area = InjectionArea.ESSENTIAL_CRAM if essential_only else InjectionArea.CRAM
    accumulative = not args.non_accumulative
    mode = "exhaustive" if args.exhaustive else f"random ({args.random})"
    scope = "essential bits of" if essential_only else "the whole footprint of"
    qualifier = "accumulative" if accumulative else "non-accumulative"

    configure(verbose=VERBOSE, warning_noun="anomalies",
              warning_hint="see the injection log for the detail")
    open_log(LOG_PATH)
    stage(f"Example 4: program the device, then {mode} injection into "
          f"{scope} each pblock ({qualifier}), simplex vs. TMR.")

    started = time.perf_counter()
    try:
        # SK-RAFT: open the connection, then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                # SK-RAFT: stage the bitstream, EBD and XDC, then program.
                dev.load(DesignFiles(bitstream=ServerPath(args.program),
                                     ebd=ServerPath(args.ebd),
                                     xdc=ServerPath(args.xdc)))
                dev.program()
                stage(f"Programmed {DEVICE} with {args.program}.")

                simplex_failures, tmr_failures = check(dev)
                if simplex_failures or tmr_failures:
                    raise SkraftError(
                        "one or both adders are wrong right after "
                        "programming: check the USER register ids and "
                        "widths")
                stage("Both adders are correct before any injection")

                simplex_sites = target_bits(dev, PBLOCK_SIMPLEX, essential_only)
                wrong_simplex, total_simplex = campaign(
                    dev, "Simplex", PBLOCK_SIMPLEX, simplex_sites, "simplex",
                    area, accumulative, args.exhaustive, args.random, started)

                stage(f"Re-programming to clear {PBLOCK_SIMPLEX} before "
                      f"testing the TMR adder")
                dev.program()

                tmr_sites = target_bits(dev, PBLOCK_TMR, essential_only)
                wrong_tmr, total_tmr = campaign(
                    dev, "TMR", PBLOCK_TMR, tmr_sites, "tmr", area,
                    accumulative, args.exhaustive, args.random, started)

                stage(f"Re-programming {DEVICE} as a final safety net")
                dev.program()

                stage(f"{wrong_simplex} of {total_simplex} trial(s) in "
                      f"{PBLOCK_SIMPLEX} left the simplex adder wrong")
                stage(f"{wrong_tmr} of {total_tmr} trial(s) in {PBLOCK_TMR} "
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
