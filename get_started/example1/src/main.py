# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example 1: fault injection, three ways.

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

Each step holds an upset for 100 ms and then corrects the upset. Press
Enter to stop a step early. Look at LD0/LD1 on the board: the heartbeat
counters show the effect of each upset.
"""

import random
import threading
import time

from skraft import Design, TargetMemory, ReadbackOption, SkraftError, SkraftFpga

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BA251CA"

# The design for all steps: two heartbeat counters (LD0, LD1).
# The script gives all three files at the start:
#   The bitstream (.bit): to program the device.
#   The EBD file (.ebd): to find which bits are essential.
#   The XDC file (.xdc): to find the pblocks.
# uploadDesignToServer() sends the files to the server. The client sends
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

# A fixed seed gives the same sequence of step 1 injections in each run.
# In steps 2 and 3, the server selects the bits.
rng = random.Random(42)

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop the
# current step early.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()

def main() -> None:
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                # Setup the SEED for deterministic behaviour. 
                dev.configure_seed(0)

                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"programmed {SERIAL_NUMBER} with {design.bit}")

                # ----------------------------------------------------------- #
                # Step 1: random bits, anywhere in the configuration RAM.
                # ----------------------------------------------------------- #
                print("\nStep 1: random bits, anywhere. "
                      "Press Enter to move on.")

                # This is a full random CRAM injection routine, with all
                # steps visible in this script. The script reads back all
                # frames of the connected device. Then the script selects
                # the frame, word and bit to flip.
                frames = dev.readback(ReadbackOption.READBACK)
                print(f"frames read back: {len(frames)}")
                time.sleep(1)
                watch_for_enter()
                # The number of injections in this step.
                n = 0
                while True:
                    if stop.is_set():
                        break

                    # Inject a random CRAM upset.
                    frame = frames[rng.randint(0, len(frames) - 1)]
                    # The number of words in a frame depends on the
                    # architecture.
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
                    dev.inject_at(frame.far, word_index, bit_index,
                                TargetMemory.CRAM)

                # ----------------------------------------------------------- #
                # Step 2: essential bits only.
                #
                # The EBD file lists the bits that the design depends on.
                # Limit the injection to these bits. Then each flip hits
                # one of these bits.
                # ----------------------------------------------------------- #
                print(f"\nStep 2: essential bits only",
                      f"({dev.bit_count(TargetMemory.ESSENTIAL_CRAM)})",
                      f". Press Enter to move on.")
                # Program the FPGA again to remove the upsets of step 1.
                dev.programFPGA(design)

                watch_for_enter()
                n = 0
                while True:
                    if stop.is_set():
                        break

                    # This time, the server selects the location from the
                    # essential bits in the EBD file.
                    report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
                    print(f"{n + 1:3d}: far {report.far:#010x} "
                        f"word {report.word_index:3d} "
                        f"bit {report.bit_index:2d}")
                    n += 1

                    # Keep the upset for 100 ms.
                    time.sleep(0.1)
                    dev.inject_at(report.far, report.word_index,
                                  report.bit_index, TargetMemory.CRAM)

                # ----------------------------------------------------------- #
                # Step 3: one pblock at a time.
                #
                # A pblock is a region of the device that contains only one
                # part of the design. In this design, each pblock contains
                # one of the two heartbeat counters. When you limit the
                # injection to a pblock, you can test one part of the design
                # alone.
                # ----------------------------------------------------------- #
                print("\nStep 3: one pblock at a time.")
                # Program the FPGA again to remove the upsets of step 2.
                dev.programFPGA(design)

                # The names of the two pblocks, as declared in the XDC file.
                pblocks = ["pblock_slow_heartbeat", "pblock_fast_heartbeat"]

                for pblock in pblocks:
                    n_essential = dev.bit_count(TargetMemory.ESSENTIAL_CRAM,
                                                pblock=pblock)
                    print(f"\n{pblock}: essential bits ({n_essential}). "
                          f"Press Enter to move on.")
                    watch_for_enter()
                    time.sleep(1)
                    n = 0
                    while True:
                        if stop.is_set():
                            break

                        # This time, the server selects the location from
                        # the essential bits in the EBD file and from the
                        # pblock range in the XDC file.
                        report = dev.inject_random(
                            TargetMemory.ESSENTIAL_CRAM,
                            pblock=pblock)
                        print(f"{n + 1:3d}: far {report.far:#010x} "
                            f"word {report.word_index:3d} "
                            f"bit {report.bit_index:2d}")
                        n += 1

                        # Keep the upset for 100 ms.
                        time.sleep(0.1)
                        dev.inject_at(report.far, report.word_index,
                                    report.bit_index, 
                                    TargetMemory.CRAM)
    except SkraftError as e:
            print(f"Example 1 failed: {e}")
    except KeyboardInterrupt:
        print(f"Interrupted")
        return
    print("\nExample 1 done.")


if __name__ == "__main__":
    main()
