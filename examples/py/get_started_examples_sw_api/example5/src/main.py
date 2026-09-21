"""Example 5 - program the device, then compare a clean DSP48 reference against a fault-injection target."""

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

DEFAULT_RANDOM_INJECTIONS = 200
SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

# The two pblocks under test, as named in the XDC. Only the target is ever
# injected into; the clean one is the untouched hardware reference.
PBLOCK_CLEAN = "pblock_dsp_clean"
PBLOCK_TARGET = "pblock_dsp_target"

# The design's a_len/b_len generics. Widen USER1-4 if the design is rebuilt
# with different values.
A_LEN = 16
B_LEN = 16

LOG_PATH = "dsp_target_injection.log"  # None disables the transcript
VERBOSE = False

WORD_BITS = 32

# The design's BSCAN USER registers. USER1 and USER2 each carry one
# instance's whole operand pair, packed as (operand B << A_LEN) | operand A.
PAIR_LEN = A_LEN + B_LEN
USER_CLEAN_OPERANDS = BscanPrimitive(1, PAIR_LEN)
USER_TARGET_OPERANDS = BscanPrimitive(2, PAIR_LEN)
RESULT_LEN = A_LEN + B_LEN
USER_CLEAN_RESULT = BscanPrimitive(3, RESULT_LEN)
USER_TARGET_RESULT = BscanPrimitive(4, RESULT_LEN)

RESULT_MASK = (1 << RESULT_LEN) - 1


# CLI flags: bitstream/EBD/XDC paths, all/essential of the target pblock,
# random[N]/exhaustive mode, accumulative/non-accumulative revert.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Program the device, then compare a clean DSP48 "
                    "reference against a fault-injection target.")
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
        help="Target the whole footprint of the target pblock, not just "
             "its essential bits.")
    area.add_argument(
        "--essential", action="store_true",
        help="Target only the essential bits of the target pblock, from "
             "the EBD (default).")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--random", nargs="?", type=int, const=DEFAULT_RANDOM_INJECTIONS,
        default=DEFAULT_RANDOM_INJECTIONS, metavar="N",
        help=f"Inject N random bits against the target pblock, one "
             f"at a time (default: {DEFAULT_RANDOM_INJECTIONS}; this "
             f"is also the default mode). Whether each is reverted "
             f"before the next depends on --accumulative/"
             f"--non-accumulative.")
    mode.add_argument(
        "--exhaustive", action="store_true",
        help="Sweep every targeted bit of the target pblock once; N "
             "from --random has no effect.")

    accumulation = parser.add_mutually_exclusive_group()
    accumulation.add_argument(
        "--accumulative", action="store_true",
        help="Leave every upset in place; faults accumulate over the run "
             "(default).")
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


# Bits inside the target pblock this run may inject into - its whole
# footprint, or just the essential ones, per --all/--essential.
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


# Interpret a raw bits-wide bit pattern as two's-complement signed.
def to_signed(value: int, bits: int) -> int:
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


# Encode a signed value as its bits-wide two's-complement pattern.
def to_unsigned(value: int, bits: int) -> int:
    return value & ((1 << bits) - 1)


# A random bits-wide two's-complement bit pattern.
def random_operand(bits: int) -> int:
    return random.randint(0, (1 << bits) - 1)


# Pack two raw operand patterns into one USER1/USER2-wide word.
def pack_operands(a_bits: int, b_bits: int) -> int:
    return (b_bits << A_LEN) | a_bits


# Write the same operand pair, packed, into both instances' own registers.
def apply_operands(dev, a_bits: int, b_bits: int) -> None:
    packed = pack_operands(a_bits, b_bits)
    dev.write_bscan(USER_CLEAN_OPERANDS, packed)   # SK-RAFT: clean operand channel
    dev.write_bscan(USER_TARGET_OPERANDS, packed)  # SK-RAFT: target operand channel


# Read a product out of USER3 or USER4.
def read_result(dev, register: BscanPrimitive) -> int:
    return int.from_bytes(dev.read_bscan(register), "big") & RESULT_MASK  # SK-RAFT: read a result register


# The true signed product of two raw operand patterns, encoded the same
# way the DSP's result registers are.
def expected_product(a_bits: int, b_bits: int) -> int:
    product = to_signed(a_bits, A_LEN) * to_signed(b_bits, B_LEN)
    return to_unsigned(product, RESULT_LEN)


