# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Speed test: the time of the main SK-RAFT functions.

The script measures how long each function takes as the client sees it,
from the call in Python to the return of its result. It runs each test
several times, and prints the minimum, the median, the 95th percentile and
the maximum, in milliseconds.

The design is brams_top of example 4: one BRAM, with flip-flops around it
(the ECC, the hold register and the BSCAN registers). Thus the script can
measure the injection into the flip-flops and into the BRAM content.

The tests:

  program              dev.program_fpga().
  read_1               dev.readback_range() of 1 frame.
  read_1000            dev.readback_range() of 1000 frames.
  write_1              dev.write_frame() of 1 frame.
  read_all             dev.readback(): all the frames of the CRAM.
  inject_ff            dev.inject_random(TargetMemory.FF).
  inject_bram          dev.inject_random(TargetMemory.BRAM, pblock=...).
  scrub_cram           One scrub cycle of all the frames of the CRAM.
  scrub_essential      One scrub cycle of the frames with essential bits.

A scrub cycle reads back the checked frames, compares them with the golden
frames (the readback after the programming) and writes back each frame
that is different. It checks neither the dummy (pad) frames nor the BRAM
content frames, as application_examples/readback_scrubbing does.
scrub_cram reads all the frames with one dev.readback().
scrub_essential reads only the frames with essential bits, with one
dev.readback_range() for each group of consecutive frames. Before each
scrub cycle, the script injects one upset into a checked frame, and then
it checks that the cycle corrected the upset.

write_1 writes back the frame that the script read, so it does not change
the design. The random upsets of inject_ff and inject_bram add up, so the
script programs the FPGA again after these tests. The script stops the
clock of the design (USER1) during these tests, as the general guidelines
require.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from skraft import (
    BscanPrimitive,
    Design,
    FpgaDevice,
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

# The design of example 4. BOARD is "basys3" or "zedboard", or the name of
# your own board (see hw/README.md). The script reads the design files from
# hw/design_examples/<BOARD>/brams_top/. Extract design_examples.zip there,
# or build the design with create_project.tcl. The paths are relative to
# src/. Run the script from that folder.
# To use your own design, set the paths of its four files below, and set
# PBLOCK_BRAM and USER_CLK_EN for your design (refer to README.md).
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/brams_top"

design = Design(
    bit=f"{DESIGN_DIR}/brams_top.bit",
    ebd=f"{DESIGN_DIR}/brams_top.ebd",
    ll=f"{DESIGN_DIR}/brams_top.ll",
    xdc=f"{DESIGN_DIR}/board.xdc",
)

# The pblock of the BRAM of brams_top, for inject_bram. None: inject into
# all the BRAMs of the design.
PBLOCK_BRAM: str | None = "pblock_soft_sec_bram"

# The clock enable of brams_top: BSCAN USER1, 1 bit. The script writes 0 to
# stop the clock and 1 to start it. None: the design has no clock enable,
# and the script does not stop the clock.
USER_CLK_EN: BscanPrimitive | None = BscanPrimitive(1, 1)

# The number of measurements of each test.
PROGRAM_REPEATS = 5
REPEATS = 50
BATCH_REPEATS = 10
READBACK_REPEATS = 3
SCRUB_CYCLES = 5
# The calls before each test that the script does not measure.
WARMUP = 3
# The number of frames of read_1000.
BATCH_FRAMES = 1000
# The index of the first frame of read_1, read_1000 and write_1 in
# dev.far_list(). The test frames must be configuration frames (block
# type 0).
FIRST_FRAME_INDEX = 100
# The block type of the BRAM content frames, in the frame address (FAR).
BRAM_BLOCK_TYPE = 1


@dataclass(frozen=True)
class Result:
    """The times of one test, in milliseconds."""

    n: int
    frames: int
    minimum: float
    median: float
    p95: float
    maximum: float


def summarize(times: list[float], frames: int = 1) -> Result:
    """Return the statistics of the times (ms) of one test. frames is the
    number of frames of one call."""
    times = sorted(times)
    return Result(
        n=len(times),
        frames=frames,
        minimum=times[0],
        median=statistics.median(times),
        p95=times[min(len(times) - 1, int(0.95 * len(times)))],
        maximum=times[-1],
    )


def elapsed_ms(start_ns: int) -> float:
    """Return the time since start_ns (time.perf_counter_ns()), in ms."""
    return (time.perf_counter_ns() - start_ns) / 1e6


def measure(call: Callable[[], object], repeats: int, frames: int = 1,
            warmup: int = WARMUP) -> Result:
    """Run call() warmup + repeats times and return the statistics of the
    measured calls."""
    for _ in range(warmup):
        call()
    times = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        call()
        times.append(elapsed_ms(start))
    return summarize(times, frames)


def word_values(frame: FpgaFrame) -> list[int]:
    """Return the values of the words of a frame."""
    return [word.value for word in frame.words]


def is_dummy(frames: list[FpgaFrame], index: int) -> bool:
    """Return True for a dummy frame of a readback: the first frame, the
    last frame, and a pad frame (the same address as the frame before)."""
    if index in (0, len(frames) - 1):
        return True
    return index >= 2 and frames[index].far == frames[index - 1].far


def enable_clock(dev: FpgaDevice, enabled: bool) -> None:
    """Start or stop the clock of the design through USER_CLK_EN."""
    if USER_CLK_EN is not None:
        dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)


