# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example: readback scrubbing of the configuration memory, in Python.

The script corrects upsets in the configuration memory (CRAM) of the FPGA.
It uses only the readback and the frame write of SK-RAFT. It does not use
the scrubbing of the server (dev.scrub). Each scrub cycle does these steps:

  1. Read back all the frames of the CRAM.
  2. Compare each frame with its golden frame. The golden frames are the
     readback at the start of the script.
  3. Write the golden frame back into each frame that is different.

The script does not check the dummy (pad) frames and the BRAM content
frames, as the SK-RAFT scrubber does.

The script does not upload design files and does not program the FPGA. It
scrubs the design that is in the FPGA. To show the scrubber at work, the
script injects one random upset into the CRAM before each scrub cycle. The
upset stays in the CRAM until the next scrub cycle.
"""

import time
from dataclasses import dataclass
from typing import List

from skraft import (
    FpgaFrame,
    ReadbackOption,
    SkraftError,
    SkraftFpga,
    TargetMemory,
)

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BA251CA"

# The number of scrub cycles.
SCRUB_CYCLES = 10
# The time from the start of one scrub cycle to the start of the next, in
# seconds. If a cycle takes more time, the next cycle starts immediately.
SCRUB_PERIOD_S = 5.0

# If True, inject one random upset into the CRAM before each scrub cycle.
# Set it to False to scrub only.
INJECT_UPSETS = True
# The seed of the random injections. The same seed gives the same upsets.
SEED = 42

# The block type of the BRAM content frames, in the frame address (FAR).
BRAM_BLOCK_TYPE = 1


@dataclass
class Upset:
    """One bit of a frame that is different from the golden data."""

    far: int
    word_index: int
    bit_index: int
    golden_word: int
    erroneous_word: int

    def __str__(self) -> str:
        return (f"far {self.far:#010x} word {self.word_index:3d} "
                f"bit {self.bit_index:2d} (golden {self.golden_word:#010x}, "
                f"read {self.erroneous_word:#010x})")


def word_values(frame: FpgaFrame) -> List[int]:
    # Keep only the values of the words. Lists of integers are fast to
    # compare.
    return [word.value for word in frame.words]


def is_dummy(frames: List[FpgaFrame], index: int) -> bool:
    # The first and the last frame of a readback are dummy frames. A frame
    # with the same address as the frame before it is a pad frame. The
    # SK-RAFT server uses the same rule.
    if index == 0 or index == len(frames) - 1:
        return True
    return index >= 2 and frames[index].far == frames[index - 1].far


class ReadbackScrubber:
    """Compares the CRAM with the golden frames and corrects it."""

    def __init__(self, dev, golden: List[FpgaFrame]):
        self.dev = dev
        self.golden_frames = golden
        self.golden = [word_values(frame) for frame in golden]
        # Never write a dummy frame: its address is the address of the
        # frame before it.
        self.checked = [index for index in range(len(golden))
                        if not is_dummy(golden, index)]
        # The block type of each frame address that was decoded.
        self.block_types = {}

    def is_bram(self, far: int) -> bool:
        # SK-RAFT: decode the frame address. The script decodes only the
        # frames that it needs, and keeps the result.
        if far not in self.block_types:
            self.block_types[far] = self.dev.decode_far(far).blocktype
        return self.block_types[far] == BRAM_BLOCK_TYPE

    def scrub(self):
        # SK-RAFT: read back all the frames of the CRAM. A plain readback
        # does not capture the flip-flops.
        frames = self.dev.readback(ReadbackOption.READBACK)

        upsets: List[Upset] = []
        correction_s = 0.0
        for index in self.checked:
            current = word_values(frames[index])
            golden = self.golden[index]
            if current == golden:
                continue
            far = frames[index].far
            if self.is_bram(far):
                continue

            # Find each bit that is different from the golden data.
            for word_index, (read, gold) in enumerate(zip(current, golden)):
                different = read ^ gold
                for bit_index in range(32):
                    if (different >> bit_index) & 1:
                        upsets.append(Upset(far, word_index, bit_index,
                                            gold, read))

            # SK-RAFT: write the golden frame back, at its frame address.
            start = time.monotonic()
            self.dev.write_frame(self.golden_frames[index])
            correction_s += time.monotonic() - start

        return upsets, correction_s


def inject_upset(dev, scrubber: ReadbackScrubber):
    while True:
        # SK-RAFT: inject one upset into a random bit of the CRAM. The
        # server does not inject into the dummy frames, and into the frames
        # that it excludes, for example the frames of the IOBs.
        injected = dev.inject_random(TargetMemory.CRAM)
        if not scrubber.is_bram(injected.far):
            return injected
        # The scrubber does not check the BRAM content frames. SK-RAFT:
        # flip the same bit again to remove the upset. Then inject again.
        dev.inject_at(injected.far, injected.word_index,
                      injected.bit_index, TargetMemory.CRAM)


def main() -> None:
    injected_total = 0
    injected_corrected = 0
    corrected_total = 0
    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                print(f"Device: serial number {dev.serial_number}, "
                      f"part number {dev.part_number}")

                # SK-RAFT: read back the CRAM at the start. These frames are
                # the golden frames.
                golden = dev.readback(ReadbackOption.READBACK)
                scrubber = ReadbackScrubber(dev, golden)
                print(f"Golden frames: {len(golden)}, checked frames: "
                      f"{len(scrubber.checked)}")

                # SK-RAFT: set the seed of the random injections, after
                # attach. Then each run injects the same upsets.
                dev.configure_seed(SEED)
                print("-" * 80)

                next_start = time.monotonic()
                last_end = next_start
                for cycle in range(1, SCRUB_CYCLES + 1):
                    injected = None
                    if INJECT_UPSETS:
                        injected = inject_upset(dev, scrubber)
                        injected_total += 1

                    # Wait for the start of the scrub cycle. The upset stays
                    # in the CRAM during this time.
                    next_start += SCRUB_PERIOD_S
                    time.sleep(max(0.0, next_start - time.monotonic()))

                    start = time.monotonic()
                    idle_s = start - last_end
                    upsets, correction_s = scrubber.scrub()
                    last_end = time.monotonic()
                    corrected_total += len(upsets)

                    print(f"Cycle {cycle:2d}: {len(upsets)} upset(s) "
                          f"corrected | correction {correction_s:.3f} s | "
                          f"cycle {last_end - start:.3f} s | "
                          f"idle {idle_s:.3f} s")
                    for upset in upsets:
                        print(f"    {upset}")
                    if injected is not None:
                        found = any(
                            upset.far == injected.far
                            and upset.word_index == injected.word_index
                            and upset.bit_index == injected.bit_index
                            for upset in upsets
                        )
                        injected_corrected += found
                        print(f"    injected far {injected.far:#010x} "
                              f"word {injected.word_index:3d} "
                              f"bit {injected.bit_index:2d}: "
                              f"{'corrected' if found else 'NOT corrected'}")
    except SkraftError as e:
        print(f"Example failed: {e}")
        return
    except KeyboardInterrupt:
        print("Interrupted.")
        return

    print("-" * 80)
    print(f"Upsets corrected: {corrected_total}")
    if INJECT_UPSETS:
        print(f"Injected upsets corrected: {injected_corrected} of "
              f"{injected_total}")
    print("Example done.")


if __name__ == "__main__":
    main()