# Apply one fresh random operand pair; compare both instances against the
# true product. Returns (clean_wrong, target_wrong, a, b, expected, clean, target).
def check(dev) -> tuple[bool, bool, int, int, int, int, int]:
    a_bits = random_operand(A_LEN)
    b_bits = random_operand(B_LEN)
    expected = expected_product(a_bits, b_bits)
    apply_operands(dev, a_bits, b_bits)
    clean_value = read_result(dev, USER_CLEAN_RESULT)
    target_value = read_result(dev, USER_TARGET_RESULT)

    return (clean_value != expected, target_value != expected,
            to_signed(a_bits, A_LEN), to_signed(b_bits, B_LEN),
            to_signed(expected, RESULT_LEN),
            to_signed(clean_value, RESULT_LEN),
            to_signed(target_value, RESULT_LEN))


# The coordinates a campaign will visit: every site once if exhaustive,
# otherwise `count` random picks (with replacement) from the site list.
def trial_coordinates(sites, exhaustive: bool, count: int):
    if exhaustive:
        yield from sites
    else:
        for _ in range(count):
            yield random.choice(sites)


# Run inject/check[/revert] trials against the target pblock's own site list.
# Returns (trials that left the target wrong, trials run).
def campaign(dev, sites: list[tuple[int, int, int]], area: InjectionArea,
             accumulative: bool, exhaustive: bool, count: int,
             started: float) -> tuple[int, int]:
    coordinates = list(trial_coordinates(sites, exhaustive, count))
    qualifier = "accumulative" if accumulative else "non-accumulative"
    stage(f"Running {len(coordinates)} injections against "
          f"{PBLOCK_TARGET} ({len(sites)} candidate bits, {qualifier})")
    emit("   #  FAR         WORD  BIT  CLEAN  TARGET  ELAPSED")

    wrong_target = 0
    for index, (far, word_index, bit_index) in enumerate(coordinates, start=1):
        dev.inject_at(far, word_index, bit_index, area)  # SK-RAFT: toggle this bit
        (clean_wrong, target_wrong, a, b, expected, clean_value,
         target_value) = check(dev)
        if not accumulative:
            dev.inject_at(far, word_index, bit_index, area)  # toggle back

        emit(f"{index:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{'wrong' if clean_wrong else 'ok':>5}  "
             f"{'wrong' if target_wrong else 'ok':>6}  "
             f"{elapsed_since(started):>7}")
        if clean_wrong or target_wrong:
            emit(f"      a={a}  b={b}  expected={expected}  clean={clean_value}  "
                 f"target={target_value}")

        if target_wrong:
            wrong_target += 1
        if clean_wrong:
            warn(f"trial {index} in {PBLOCK_TARGET}: the clean reference "
                 f"also went wrong; the two instances have independent "
                 f"operand write channels, so this is routing shared "
                 f"between the two multipliers' own logic rather than a "
                 f"shared operand feed (CONTAIN_ROUTING is not set)")

    return wrong_target, len(coordinates)


# Connect, program the device, then run the campaign against the target pblock.
def main() -> None:
    args = parse_args()
    essential_only = not args.all
    area = InjectionArea.ESSENTIAL_CRAM if essential_only else InjectionArea.CRAM
    accumulative = not args.non_accumulative
    mode = "exhaustive" if args.exhaustive else f"random ({args.random})"
    scope = "essential bits of" if essential_only else "the whole footprint of"
    qualifier = "accumulative" if accumulative else "non-accumulative"

    configure(verbose=VERBOSE, warning_noun="cross-talk hits",
              warning_hint="see the injection log for the detail")
    open_log(LOG_PATH)
    stage(f"Example 5: program the device, then {mode} injection into "
          f"{scope} {PBLOCK_TARGET} ({qualifier}).")

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

                find_pblock(dev, PBLOCK_CLEAN)
                stage(f"{PBLOCK_CLEAN} is never targeted; it is the "
                      f"untouched hardware reference")

                clean_wrong, target_wrong = check(dev)[:2]
                if clean_wrong or target_wrong:
                    raise SkraftError(
                        "one or both DSP instances are wrong right after "
                        "programming: check the USER register ids and "
                        "widths")
                stage("Both DSP instances agree with the true signed "
                      "product before any injection")

                sites = target_bits(dev, PBLOCK_TARGET, essential_only)
                if not sites:
                    stage("Nothing to inject: check that the XDC and the "
                          "EBD belong to the programmed bitstream.")
                    return

                wrong_target, total = campaign(dev, sites, area, accumulative,
                                               args.exhaustive, args.random,
                                               started)

                stage(f"Re-programming {DEVICE} as a final safety net")
                dev.program()

                stage(f"{wrong_target} of {total} trial(s) left the "
                      f"targeted DSP instance wrong against the true "
                      f"signed product")
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
