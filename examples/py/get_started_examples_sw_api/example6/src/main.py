"""JTAG/BSCAN-driven signed multiply: a clean DSP48 reference versus a
fault-injection target.

Two identical DSP48 instances, each with its own BSCAN operand-write
channel (USER1/USER2), so an upset can't corrupt both instances' inputs
through a shared path - the same lesson the TMR adder example elsewhere in
this suite found the hard way. See README.md for the register map and
operand packing. ``pblock_dsp_clean`` is never injected into; it exists
purely as an untouched hardware twin.

``pblock_dsp_target`` is resolved to essential bits the same way the rest of
this suite confines a pblock. Separate operand channels close the input
side of any cross-talk, but not the output side: with ``CONTAIN_ROUTING``
unset on both pblocks, the two multipliers' own logic and result routing
can still overlap. Rather than trust the clean instance as ground truth for
that reason, every check recomputes the true signed product from the
operands actually written and compares both instances against that.

Each of the ``REPEATS`` trials is self-contained: one upset at a random
essential bit, one check of both instances against the true product, then
``inject_at`` fires again at the same coordinates to revert it
(``FpgaBitFlip`` toggles, so hitting the same spot twice is a plain revert)
before the next trial starts. Nothing accumulates across trials.

The device is re-programmed once at the end, as a safety net rather than a
necessity.
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

# The two pblocks under test, as named in the XDC. Only the target is ever
# injected into; the clean one is the untouched hardware reference.
PBLOCK_CLEAN = "pblock_dsp_clean"
PBLOCK_TARGET = "pblock_dsp_target"

# The design's a_len/b_len generics. Widen USER1-4 if the design is rebuilt
# with different values.
A_LEN = 16
B_LEN = 16

# How many single-bit inject/check/revert trials to run against
# pblock_dsp_target.
REPEATS = 200

LOG_PATH = "dsp_target_injection.log"  # None disables the transcript
VERBOSE = False

WORD_BITS = 32

# The design's BSCAN USER registers, from the specification above. USER1 and
# USER2 each carry one instance's whole operand pair, packed as
# (operand B << A_LEN) | operand A.
PAIR_LEN = A_LEN + B_LEN
USER_CLEAN_OPERANDS = BscanPrimitive(1, PAIR_LEN)
USER_TARGET_OPERANDS = BscanPrimitive(2, PAIR_LEN)
RESULT_LEN = A_LEN + B_LEN
USER_CLEAN_RESULT = BscanPrimitive(3, RESULT_LEN)
USER_TARGET_RESULT = BscanPrimitive(4, RESULT_LEN)

RESULT_MASK = (1 << RESULT_LEN) - 1


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
    """The essential bits of the target pblock: footprint intersected with
    the design's essential bits, so every upset lands on a bit the targeted
    instance actually depends on."""
    pblock = find_pblock(dev, pblock_name)
    sites = sorted(set(pblock_bits(dev, pblock)))
    stage(f"{pblock_name}: {len(sites)} CRAM bits in the footprint")

    essential = essential_bits_in(dev, {far for far, _, _ in sites})
    sites = [site for site in sites if site in essential]
    stage(f"{pblock_name}: {len(sites)} of them are essential")
    return sites


def to_signed(value: int, bits: int) -> int:
    """Interpret a raw ``bits``-wide bit pattern as two's-complement signed."""
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def to_unsigned(value: int, bits: int) -> int:
    """Encode a signed value as its ``bits``-wide two's-complement pattern."""
    return value & ((1 << bits) - 1)


def random_operand(bits: int) -> int:
    """A random ``bits``-wide two's-complement bit pattern."""
    return random.randint(0, (1 << bits) - 1)


def pack_operands(a_bits: int, b_bits: int) -> int:
    """Pack two raw operand patterns into one USER1/USER2-wide word: bits
    ``A_LEN - 1`` down to ``0`` are operand A, bits ``PAIR_LEN - 1`` down to
    ``A_LEN`` are operand B."""
    return (b_bits << A_LEN) | a_bits


def apply_operands(dev, a_bits: int, b_bits: int) -> None:
    """Write the same operand pair, packed into one word each, into both
    instances' own operand registers."""
    packed = pack_operands(a_bits, b_bits)
    dev.write_bscan(USER_CLEAN_OPERANDS, packed)
    dev.write_bscan(USER_TARGET_OPERANDS, packed)


def read_result(dev, register: BscanPrimitive) -> int:
    """Read a product out of USER3 or USER4."""
    return int.from_bytes(dev.read_bscan(register), "big") & RESULT_MASK


def expected_product(a_bits: int, b_bits: int) -> int:
    """The true signed product of two raw operand patterns, encoded the same
    way the DSP's result registers are."""
    product = to_signed(a_bits, A_LEN) * to_signed(b_bits, B_LEN)
    return to_unsigned(product, RESULT_LEN)


def check(dev) -> tuple[bool, bool, int, int, int, int, int]:
    """Apply one fresh random operand pair and compare both DSP instances
    against the true signed product.

    Returns ``(clean_wrong, target_wrong, a, b, expected, clean_value,
    target_value)``, with the last five all in signed decimal.
    """
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


def campaign(dev, sites: list[tuple[int, int, int]], started: float) -> int:
    """Run ``REPEATS`` independent single-bit trials against
    ``pblock_dsp_target``.

    Each trial injects one upset, checks both instances against the true
    signed product, then injects at the same ``(far, word_index, bit_index)``
    again to flip the bit back before the next trial starts. Returns how
    many trials left the targeted instance wrong.
    """
    stage(f"Running {REPEATS} single-bit inject/check/revert trials "
          f"against {PBLOCK_TARGET} ({len(sites)} essential bits)")
    emit("   #  FAR         WORD  BIT  CLEAN  TARGET  ELAPSED")

    wrong_target = 0
    for index in range(1, REPEATS + 1):
        far, word_index, bit_index = random.choice(sites)

        dev.inject_at(far, word_index, bit_index, InjectionArea.ESSENTIAL_CRAM)
        (clean_wrong, target_wrong, a, b, expected, clean_value,
         target_value) = check(dev)
        dev.inject_at(far, word_index, bit_index, InjectionArea.ESSENTIAL_CRAM)

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

    return wrong_target


def main() -> None:
    configure(verbose=VERBOSE, warning_noun="cross-talk hits",
              warning_hint="see the injection log for the detail")
    open_log(LOG_PATH)
    stage("Example 6: JTAG/BSCAN-driven signed multiply, clean DSP48 reference vs. fault-injection target")
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

                sites = target_bits(dev, PBLOCK_TARGET)
                if not sites:
                    stage("Nothing to inject: check that the XDC and the "
                          "EBD belong to the programmed bitstream.")
                    return

                wrong_target = campaign(dev, sites, started)

                stage(f"Re-programming {DEVICE} as a final safety net")
                dev.program()

                stage(f"{wrong_target} of {REPEATS} trial(s) left the "
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
