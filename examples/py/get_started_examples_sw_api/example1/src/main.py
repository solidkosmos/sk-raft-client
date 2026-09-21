"""Example 1 - program the device, then inject CRAM upsets."""

import argparse

from skraft import InjectionArea
from skraft.datatypes import DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

DEFAULT_RANDOM_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"


# CLI flags: bitstream path, random[N]/exhaustive mode, accumulative/non-accumulative revert.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Program the device, then inject CRAM upsets.")
    parser.add_argument(
        "--program", metavar="BITSTREAM_PATH", required=True,
        help="Server-side path to the .bit file to program before "
             "injecting.")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--random", nargs="?", type=int, const=DEFAULT_RANDOM_INJECTIONS,
        default=DEFAULT_RANDOM_INJECTIONS, metavar="N",
        help=f"Inject N random CRAM bits, one at a time (default: "
             f"{DEFAULT_RANDOM_INJECTIONS}; this is also the default mode).")
    mode.add_argument(
        "--exhaustive", action="store_true",
        help="Sweep every CRAM bit of the design once; N from --random "
             "has no effect.")

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

    return parser.parse_args()


# Flip `injections` random CRAM bits one at a time, reverting each if not accumulative.
def inject_random_cram(dev, injections: int, accumulative: bool) -> None:
    for i in range(1, injections + 1):
        report = dev.inject_random(InjectionArea.CRAM)  # SK-RAFT: flip one random CRAM bit

        print(f"----- INJECTION {i}/{injections} -----")
        print(f"FAR:        {report.far:#010x}")
        print(f"WORD_INDEX: {report.word_index}")
        print(f"BIT_INDEX:  {report.bit_index}")

        if not accumulative:
            # SK-RAFT: FpgaBitFlip toggles, so hitting the same bit again reverts it.
            dev.inject_at(report.far, report.word_index, report.bit_index,
                          InjectionArea.CRAM)


# Sweep every CRAM bit of the design once; N from --random plays no part here.
# One bulk call, not a loop of independent picks, so it always leaves every
# bit flipped - accumulative/non-accumulative doesn't apply here.
def inject_exhaustive_cram(dev) -> int:
    print("Sweeping every CRAM bit of the design once - this can take a "
          "while.")
    # SK-RAFT: flips every CRAM bit in one call, returns each location hit.
    reports, injected = dev.inject_exhaustive(InjectionArea.CRAM)
    print(f"{injected} bits injected at {len(reports)} locations.")
    return injected


# Connect, program the device, then dispatch to the chosen injection mode.
def main() -> None:
    args = parse_args()
    accumulative = not args.non_accumulative
    mode = "exhaustive" if args.exhaustive else f"random ({args.random})"
    qualifier = "always leaves upsets in place" if args.exhaustive \
        else ("accumulative" if accumulative else "non-accumulative")

    print(f"Example 1: program the device, then {mode} CRAM injection "
          f"({qualifier}).")
    if args.exhaustive and args.non_accumulative:
        print("Note: --non-accumulative has no effect with --exhaustive.")

    try:
        # SK-RAFT: open the connection, then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                # SK-RAFT: stage the bitstream, then program the device with it.
                dev.load(DesignFiles(bitstream=ServerPath(args.program)))
                dev.program()
                print(f"Programmed {DEVICE} with {args.program}.")

                if args.exhaustive:
                    injected = inject_exhaustive_cram(dev)
                else:
                    injected = args.random
                    inject_random_cram(dev, args.random, accumulative)
    except SkraftError as e:
        print(f"Example 1 failed: {e}")
        return

    print(f"Example 1 done: {injected} upsets injected ({qualifier}).")


if __name__ == "__main__":
    main()
