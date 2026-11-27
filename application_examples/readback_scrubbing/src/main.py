# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example: readback scrubbing of the configuration memory, in Python.

The script corrects upsets in the configuration memory (CRAM) of the FPGA.
It uses only the readback and the frame write of SK-RAFT. Each scrub cycle
checks all the checked frames. FRAMES_PER_READBACK sets how many frames
the script reads back at a time:

  0: read back all the frames of the CRAM, and then check them.
  N: read back the next N frames, and check them. Then do the same for the
     next N frames, up to the last frame.

To check a frame, the script compares it with its golden frame. The golden
frames are the readback at the start of the script. For each frame that is
different, the script writes the golden frame back.

SCRUB_TARGET selects the frames that the scrubber checks: all the frames of
the CRAM, or only the frames with essential bits. The script never checks
the dummy (pad) frames and the BRAM content frames.

For the whole CRAM, the script does not upload design files and does not
program the FPGA. It scrubs the design that is in the FPGA. For the
essential CRAM, the script programs the FPGA with DESIGN, because the server
gets the essential bits from the essential bits (EBD) file when it programs
the FPGA.

To show the scrubber at work, the script injects one random upset into the
checked frames before each scrub cycle. Each scrub cycle starts when the
previous one ends.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

from skraft import (
    Design,
    FpgaFrame,
    FrameAddressError,
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

# The frames that the scrubber checks and corrects:
#   TargetMemory.CRAM: all the frames of the CRAM. The script scrubs the
#     design that is in the FPGA.
#   TargetMemory.ESSENTIAL_CRAM: only the frames with essential bits. The
#     script programs the FPGA with DESIGN first.
# In both cases, the script does not check the BRAM content frames.
SCRUB_TARGET = TargetMemory.CRAM

# The number of frames that the script reads back at a time, in each scrub
# cycle:
#   0: one readback of all the frames of the CRAM. Then the script checks
#     all the frames.
#   N > 0: one readback of the next N checked frames. The script checks
#     them, and then reads back the next N frames, up to the last frame.
# The value must be smaller than the number of frames of the device.
FRAMES_PER_READBACK = 0

# The design for SCRUB_TARGET = TargetMemory.ESSENTIAL_CRAM: the bitstream
# and its essential bits (EBD) file. The default is the targeted_top design
# of get_started, for BOARD. Extract design_examples.zip there first, or set
# the paths of your design.
BOARD = "basys3"
HERE = Path(__file__).resolve().parent
DESIGN_DIR = (HERE.parents[2] / "get_started" / "hw" / "design_examples"
              / BOARD / "targeted_top")
DESIGN = Design(
    bit=str(DESIGN_DIR / "targeted_top.bit"),
    ebd=str(DESIGN_DIR / "targeted_top.ebd"),
)

# The number of scrub cycles. Each cycle starts when the previous one ends.
SCRUB_CYCLES = 10

# If True, inject one random upset into the checked frames before each scrub
# cycle. Set it to False to scrub only.
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

    def __init__(self, dev, golden: List[FpgaFrame],
                 essential_fars: Optional[Set[int]],
                 frames_per_readback: int):
        self.dev = dev
        self.golden_frames = golden
        self.golden = [word_values(frame) for frame in golden]
        self.frames_per_readback = frames_per_readback

        # The indexes of the checked frames, in the order of the readback.
        # Never write a dummy frame: its address is the address of the
        # frame before it. Do not check the BRAM content frames: the
        # contents of the BRAMs change during operation.
        self.checked: List[int] = []
        for index, frame in enumerate(golden):
            if is_dummy(golden, index):
                continue
            if essential_fars is not None and frame.far not in essential_fars:
                continue
            # SK-RAFT: decode the frame address, to get the block type.
            if self.dev.decode_far(frame.far).blocktype == BRAM_BLOCK_TYPE:
                continue
            self.checked.append(index)
        self.checked_fars = {golden[index].far for index in self.checked}

    def readbacks_per_cycle(self) -> int:
        if self.frames_per_readback == 0:
            return 1
        return -(-len(self.checked) // self.frames_per_readback)

    def groups(self) -> List[List[int]]:
        # The indexes of the frames of each readback of a scrub cycle.
        if self.frames_per_readback == 0:
            return [self.checked]
        size = self.frames_per_readback
        return [self.checked[start:start + size]
                for start in range(0, len(self.checked), size)]

    def read_frames(self, indexes: List[int]) -> List[FpgaFrame]:
        # Read back the frames of one group, in the order of the group.
        if self.frames_per_readback == 0:
            # SK-RAFT: read back all the frames of the CRAM. A plain
            # readback does not capture the flip-flops.
            frames = self.dev.readback(ReadbackOption.READBACK)
            return [frames[index] for index in indexes]

        fars = [self.golden_frames[index].far for index in indexes]
        # read back the frames from the lowest to the highest FAR
        # of the group, with one readback. The result also has the frames
        # between them that the scrubber does not check (for example the
        # frames without essential bits), but no dummy frames.
        frames = self.dev.readback_range(min(fars), max(fars))
        by_far = {frame.far: frame for frame in frames}
        missing = [far for far in fars if far not in by_far]
        if missing:
            raise FrameAddressError(
                f"the range readback has no frame {missing[0]:#010x}")
        return [by_far[far] for far in fars]

    def check(self, indexes: List[int],
              frames: List[FpgaFrame]) -> Tuple[List[Upset], float]:
        # Compare the frames with the golden frames, and correct them.
        upsets: List[Upset] = []
        correction_s = 0.0
        for index, frame in zip(indexes, frames):
            current = word_values(frame)
            golden = self.golden[index]
            if current == golden:
                continue

            # Find each bit that is different from the golden data.
            for word_index, (read, gold) in enumerate(zip(current, golden)):
                different = read ^ gold
                for bit_index in range(32):
                    if (different >> bit_index) & 1:
                        upsets.append(Upset(frame.far, word_index, bit_index,
                                            gold, read))

            # SK-RAFT: write the golden frame back, at its frame address.
            start = time.monotonic()
            self.dev.write_frame(self.golden_frames[index])
            correction_s += time.monotonic() - start

        return upsets, correction_s

    def scrub(self) -> Tuple[List[Upset], float]:
        # One scrub cycle: read back each group of frames, and check it
        # before the next readback.
        upsets: List[Upset] = []
        correction_s = 0.0
        for indexes in self.groups():
            frames = self.read_frames(indexes)
            group_upsets, group_correction_s = self.check(indexes, frames)
            upsets += group_upsets
            correction_s += group_correction_s
        return upsets, correction_s


def inject_upset(dev, scrubber: ReadbackScrubber):
    while True:
        # inject one upset into a random bit of SCRUB_TARGET. The
        # server does not inject into the dummy frames, and into the frames
        # that it excludes, for example the frames of the IOBs.
        injected = dev.inject_random(SCRUB_TARGET)
        if injected.far in scrubber.checked_fars:
            return injected
        # The scrubber does not check this frame, for example a BRAM
        # content frame. SK-RAFT: flip the same bit again to remove the
        # upset. Then inject again.
        dev.inject_at(injected.far, injected.word_index,
                      injected.bit_index, TargetMemory.CRAM)


def main() -> int:
    injected_total = 0
    injected_corrected = 0
    corrected_total = 0

    if SCRUB_TARGET not in (TargetMemory.CRAM, TargetMemory.ESSENTIAL_CRAM):
        print("SCRUB_TARGET must be TargetMemory.CRAM or "
              "TargetMemory.ESSENTIAL_CRAM.")
        return 2
    essential = SCRUB_TARGET == TargetMemory.ESSENTIAL_CRAM

    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            # Select the first detected device.
            serial_number = client.get_devices()[0].serial_number

            with client.attach(serial_number) as dev:
                # Setup the SEED for deterministic behaviour.
                dev.configure_seed(0)

                print(f"Device: serial number {dev.serial_number}, "
                      f"part number {dev.part_number}")

                # get the frame addresses of the device, to check
                # FRAMES_PER_READBACK.
                device_frames = len(dev.far_list())
                if not 0 <= FRAMES_PER_READBACK < device_frames:
                    print(f"FRAMES_PER_READBACK must be from 0 to "
                          f"{device_frames - 1} (the device has "
                          f"{device_frames} frames).")
                    return 2

                essential_fars = None
                if essential:
                    # upload the design and program the FPGA. The
                    # server gets the essential bits from the EBD file when
                    # it programs the FPGA.
                    dev.upload_design_to_server(DESIGN)
                    dev.program_fpga(DESIGN)
                    print(f"Programmed {DESIGN.bit}")
                    # SK-RAFT: get the frames that have essential bits. The
                    # script uses only their frame addresses.
                    essential_fars = {frame.far
                                      for frame in dev.essential_frames()}

                # SK-RAFT: read back the CRAM at the start. These frames are
                # the golden frames.
                golden = dev.readback(ReadbackOption.READBACK)
                scrubber = ReadbackScrubber(dev, golden, essential_fars,
                                            FRAMES_PER_READBACK)
                if not scrubber.checked:
                    print("The scrubber has no frames to check.")
                    return 1
                frames_per_readback = (FRAMES_PER_READBACK
                                       if FRAMES_PER_READBACK else "all")
                print(f"Scrub target: "
                      f"{'essential CRAM' if essential else 'whole CRAM'}, "
                      f"frames per readback: {frames_per_readback}")
                print(f"Golden frames: {len(golden)}, checked frames: "
                      f"{len(scrubber.checked)}, readbacks per cycle: "
                      f"{scrubber.readbacks_per_cycle()}")

                # SK-RAFT: set the seed of the random injections, after
                # attach. Then each run injects the same upsets.
                dev.configure_seed(SEED)
                print("-" * 80)

                for cycle in range(1, SCRUB_CYCLES + 1):
                    injected = None
                    if INJECT_UPSETS:
                        injected = inject_upset(dev, scrubber)
                        injected_total += 1

                    # The time of the cycle is the time that the scrub
                    # actually takes. The injection is not part of it.
                    start = time.monotonic()
                    upsets, correction_s = scrubber.scrub()
                    cycle_s = time.monotonic() - start
                    corrected_total += len(upsets)

                    print(f"Cycle {cycle:2d}: {len(upsets)} upset(s) "
                          f"corrected | correction {correction_s:.3f} s | "
                          f"cycle {cycle_s:.3f} s")
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
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130

    print("-" * 80)
    print(f"Upsets corrected: {corrected_total}")
    if INJECT_UPSETS:
        print(f"Injected upsets corrected: {injected_corrected} of "
              f"{injected_total}")
    print("Example done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
