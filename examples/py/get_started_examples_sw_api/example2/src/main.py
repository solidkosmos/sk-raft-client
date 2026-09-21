"""Example 2 - program the device, then inject essential or CRAM upsets."""

import argparse

from skraft import InjectionArea
from skraft.datatypes import DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

DEFAULT_RANDOM_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

# CLI flags: bitstream/EBD paths, all/essential area, random[N]/exhaustive mode, accumulative/non-accumulative revert.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Program the device, then inject essential or CRAM upsets.")
    parser.add_argument(
        "--program", metavar="BITSTREAM_PATH", required=True,
        help="Server-side path to the .bit file to program before "
             "injecting.")
    parser.add_argument(
        "--ebd", metavar="EBD_PATH",
        help="Server-side path to the .ebd file. Required unless --all is "
             "set.")

    area = parser.add_mutually_exclusive_group()
    area.add_argument(
        "--all", action="store_true",
        help="Target the whole of CRAM, not just essential bits.")
    area.add_argument(
        "--essential", action="store_true",
        help="Target only essential bits, from the EBD (default).")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--random", nargs="?", type=int, const=DEFAULT_RANDOM_INJECTIONS,
        default=DEFAULT_RANDOM_INJECTIONS, metavar="N",
        help=f"Inject N random bits, one at a time (default: "
             f"{DEFAULT_RANDOM_INJECTIONS}; this is also the default mode).")
    mode.add_argument(
        "--exhaustive", action="store_true",
        help="Sweep every targeted bit once; N from --random has no effect.")

    accumulation = parser.add_mutually_exclusive_group()
    accumulation.add_argument(
        "--accumulative", action="store_true",
        help="Leave every upset in place; faults accumulate over the run "
             "(default). Random mode only.")
    accumulation.add_argument(
        "--non-accumulative", action="store_true",
        help="Undo each upset before continuing, so nothing accumulates. "
             "Random mode only - exhaustive always leaves every bit "
             "flipped.")

    args = parser.parse_args()
    if not args.all and not args.ebd:
        parser.error("--ebd is required unless --all is set")
    return args


# Flip `injections` random bits of `area` one at a time, reverting each if not accumulative.
def inject_random(dev, area: InjectionArea, injections: int,
                   accumulative: bool) -> None:
    for i in range(1, injections + 1):
        report = dev.inject_random(area)  # SK-RAFT: flip one random bit in `area`

        print(f"----- INJECTION {i}/{injections} -----")
        print(f"FAR:        {report.far:#010x}")
        print(f"WORD_INDEX: {report.word_index}")
        print(f"BIT_INDEX:  {report.bit_index}")

        if not accumulative:
            # SK-RAFT: FpgaBitFlip toggles, so hitting the same bit again reverts it.
            dev.inject_at(report.far, report.word_index, report.bit_index, area)


# Sweep every bit of `area` once; N from --random plays no part here.
# One bulk call, not a loop of independent picks, so it always leaves every
# bit flipped - accumulative/non-accumulative doesn't apply here.
def inject_exhaustive(dev, area: InjectionArea) -> int:
    print("Sweeping every targeted bit once - this can take a while.")
    # SK-RAFT: flips every bit of `area` in one call, returns each location hit.
    reports, injected = dev.inject_exhaustive(area)
    print(f"{injected} bits injected at {len(reports)} locations.")
    return injected


# Connect, program the device, then dispatch to the chosen injection mode.
def main() -> None:
    args = parse_args()
    area = InjectionArea.CRAM if args.all else InjectionArea.ESSENTIAL_CRAM
    accumulative = not args.non_accumulative
    mode = "exhaustive" if args.exhaustive else f"random ({args.random})"
    target = "all of CRAM" if args.all else "essential bits"
    qualifier = "always leaves upsets in place" if args.exhaustive \
        else ("accumulative" if accumulative else "non-accumulative")

    print(f"Example 2: program the device, then {mode} injection into "
          f"{target} ({qualifier}).")
    if args.exhaustive and args.non_accumulative:
        print("Note: --non-accumulative has no effect with --exhaustive.")

    try:
        # SK-RAFT: open the connection, then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                # SK-RAFT: stage the bitstream (and EBD, when targeting essential bits), then program.
                dev.load(DesignFiles(
                    bitstream=ServerPath(args.program),
                    ebd=ServerPath(args.ebd) if args.ebd else None))
                dev.program()
                print(f"Programmed {DEVICE} with {args.program}.")

                if args.exhaustive:
                    injected = inject_exhaustive(dev, area)
                else:
                    injected = args.random
                    inject_random(dev, area, args.random, accumulative)
    except SkraftError as e:
        print(f"Example 2 failed: {e}")
        return

    print(f"Example 2 done: {injected} upsets injected ({qualifier}).")

if __name__ == "__main__":
    main()