def program(dev: FpgaDevice) -> None:
    """Program the FPGA, to clear the upsets, and start the clock."""
    dev.program_fpga(design)
    enable_clock(dev, True)


@dataclass
class Scrubber:
    """One scrub cycle: read back the checked frames, compare them with the
    golden frames and write back each frame that is different.

    golden is the readback after the programming. checked holds the indexes
    of the checked frames in golden. With full=True, a cycle reads all the
    frames with one readback. With full=False, it reads each group of
    consecutive checked frames with one range readback.
    """

    dev: FpgaDevice
    golden: list[FpgaFrame]
    checked: list[int]
    full: bool
    golden_words: list[list[int]] = field(init=False)
    groups: list[list[int]] = field(init=False)

    def __post_init__(self) -> None:
        self.golden_words = [word_values(frame) for frame in self.golden]
        self.groups = []
        for index in self.checked:
            if self.groups and index == self.groups[-1][-1] + 1:
                self.groups[-1].append(index)
            else:
                self.groups.append([index])

    def checked_fars(self) -> set[int]:
        """Return the frame addresses of the checked frames."""
        return {self.golden[index].far for index in self.checked}

    def read(self) -> list[tuple[int, FpgaFrame]]:
        """Read back the checked frames. Return (index, frame) pairs."""
        if self.full:
            frames = self.dev.readback(ReadbackOption.READBACK)
            return [(index, frames[index]) for index in self.checked]
        pairs = []
        for group in self.groups:
            frames = self.dev.readback_range(self.golden[group[0]].far,
                                             self.golden[group[-1]].far)
            by_far = {frame.far: frame for frame in frames}
            pairs += [(index, by_far[self.golden[index].far])
                      for index in group]
        return pairs

    def scrub(self) -> set[int]:
        """Run one scrub cycle. Return the addresses of the frames that it
        wrote back."""
        written = set()
        for index, frame in self.read():
            if word_values(frame) != self.golden_words[index]:
                self.dev.write_frame(self.golden[index])
                written.add(frame.far)
        return written


def inject_checked(dev: FpgaDevice, target: TargetMemory,
                   fars: set[int]) -> int:
    """Inject one random upset into target, in one of the frames fars.
    Return the frame address of the upset."""
    while True:
        hit = dev.inject_random(target)
        if hit.far in fars:
            return hit.far
        # The scrubber does not check this frame: flip the bit back, and
        # inject again.
        dev.inject_at(hit.far, hit.word_index, hit.bit_index,
                      TargetMemory.CRAM)


def measure_scrub(dev: FpgaDevice, scrubber: Scrubber,
                  target: TargetMemory) -> tuple[Result, int]:
    """Run SCRUB_CYCLES scrub cycles, each after one upset. Return the
    statistics of the cycles (the injection is not measured) and the number
    of upsets that the cycles corrected."""
    fars = scrubber.checked_fars()
    times = []
    corrected = 0
    for _ in range(SCRUB_CYCLES):
        far = inject_checked(dev, target, fars)
        start = time.perf_counter_ns()
        written = scrubber.scrub()
        times.append(elapsed_ms(start))
        corrected += far in written
    return summarize(times, len(scrubber.checked)), corrected


def test_frames(dev: FpgaDevice, fars: list[int]) -> tuple[int, int]:
    """Return the first and the last FAR of the read_1000 frames. Stop if
    they are not configuration frames (block type 0)."""
    first = min(FIRST_FRAME_INDEX, len(fars) - BATCH_FRAMES)
    far0, far_last = fars[first], fars[first + BATCH_FRAMES - 1]
    for far in (far0, far_last):
        if dev.decode_far(far).blocktype != 0:
            raise SystemExit(f"The test frame {far:#010x} is not a "
                             f"configuration frame. Change "
                             f"FIRST_FRAME_INDEX.")
    return far0, far_last


