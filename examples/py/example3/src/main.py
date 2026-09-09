"""TEST 3 - Targeted injection into essential bits, random or exhaustive.

The EBD file is loaded and the device programmed, then ``dev.essential_frames()``
is used to build the list of essential bit locations. Both injection functions
below drive ``dev.inject_at()`` with those coordinates, so every upset is
guaranteed to land on a bit the design actually uses:

* ``inject_random_essential`` - picks locations at random (with replacement,
  so the same bit can be hit twice).
* ``inject_exhaustive_essential`` - walks every essential bit exactly once.

The mode is chosen interactively at start-up.
"""

from __future__ import annotations

import random

from skraft import InjectionArea
from skraft.datatypes import DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

NUMBER_OF_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM = ServerPath("/home/embeddedcat/Desktop/tester.bit")
EBD = ServerPath("/home/embeddedcat/Desktop/tester.ebd")

WORD_BITS = 32
PROGRESS_EVERY = 100


def essential_bit_locations(dev) -> list[tuple[int, int, int]]:
    """Return every essential bit as an ``(far, word_index, bit_index)`` tuple.

    Built from the EBD-derived frames, so the EBD file must be loaded. On a
    large design this list can hold millions of entries; if that is a problem,
    consume ``iter_essential_bit_locations`` instead and only materialise what
    you need.
    """
    return list(iter_essential_bit_locations(dev))


def iter_essential_bit_locations(dev):
    """Lazily yield ``(far, word_index, bit_index)`` for each essential bit."""
    for frame in dev.essential_frames():
        for word_index, word in enumerate(frame.words):
            value = word.value
            if value == 0:
                continue  # no essential bit in this word
            for bit_index in range(WORD_BITS):
                if (value >> bit_index) & 1:
                    yield frame.far, word_index, bit_index


def inject_random_essential(dev, injections: int) -> int:
    """Inject ``injections`` upsets at randomly chosen essential bits.

    Uses ``essential_frames`` to know where the essential bits are and
    ``inject_at`` to hit them. Returns the number of upsets injected.
    """
    locations = essential_bit_locations(dev)
    if not locations:
        print("No essential bits found - check that the EBD file matches "
              "the bitstream.")
        return 0

    print(f"{len(locations)} essential bits available; "
          f"injecting {injections} at random.")

    for i in range(1, injections + 1):
        far, word_index, bit_index = random.choice(locations)
        report = dev.inject_at(far, word_index, bit_index,
                               InjectionArea.ESSENTIAL_CRAM)

        if i % PROGRESS_EVERY == 0 or i == injections:
            print(f"[{i}/{injections}] FAR={report.far:#010x} "
                  f"WORD_INDEX={report.word_index} "
                  f"BIT_INDEX={report.bit_index}")

    return injections


def inject_exhaustive_essential(dev) -> int:
    """Inject one upset into every essential bit, once.

    Same ``essential_frames`` -> ``inject_at`` path as the random variant, but
    it sweeps the whole set instead of sampling it. Returns the number of
    upsets injected.

    This is cumulative: nothing is corrected between injections, so by the end
    every essential bit of the design has been flipped. Re-program the device
    afterwards before running any other test.
    """
    injected = 0
    for far, word_index, bit_index in iter_essential_bit_locations(dev):
        dev.inject_at(far, word_index, bit_index,
                      InjectionArea.ESSENTIAL_CRAM)
        injected += 1

        if injected % PROGRESS_EVERY == 0:
            print(f"[{injected}] FAR={far:#010x} "
                  f"WORD_INDEX={word_index} BIT_INDEX={bit_index}")

    print(f"Swept {injected} essential bits.")
    return injected


def ask_mode() -> str:
    """Ask for the injection mode until a valid answer is given."""
    while True:
        answer = input("Injection mode - [r]andom or [e]xhaustive? ").strip().lower()
        if answer in ("r", "random"):
            return "random"
        if answer in ("e", "exhaustive"):
            return "exhaustive"
        print("Please answer 'r' or 'e'.")


def main() -> None:
    print("TEST 3: essential-bit injection via inject_at.")

    mode = ask_mode()

    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ebd=EBD))
                dev.program()
                print(f"Programmed {DEVICE} with {BITSTREAM}.")

                if mode == "random":
                    injected = inject_random_essential(dev,
                                                       NUMBER_OF_INJECTIONS)
                else:
                    injected = inject_exhaustive_essential(dev)
    except SkraftError as e:
        print(f"TEST 3 failed: {e}")
        return

    print(f"TEST 3 done ({mode}): {injected} upsets injected.")


if __name__ == "__main__":
    main()
