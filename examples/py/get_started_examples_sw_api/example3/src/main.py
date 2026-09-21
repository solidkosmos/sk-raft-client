"""Example 3 - program the device, then inject upsets confined to a pblock."""

import argparse
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
)
from skraft import InjectionArea
from skraft.datatypes import DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

DEFAULT_RANDOM_INJECTIONS = 300
SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

WORD_BITS = 32
PAUSE_S = 0.1                      # delay after each upset; 0 for full speed
LOG_PATH = "pblock_injection.log"  # None disables the transcript
VERBOSE = False                    # True also prints the per-clause detail


# CLI flags: bitstream/EBD/XDC paths, pblock name, all/essential of that
# target, random[N]/exhaustive mode, accumulative/non-accumulative revert.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Program the device, then inject upsets confined to a "
                    "pblock.")
    parser.add_argument(
        "--program", metavar="BITSTREAM_PATH", required=True,
        help="Server-side path to the .bit file to program before "
             "injecting.")
    parser.add_argument(
        "--ebd", metavar="EBD_PATH", required=True,
        help="Server-side path to the .ebd file.")
    parser.add_argument(
        "--xdc", metavar="XDC_PATH", required=True,
        help="Server-side path to the .xdc file declaring --target.")
    parser.add_argument(
        "--target", metavar="PBLOCK_NAME", required=True,
        help="Pblock to attack, named exactly as in the XDC.")

    area = parser.add_mutually_exclusive_group()
    area.add_argument(
        "--all", action="store_true",
        help="Target the whole footprint of --target, not just its "
             "essential bits.")
    area.add_argument(
        "--essential", action="store_true",
        help="Target only the essential bits of --target, from the EBD "
             "(default).")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--random", nargs="?", type=int, const=DEFAULT_RANDOM_INJECTIONS,
        default=DEFAULT_RANDOM_INJECTIONS, metavar="N",
        help=f"Inject N random bits inside --target, one at a time "
             f"(default: {DEFAULT_RANDOM_INJECTIONS}; this is also the "
             f"default mode).")
    mode.add_argument(
        "--exhaustive", action="store_true",
        help="Sweep every targeted bit of --target once; N from --random "
             "has no effect.")

    accumulation = parser.add_mutually_exclusive_group()
    accumulation.add_argument(
        "--accumulative", action="store_true",
        help="Leave every upset in place; faults accumulate over the run "
             "(default).")
    accumulation.add_argument(
        "--non-accumulative", action="store_true",
        help="Undo each upset before continuing, so nothing accumulates. "
             "Applies to both modes here.")

    return parser.parse_args()


# Return the named pblock of the loaded XDC.
def find_pblock(dev, name: str):
    available = dev.pblocks()  # SK-RAFT: pblocks declared in the loaded XDC
    stage(f"Pblocks in the XDC: {', '.join(p.name for p in available)}")
    for pblock in available:
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
        frames = dev.pblock_by_clause(clause)  # SK-RAFT: clause -> frames + occupied areas
        detail(f"clause {clause} covers {len(frames)} frames")
        for frame in frames:
            for area in frame.occupied_area:
                for word, bit in area_bits(area):
                    yield frame.far, word, bit


# The essential bits of the given frames, from the EBD file.
def essential_bits(dev, fars: set[int]) -> set[tuple[int, int, int]]:
    bits = set()
    for frame in dev.essential_frames():  # SK-RAFT: EBD-derived essential-bit frames
        if frame.far not in fars:
            continue
        for word_index, word in enumerate(frame.words):
            for bit in range(WORD_BITS):
                if (word.value >> bit) & 1:
                    bits.add((frame.far, word_index, bit))
    return bits


# Bits inside the pblock this run may inject into - its whole footprint, or
# just the essential ones, per --all/--essential of the given target.
def target_bits(dev, pblock, essential_only: bool) -> list[tuple[int, int, int]]:
    sites = sorted(set(pblock_bits(dev, pblock)))
    stage(f"{pblock.name}: {len(sites)} CRAM bits in the footprint")

    if not essential_only:
        return sites

    essential = essential_bits(dev, {far for far, _, _ in sites})
    sites = [site for site in sites if site in essential]
    stage(f"{pblock.name}: {len(sites)} of them are essential")
    return sites


# Flip `injections` random bits inside the pblock, reverting each if not accumulative.
def inject_random(dev, sites, injections: int, area: InjectionArea,
                  accumulative: bool, started: float) -> None:
    emit("   #  FAR         WORD  BIT  ELAPSED")
    for i in range(1, injections + 1):
        far, word_index, bit_index = random.choice(sites)
        dev.inject_at(far, word_index, bit_index, area)  # SK-RAFT: toggle this bit
        emit(f"{i:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{elapsed_since(started):>7}")

        if not accumulative:
            dev.inject_at(far, word_index, bit_index, area)  # toggle back
        if PAUSE_S:
            time.sleep(PAUSE_S)


# Sweep every site inside the pblock once; N from --random plays no part here.
def inject_exhaustive(dev, sites, area: InjectionArea, accumulative: bool,
                      started: float) -> int:
    emit("   #  FAR         WORD  BIT  ELAPSED")
    for i, (far, word_index, bit_index) in enumerate(sites, start=1):
        dev.inject_at(far, word_index, bit_index, area)  # SK-RAFT: toggle this bit
        emit(f"{i:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{elapsed_since(started):>7}")

        if not accumulative:
            dev.inject_at(far, word_index, bit_index, area)  # toggle back
        if PAUSE_S:
            time.sleep(PAUSE_S)
    return len(sites)


# Connect, program the device, then dispatch to the chosen injection mode.
def main() -> None:
    args = parse_args()
    essential_only = not args.all
    area = InjectionArea.ESSENTIAL_CRAM if essential_only else InjectionArea.CRAM
    accumulative = not args.non_accumulative
    mode = "exhaustive" if args.exhaustive else f"random ({args.random})"
    scope = "essential bits of" if essential_only else "the whole footprint of"
    qualifier = "accumulative" if accumulative else "non-accumulative"

    configure(verbose=VERBOSE)
    open_log(LOG_PATH)
    stage(f"Example 3: program the device, then {mode} injection into "
          f"{scope} {args.target} ({qualifier}).")

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

                pblock = find_pblock(dev, args.target)
                sites = target_bits(dev, pblock, essential_only)
                if not sites:
                    stage("Nothing to inject: check that the XDC and EBD "
                          "belong to the programmed bitstream.")
                    return

                if args.exhaustive:
                    injected = inject_exhaustive(dev, sites, area,
                                                 accumulative, started)
                else:
                    injected = args.random
                    inject_random(dev, sites, args.random, area,
                                 accumulative, started)

                if accumulative:
                    stage(f"Re-programming to clear the {injected} upsets")
                    dev.program()
    except SkraftError as e:
        stage(f"Example 3 failed: {e}")
        return
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
        return
    finally:
        close_log()

    stage(f"Example 3 done: {injected} upsets injected ({qualifier}). "
          f"Took {elapsed_since(started)}.")


if __name__ == "__main__":
    main()
