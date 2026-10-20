# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example 2: single-bit upsets in a simplex adder and a TMR adder.

The script programs the FPGA with the bitstream and prints the number of
essential bits in each pblock. Then the script runs single-bit upset
trials until you press Enter. Each trial flips one random essential bit
in each pblock
(simplex and TMR). Then the trial applies 100 random operand pairs to
both adders. This number of pairs is enough to test the circuit, but the
test is not exhaustive. If one or more results of an adder are wrong, the
trial marks that adder as failed.

After each trial, the script corrects both bits. A status line shows the
current VF of each adder (the fraction of trials in which the adder
failed). At the end, the script prints the final counts.

The TMR adder can still fail: if an upset hits the voter, the
triplication does not protect the adder.

"""

import os
import random
import threading
import time

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BA251CA"

# The design for all trials: a simplex adder and a TMR adder.
# The script gives all three files at the start:
#   The bitstream (.bit): to program the device.
#   The EBD file (.ebd): to find which bits are essential.
#   The XDC file (.xdc): to find the pblocks.
# uploadDesignToServer() sends the files to the server. The client sends
# only the file name of each path, not the directory.
#
# BOARD is the board of your target device: "basys3" or "zedboard", or
# the name of your own board (see hw/README.md). The script reads the
# design files from hw/design_examples/<BOARD>/bscan_adder_top/. Extract
# design_examples.zip there, or build the design with create_project.tcl.
# The paths are relative to src/. Run the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/bscan_adder_top"

design = Design(
    bit=f"{DESIGN_DIR}/bscan_adder_top.bit",
    ebd=f"{DESIGN_DIR}/bscan_adder_top.ebd",
    xdc=f"{DESIGN_DIR}/board.xdc",
)

# The two pblocks to test, with the names from the XDC file.
PBLOCK_SIMPLEX = "pblock_sngl_add"
PBLOCK_TMR = "pblock_tmr_add"

# The script corrects the upsets of each trial immediately after the check
# (non-accumulative). The trials continue until you press Enter.

# The op_len generic of the design. OP_LEN sets the width of USER1 and
# of USER2/USER3 (with the carry bit). If you build the design again
# with a different value, set OP_LEN to the same value.
OP_LEN = 4

# The script packs each operand pair as (operand B << OP_LEN) | operand A.
PAIR_LEN = OP_LEN * 2

RESULT_MASK = (1 << (OP_LEN + 1)) - 1
OP_MASK = (1 << OP_LEN) - 1

# BSCAN registers: (USER number, width in bits)
USER_OPERANDS = BscanPrimitive(1, PAIR_LEN)
USER_SIMPLEX_RESULT = BscanPrimitive(2, OP_LEN + 1)
USER_TMR_RESULT = BscanPrimitive(3, OP_LEN + 1)

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop the
# trials.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# Green/red pass/fail labels. os.system("") makes the classic Windows
# console show ANSI colours. Other terminals ignore this call.
os.system("")
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"


def verdict(ok: bool) -> str:
    return f"{GREEN}Correct{RESET}" if ok else f"{RED}Wrong{RESET}  "


# Write one operand pair to both adders (USER1).
def set_operands(dev, a: int, b: int) -> None:
    # SK-RAFT: write the packed operand pair.
    dev.write_bscan(USER_OPERANDS, (b << OP_LEN) | a)


# Read the result of the simplex adder (USER2).
def read_simplex_result(dev) -> int:
    # SK-RAFT: read the result. Then unpack it.
    data = dev.read_bscan(USER_SIMPLEX_RESULT)
    return int.from_bytes(data, "big") & RESULT_MASK


# Read the result of the TMR adder (USER3).
def read_tmr_result(dev) -> int:
    # SK-RAFT: read the result. Then unpack it.
    data = dev.read_bscan(USER_TMR_RESULT)
    return int.from_bytes(data, "big") & RESULT_MASK


def main() -> None:
    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                # Setup the SEED for deterministic behaviour. 
                dev.configure_seed(0)

                # SK-RAFT: upload the bitstream, EBD file and XDC file.
                # Then program the FPGA.
                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"Programmed {SERIAL_NUMBER}.")
                simplex_ebits = dev.bit_count(TargetMemory.ESSENTIAL_CRAM, 
                                              pblock=PBLOCK_SIMPLEX)
                tmr_ebits = dev.bit_count(TargetMemory.ESSENTIAL_CRAM, 
                                          pblock=PBLOCK_TMR)
                print("Number of Essential Bits in:")
                print(f"Simplex Adder = {simplex_ebits} | "
                      f"TMR Adder = {tmr_ebits}")
                print(f"Press Enter to move on.")
                print("-" * 80)
                print("Vulnerability Factor (VF) = observable errors / "
                      "injected faults")
                watch_for_enter()
                simplex_error = 0
                tmr_error = 0
                n = 0
                while True:
                    if stop.is_set():
                        break
                    simplex_ok = True
                    tmr_ok = True
                    # Inject one random upset into an essential bit of each
                    # adder.
                    report_sim = dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                                                   pblock=PBLOCK_SIMPLEX)
                    report_tmr = dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                                                   pblock=PBLOCK_TMR)

                    # Apply 100 random operand pairs with the same upset in
                    # place. This number is enough to test both circuits. If
                    # one or more operand pairs give an error, add 1 to the
                    # error count of the adder that failed.
                    for _ in range(100):
                        a = random.randint(0, OP_MASK)
                        b = random.randint(0, OP_MASK)
                        # Calculate the expected result.
                        expected = (a + b) & RESULT_MASK
                        # Write the operands to BSCAN register USER1.
                        set_operands(dev, a, b)
                        # Read the result of each adder.
                        simplex_result = read_simplex_result(dev)
                        tmr_result = read_tmr_result(dev)
                        # Set the pass/fail status of each adder. One wrong
                        # result is sufficient to mark the adder as failed for
                        # this trial.
                        if simplex_result != expected:
                            simplex_ok = False
                        if tmr_result != expected:
                            tmr_ok = False
                    # Add 1 to the error count of each adder that failed. The
                    # count grows by 1 for each trial at most. Thus, VF is a
                    # fraction of trials, not of operand pairs.
                    if not simplex_ok:
                        simplex_error += 1
                    if not tmr_ok:
                        tmr_error += 1
                    # Correct the upset in both adders. Essential bits are
                    # CRAM bits. Thus, use the plain CRAM target to flip
                    # them again.
                    # Set to False to keep the injected upsets
                    # (accumulative fault injection).
                    if True:
                        dev.inject_at(report_sim.far, report_sim.word_index,
                                    report_sim.bit_index, TargetMemory.CRAM)
                        dev.inject_at(report_tmr.far, report_tmr.word_index,
                                    report_tmr.bit_index, TargetMemory.CRAM)
                    n += 1
                    # After each trial, the script writes the status line again
                    # over the same line (\r). The line shows the result of
                    # each adder for this trial (green/red) and the current
                    # VFs.
                    print(f"\r# of trials = {n}  ||  "
                          f"Simplex {verdict(simplex_ok)} "
                          f"VF = {simplex_error}/{n} "
                          f"({simplex_error/n * 100:.2f}%)  |  "
                          f"TMR {verdict(tmr_ok)} "
                          f"VF = {tmr_error}/{n} "
                          f"({tmr_error/n * 100:.2f}%)   ",
                          end="", flush=True)

                # You pressed Enter before the first trial started.
                if n == 0:
                    print("\nNo trials completed.")
                    return
                print(f"\n{simplex_error} simplex, "
                      f"{tmr_error} tmr errors in {n} trials.")
                print(f"Final Simplex Adder VF = {simplex_error}/{n} "
                      f"({simplex_error/n * 100:.2f}%)")
                print(f"Final TMR Adder VF     = {tmr_error}/{n} "
                      f"({tmr_error/n * 100:.2f}%)")

                
    except SkraftError as e:
        print(f"Example 2 failed: {e}")
        return
    except KeyboardInterrupt:
        print(f"Interrupted")
        return

    print(f"Example 2 done.")


if __name__ == "__main__":
    main()
