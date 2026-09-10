"""Essential-bit injection with a BSCAN adder self-test.

The design under test is an adder reachable through three BSCAN USER
registers:

    USER1    8 bits    operand A    (shifted in)
    USER2    8 bits    operand B    (shifted in)
    USER3   16 bits    result       (shifted out, A + B)

``dev.essential_frames()`` gives the bits the design actually depends on, in
the same ``(far, word, bit)`` coordinates ``dev.inject_at()`` takes. Each
round flips one of them and exercises the adder: a wrong sum means that bit
mattered. The bit is then flipped a second time, which restores it, so every
round starts from a clean design and sees exactly one live fault. Set
``CORRECT`` to False to leave the upsets in place instead, so the faults pile
up and the design degrades as the run goes on.

``MODE`` chooses which bits are used: ``random`` samples ``INJECTIONS`` of
them, ``exhaustive`` sweeps every one, which characterises the design bit by
bit but takes as long as the design has essential bits.

Edit the settings below and run. Requires essential bits in the bitstream
(``BITSTREAM.SEU.ESSENTIALBITS YES``).
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

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM = ServerPath("/home/embeddedcat/Desktop/bscan_tester.bit")
EBD = ServerPath("/home/embeddedcat/Desktop/bscan_tester.ebd")

# "random" samples INJECTIONS essential bits; "exhaustive" upsets every one
# of them, in order.
MODE = "random"

# How many upsets to inject in "random" mode.
INJECTIONS = 1000

# True flips each bit back after its test, so every test sees exactly one
# fault. False leaves the upsets in place and lets them accumulate; the
# device is re-programmed at the end of the run to clear them.
CORRECT = True

# The adder's BSCAN USER registers.
USER_A = BscanPrimitive(1, 8)        # operand A, shifted in
USER_B = BscanPrimitive(2, 8)        # operand B, shifted in
USER_RESULT = BscanPrimitive(3, 16)  # result, shifted out

# The operand pairs checked after each upset: alternating bit patterns, which
# also catch a stuck bit in either operand register, and the upper limit, the
# only pair that exercises the carry out of bit 7.
TEST_VECTORS = ((0x5A, 0xA5), (0xFF, 0xFF))

LOG_PATH = "bscan_adder.log"  # None disables the transcript
VERBOSE = False               # True also prints the per-vector detail

WORD_BITS = 32
RESULT_MASK = (1 << USER_RESULT.size_in_bits) - 1


def essential_bits(dev) -> list[tuple[int, int, int]]:
    """Every essential bit as ``(far, word_index, bit_index)``.

    A set bit in an essential frame marks an essential bit at that position,
    so the frames are read as masks rather than as configuration data.
    """
    stage("Reading the essential frames (EBD)")
    sites = [
        (frame.far, word_index, bit)
        for frame in dev.essential_frames()
        for word_index, word in enumerate(frame.words)
        if word.value
        for bit in range(WORD_BITS)
        if (word.value >> bit) & 1
    ]
    stage(f"{len(sites)} essential bits found")
    return sites

def read_adder(dev, a: int, b: int) -> int:
    """Apply operands ``a`` and ``b`` and return the adder's result.

    The operands are shifted into USER1 and USER2; the result is read from
    USER3, which shifts a dummy value through and leaves the register
    contents untouched.
    """
    dev.write_bscan(USER_A, a)
    dev.write_bscan(USER_B, b)
    return int.from_bytes(dev.read_bscan(USER_RESULT), "big") & RESULT_MASK


def test_adder(dev, context: str) -> int:
    """Run the test vectors and return how many gave a wrong result."""
    failures = 0
    for a, b in TEST_VECTORS:
        expected = (a + b) & RESULT_MASK
        actual = read_adder(dev, a, b)
        if actual == expected:
            detail(f"{context}: A={a:#04x} B={b:#04x} -> {actual:#06x} ok")
        else:
            failures += 1
            warn(f"{context}: A={a:#04x} B={b:#04x} -> expected "
                 f"{expected:#06x}, got {actual:#06x}")
    return failures

def chosen_bits(sites: list[tuple[int, int, int]]
                ) -> list[tuple[int, int, int]]:
    """The bits this run will upset, in the order they will be upset."""
    if MODE == "exhaustive":
        return sites
    return [random.choice(sites) for _ in range(INJECTIONS)]


def campaign(dev, sites: list[tuple[int, int, int]], started: float) -> int:
    """Upset one essential bit at a time, testing the adder after each one.

    Returns how many upsets broke it.
    """
    targets = chosen_bits(sites)
    stage(f"{MODE.capitalize()} injection: {len(targets)} upsets, "
          f"{'corrected after each test' if CORRECT else 'accumulating'}")
    emit("   #  FAR         WORD  BIT  ADDER      ELAPSED")

    broken = 0
    for index, (far, word_index, bit_index) in enumerate(targets, start=1):
        dev.inject_at(far, word_index, bit_index, InjectionArea.ESSENTIAL_CRAM)

        failures = test_adder(dev, f"injection {index}")
        broken += 1 if failures else 0

        if CORRECT:
            # Flipping the same bit again restores it.
            dev.inject_at(far, word_index, bit_index,
                          InjectionArea.ESSENTIAL_CRAM)

        verdict = f"FAIL {failures}/{len(TEST_VECTORS)}" if failures else "ok"
        emit(f"{index:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{verdict:<9}  {elapsed_since(started):>7}")

    stage(f"{broken}/{len(targets)} upsets broke the adder")
    return broken

def main() -> None:
    configure(verbose=VERBOSE, warning_noun="adder errors",
              warning_hint="the ADDER column reports them all")
    open_log(LOG_PATH)
    started = time.perf_counter()
    try:
        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ebd=EBD))
                dev.program()
                stage(f"Programmed {DEVICE}, {dev.essential_cram_bits} "
                      f"essential CRAM bits")

                # A failure here is the USER register ids or widths, not an
                # injected upset.
                if test_adder(dev, "baseline"):
                    stage("The adder is already wrong before any injection: "
                          "check the USER register ids and widths.")
                    return
                stage("Baseline passed")

                campaign(dev, essential_bits(dev), started)

                if not CORRECT:
                    stage("Re-programming to clear the accumulated faults")
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
