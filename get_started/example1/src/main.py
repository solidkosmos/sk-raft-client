# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example 1: CRAM injection in three steps.

This example flips bits in the configuration RAM (CRAM) of the FPGA and
shows the effect of each upset. The target area becomes smaller in three
steps. Each step is more targeted than the step before it:

  1. Random bits, anywhere.       Most flips have no effect. This step
                                   shows why it is important to aim at
                                   essential bits only.
  2. Essential bits only.         Each flip hits a bit that the design
                                   depends on.
  3. One pblock at a time.        The target is one part of the design
                                   only, so you can test that part alone.

Each step holds an upset for 100 ms and then corrects the upset. Step 1
stops after STEP1_UPSETS upsets (200), or earlier when you press Enter.
Steps 2 and 3 continue until you press Enter.

The design has two shift registers with a feedback loop. LD0 and LD1 on
the board show their parities. Each register starts with one '1' bit, so
both LEDs are on. An upset that changes the number of '1' bits in a
register changes its LED. The register keeps the changed bits after the
correction of the upset, until the script programs the FPGA again.
"""

from __future__ import annotations

import random
import threading
import time

from skraft import (
    Design,
    FpgaDevice,
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

# The design for all steps: targeted_top, two 16-bit shift registers
# with a feedback loop. LD0 and LD1 show their parities.
# The script gives all three files at the start:
#   The bitstream (.bit): to program the device.
#   The EBD file (.ebd): to find which bits are essential.
#   The XDC file (.xdc): to find the pblocks.
# dev.upload_design_to_server() sends the files to the server. The client sends
# only the file name of each path, not the directory.
#
# BOARD is the board of your target device: "basys3" or "zedboard", or
# the name of your own board (see hw/README.md). The script reads the
# design files from hw/design_examples/<BOARD>/targeted_top/. Extract
# design_examples.zip there, or build the design with create_project.tcl.
# The paths are relative to src/. Run the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/targeted_top"

design = Design(
    bit=f"{DESIGN_DIR}/targeted_top.bit",
    ebd=f"{DESIGN_DIR}/targeted_top.ebd",
    xdc=f"{DESIGN_DIR}/board.xdc",
)

# The pblocks of step 3, as the XDC file declares them.
PBLOCKS = ["pblock_sr_0", "pblock_sr_1"]

# A fixed seed gives the same sequence of step 1 injections in each run.
# In steps 2 and 3, the server selects the bits.
rng = random.Random(42)

# Step 1 stops after this number of upsets. Press Enter to stop it earlier.
STEP1_UPSETS = 200

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop the
# current step early.
stop = threading.Event()
enter_thread: threading.Thread | None = None


def watch_for_enter() -> None:
    """Clear stop, and set it again when you press Enter.

    Step 1 can end without Enter. Then its thread still waits for Enter,
    and the next step uses that thread, so only one thread reads the
    keyboard.
    """
    global enter_thread
    stop.clear()
    if enter_thread is None or not enter_thread.is_alive():
        enter_thread = threading.Thread(
            target=lambda: (input(), stop.set()), daemon=True)
        enter_thread.start()


def step1_random_bits(dev: FpgaDevice) -> None:
    """Step 1: flip random bits, anywhere in the configuration RAM.

    This is a full random CRAM injection routine, with all steps visible in
    this script. The step reads back all the frames of the device. Then it
    selects the frame, word and bit to flip. It stops after STEP1_UPSETS
    upsets, or earlier when you press Enter.

    Args:
        dev: The attached device, programmed with the design.
    """
    print(f"\nStep 1: random bits, anywhere. {STEP1_UPSETS} "
          "upsets, or press Enter to move on.")

    frames = dev.readback(ReadbackOption.READBACK)
    print(f"frames read back: {len(frames)}")
    time.sleep(1)
    watch_for_enter()
    # The number of injections in this step.
    n = 0
    while n < STEP1_UPSETS and not stop.is_set():
        # Inject a random CRAM upset.
        frame = frames[rng.randint(0, len(frames) - 1)]
        # The number of words in a frame depends on the architecture.
        word_index = rng.randint(0, len(frame.words) - 1)
        # A word has 32 bits, so the bit index is 0 to 31.
        bit_index = rng.randint(0, 31)
        report = dev.inject_at(frame.far, word_index, bit_index,
                               TargetMemory.CRAM)
        print(f"{n + 1:3d}: far {report.far:#010x} "
              f"word {report.word_index:3d} "
              f"bit {report.bit_index:2d}")
        n += 1

        # Keep the upset for 100 ms.
        time.sleep(0.1)

        # Flip the same bit again to correct the upset.
        dev.inject_at(frame.far, word_index, bit_index, TargetMemory.CRAM)


def step2_essential_bits(dev: FpgaDevice) -> None:
    """Step 2: flip random essential bits only.

    The EBD file lists the bits that the design depends on. The step limits
    the injection to these bits, so each flip hits one of them. It programs
    the FPGA again first, to remove the upsets of step 1. It continues until
    you press Enter.

    Args:
        dev: The attached device, with the design uploaded to the server.
    """
    print("\nStep 2: essential bits only",
          f"({dev.bit_count(TargetMemory.ESSENTIAL_CRAM)})",
          ". Press Enter to move on.")
    # Program the FPGA again to remove the upsets of step 1.
    dev.program_fpga(design)

    watch_for_enter()
    n = 0
    while not stop.is_set():
        # This time, the server selects the location from the essential bits
        # in the EBD file.
        report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
        print(f"{n + 1:3d}: far {report.far:#010x} "
              f"word {report.word_index:3d} "
              f"bit {report.bit_index:2d}")
        n += 1

        # Keep the upset for 100 ms.
        time.sleep(0.1)

        # Flip the same bit again to correct the upset.
        dev.inject_at(report.far, report.word_index, report.bit_index,
                      TargetMemory.CRAM)


def step3_one_pblock_at_a_time(dev: FpgaDevice) -> None:
    """Step 3: flip random essential bits of one pblock at a time.

    A pblock is a region of the device that contains only one part of the
    design. In this design, each pblock contains one of the two shift
    registers: pblock_sr_0 the register of LD0, pblock_sr_1 the register of
    LD1. When you limit the injection to a pblock, you can test one part of
    the design alone. The step programs the FPGA again first, to
    remove the upsets of step 2. Each pblock continues until you press
    Enter.

    Args:
        dev: The attached device, with the design uploaded to the server.
    """
    print("\nStep 3: one pblock at a time.")
    # Program the FPGA again to remove the upsets of step 2.
    dev.program_fpga(design)

    for pblock in PBLOCKS:
        n_essential = dev.bit_count(TargetMemory.ESSENTIAL_CRAM, pblock=pblock)
        print(f"\n{pblock}: essential bits ({n_essential}). "
              "Press Enter to move on.")
        watch_for_enter()
        time.sleep(1)
        n = 0
        while not stop.is_set():
            # This time, the server selects the location from the essential
            # bits in the EBD file and from the pblock range in the XDC file.
            report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                                       pblock=pblock)
            print(f"{n + 1:3d}: far {report.far:#010x} "
                  f"word {report.word_index:3d} "
                  f"bit {report.bit_index:2d}")
            n += 1

            # Keep the upset for 100 ms.
            time.sleep(0.1)

            # Flip the same bit again to correct the upset.
            dev.inject_at(report.far, report.word_index, report.bit_index,
                          TargetMemory.CRAM)


def main() -> int:
    """Run the three steps on the first board that the server lists.

    Returns:
        0 when all the steps ran, 1 after an SK-RAFT error, 130 after Ctrl+C.
    """
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            # Select the first detected device.
            serial_number = client.get_devices()[0].serial_number

            with client.attach(serial_number) as dev:
                # Setup the SEED for deterministic behaviour.
                dev.configure_seed(0)

                dev.upload_design_to_server(design)
                dev.program_fpga(design)
                print(f"programmed {serial_number} with {design.bit}")

                step1_random_bits(dev)
                step2_essential_bits(dev)
                step3_one_pblock_at_a_time(dev)
    except SkraftError as e:
        print(f"Example 1 failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted")
        return 130
    print("\nExample 1 done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