def run_tests(dev: FpgaDevice) -> dict[str, Result]:
    """Run the tests on an attached device, with the design uploaded."""
    results: dict[str, Result] = {}

    print("Measuring the programming...")
    results["program"] = measure(lambda: dev.program_fpga(design),
                                 PROGRAM_REPEATS, warmup=0)
    enable_clock(dev, True)

    print("Measuring the frame reads and writes...")
    fars = dev.far_list()
    far0, far_last = test_frames(dev, fars)
    frame0 = dev.readback_range(far0, far0)
    results["read_1"] = measure(lambda: dev.readback_range(far0, far0),
                                REPEATS)
    results["read_1000"] = measure(
        lambda: dev.readback_range(far0, far_last), BATCH_REPEATS,
        BATCH_FRAMES)
    results["write_1"] = measure(lambda: dev.write_frame(frame0[0]), REPEATS)
    if word_values(dev.readback_range(far0, far0)[0]) != word_values(
            frame0[0]):
        print("The frame of write_1 changed. Check the setup.")
    results["read_all"] = measure(
        lambda: dev.readback(ReadbackOption.READBACK), READBACK_REPEATS,
        len(fars), warmup=0)

    print("Measuring the injections into the flip-flops and the BRAM...")
    enable_clock(dev, False)
    results["inject_ff"] = measure(
        lambda: dev.inject_random(TargetMemory.FF), REPEATS)
    results["inject_bram"] = measure(
        lambda: dev.inject_random(TargetMemory.BRAM, pblock=PBLOCK_BRAM),
        REPEATS)
    program(dev)

    print("Measuring the scrub cycles...")
    golden = dev.readback(ReadbackOption.READBACK)
    # The checked frames: no dummy frames, no BRAM content frames.
    checked = [
        index for index, frame in enumerate(golden)
        if not is_dummy(golden, index)
        and dev.decode_far(frame.far).blocktype != BRAM_BLOCK_TYPE
    ]
    essential_fars = {frame.far for frame in dev.essential_frames()}
    checked_essential = [index for index in checked
                         if golden[index].far in essential_fars]

    cram = Scrubber(dev, golden, checked, full=True)
    results["scrub_cram"], corrected = measure_scrub(
        dev, cram, TargetMemory.CRAM)
    print(f"scrub_cram: {len(checked)} checked frames, {corrected} of "
          f"{SCRUB_CYCLES} upsets corrected.")

    essential = Scrubber(dev, golden, checked_essential, full=False)
    results["scrub_essential"], corrected = measure_scrub(
        dev, essential, TargetMemory.ESSENTIAL_CRAM)
    print(f"scrub_essential: {len(checked_essential)} checked frames in "
          f"{len(essential.groups)} range readbacks, {corrected} of "
          f"{SCRUB_CYCLES} upsets corrected.")
    return results


def print_results(results: dict[str, Result]) -> None:
    """Print the statistics of each test."""
    print(f"\n{'TEST':<16} {'N':>4} {'MIN':>10} {'MEDIAN':>10} {'P95':>10} "
          f"{'MAX':>10} {'FRAMES':>7} {'/FRAME':>7}   (ms)")
    for name, r in results.items():
        frames = (f"{r.frames:>7} {r.median / r.frames:>7.3f}"
                  if r.frames > 1 else "")
        print(f"{name:<16} {r.n:>4} {r.minimum:>10.3f} {r.median:>10.3f} "
              f"{r.p95:>10.3f} {r.maximum:>10.3f} {frames}")


def main() -> int:
    """Run the speed test."""
    print("Speed test: the time of the SK-RAFT functions")
    results: dict[str, Result] = {}
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            # Select the first detected device.
            serial_number = client.get_devices()[0].serial_number
            with client.attach(serial_number) as dev:
                dev.configure_seed(0)
                dev.upload_design_to_server(design)
                print(f"Board {serial_number}, design {design.bit}.")
                results = run_tests(dev)
                print("Programming the FPGA again to clear the device.")
                program(dev)
    except SkraftError as e:
        print(f"Speed test failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Program the FPGA again before you use the "
              "design.")
        return 130

    print_results(results)
    print("\nSpeed test done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
