"""Example 1: fault injection, three ways.

We flip bits in the FPGA's configuration memory (CRAM) and see what breaks - but
we narrow down where we flip in three steps, each more targeted than the last:

  1. Random bits, anywhere.       Mostly hits nothing. Shows why aiming to
                                   essential bits only matters.
  2. Essential bits only.         Every flip lands on a bit the design
                                   depends on.
  3. One pblock at a time.        Narrows further to a single part of the
                                   design, so you can test it on its own.

Each step holds an upset for 100ms, then corrects it, and can be stopped
early by pressing Enter. Watch LD0/LD1 on the board: the heartbeats show
what each upset does.
"""

import random
import threading
import time

from skraft import Design, TargetMemory, ReadbackOption, SkraftError, SkraftFpga

# --------------------------------------------------------------------------- #
# Configuration. Edit these to match your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you are unsure of your target device's serial number
# you can check via the get_devices call 
DEVICE = "210183BFD452A"

# The design used throughout: two heartbeat counters (LD0, LD1).
# We give all three files up front - .bit to program the device,
# .ebd to know which bits are essential, .xdc to know the pblocks.
# uploadDesignToServer() sends the files, 
# and the server stores them under the same relative path.
design = Design(
    bit="design_files/targeted_top.bit",
    ebd="design_files/targeted_top.ebd",
    xdc="design_files/board.xdc",
)

# Same seed, same sequence of step 1 injections every run (steps 2 and 3
# let the server pick the bits).
rng = random.Random(42)

# Watches for the Enter key in the background, so it doesn't block the
# injection loop below. Press Enter any time to end the current step early
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()

def main() -> None:
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:

                dev.uploadDesignToServer(design)
                dev.programFPGA()
                print(f"programmed {DEVICE} with {design.bit}")

                # ----------------------------------------------------------- #
                # Step 1: random bits, anywhere in the configuration memory.
                # ----------------------------------------------------------- #
                print("\nStep 1: random bits, anywhere. "
                      "Press Enter to move on.")

                # A complete random CRAM injection routine, done in the
                # open: read back every frame of the connected device, then
                # choose the frame, word and bit to flip here in the script.
                frames = dev.readback(ReadbackOption.READBACK)
                print(f"frames read back: {len(frames)}")
                time.sleep(1)
                watch_for_enter()
                n = 0  # count the number of injections so far
                while True:
                    if stop.is_set():
                        break

                    # Inject a random CRAM upset.
                    frame = frames[rng.randint(0, len(frames) - 1)]
                    # Word count depends on the architecture
                    word_index = rng.randint(0, len(frame.words) - 1)
                    bit_index = rng.randint(0, 31)  # a config word is 32 bits 
                    report = dev.inject_at(frame.far, word_index, bit_index,
                                        TargetMemory.CRAM)
                    print(f"{n + 1:3d}: far {report.far:#010x} "
                        f"word {report.word_index:3d} "
                        f"bit {report.bit_index:2d}")
                    n += 1

                    time.sleep(0.1)  # hold the upset in place for 100ms

                    # Flipping the same bit again corrects the upset.
                    dev.inject_at(frame.far, word_index, bit_index,
                                TargetMemory.CRAM)

                # ----------------------------------------------------------- #
                # Step 2: essential bits only.
                #
                # The .ebd file lists which bits the design depends on.
                # Restrict injection to those, and every flip lands on one.
                # ----------------------------------------------------------- #
                print(f"\nStep 2: essential bits only",
                      f"({dev.bit_count(TargetMemory.ESSENTIAL_CRAM)})",
                      f". Press Enter to move on.")
                dev.programFPGA()  # start clean again

                watch_for_enter()
                n = 0
                while True:
                    if stop.is_set():
                        break

                    # The server picks the location this time, from the
                    # essential bits it knows about via the .ebd file.
                    report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
                    print(f"{n + 1:3d}: far {report.far:#010x} "
                        f"word {report.word_index:3d} "
                        f"bit {report.bit_index:2d}")
                    n += 1

                    time.sleep(0.1)  # hold the upset in place for 100ms
                    dev.inject_at(report.far, report.word_index,
                                  report.bit_index, TargetMemory.CRAM)

                # ----------------------------------------------------------- #
                # Step 3: one pblock at a time.
                #
                # A pblock is a region of the chip reserved for one part of
                # the design - here, one of the two heartbeat counters. By
                # confining injection to a pblock, you can test one piece of
                # the design in isolation.
                # ----------------------------------------------------------- #
                print("\nStep 3: one pblock at a time.")
                dev.programFPGA()  # start clean again

                # Names of the two pblocks, as declared in the .xdc file.
                pblocks = ["pblock_slow_heartbeat", "pblock_fast_heartbeat"]

                for pblock in pblocks:
                    print(f"\n{pblock}: essential bits"
                        f"({dev.bit_count(TargetMemory.ESSENTIAL_CRAM, 
                                          pblock=pblock)}). "
                        f"Press Enter to move on.")
                    watch_for_enter()
                    time.sleep(1)
                    n = 0
                    while True:
                        if stop.is_set():
                            break

                        # The server picks the location this time, from the
                        # essential bits it knows about via the .ebd file
                        # and the pblock range via the XDC.
                        report = dev.inject_random(
                            TargetMemory.ESSENTIAL_CRAM,
                            pblock=pblock)
                        print(f"{n + 1:3d}: far {report.far:#010x} "
                            f"word {report.word_index:3d} "
                            f"bit {report.bit_index:2d}")
                        n += 1

                        time.sleep(0.1)  # hold the upset in place for 100ms
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