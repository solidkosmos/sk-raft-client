"""Example 2 - single-bit upsets against simplex vs. TMR adders.

Programs a bitstream and prints each pblock's essential-bit count, then
runs single-bit-upset trials until Enter is pressed. Each trial injects
one random essential bit into each pblock (simplex and TMR), drives 100
random operand pairs through both adders - enough to exercise the
circuit, not an exhaustive test - and marks an adder as failed if any of
its results was wrong. Both bits are then reverted. A status line keeps
each adder's VF (the fraction of trials in which it failed) up to date,
and the final counts are printed at the end.

The TMR adder can still fail: an upset that lands in its voter defeats
the triplication.

"""

import os
import random
import threading
import time

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga, TargetMemory

# --------------------------------------------------------------------------- #
# Configuration. Edit these to match your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "210248781184"

# The design used throughout: simplex and TMR adders on a Basys-3.
# uploadDesignToServer() sends the files, 
# and the server stores them under the same relative path.
design = Design(
    bit="design_files/bscan_adder_top.bit",
    ebd="design_files/bscan_adder_top.ebd",
    xdc="design_files/board.xdc",
)

# The two pblocks under test, as named in the XDC
PBLOCK_SIMPLEX = "pblock_sngl_add"
PBLOCK_TMR = "pblock_tmr_add"

# Every trial below is reverted right after checking (non-accumulative);
# trials keep going until Enter is pressed.

# The design's op_len generic. Widens USER1 and
# USER2/USER3 with the carry bit,
# if the design is rebuilt with a different value
OP_LEN = 4

# Each operand pair packs as (operand B << OP_LEN) | operand A. 
PAIR_LEN = OP_LEN * 2

RESULT_MASK = (1 << (OP_LEN + 1)) - 1
OP_MASK = (1 << OP_LEN) - 1

# BSCAN registers: (USER number, width in bits)
USER_OPERANDS = BscanPrimitive(1, PAIR_LEN)
USER_SIMPLEX_RESULT = BscanPrimitive(2, OP_LEN + 1)
USER_TMR_RESULT = BscanPrimitive(3, OP_LEN + 1)

# Watches for the Enter key in the background, so it doesn't block the
# injection loop below. Press Enter any time to end the trials.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# Green/red pass-fail labels. os.system("") turns on ANSI colours in the
# classic Windows console; other terminals ignore it.
os.system("")
GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"


def verdict(ok: bool) -> str:
    return f"{GREEN}Correct{RESET}" if ok else f"{RED}Wrong{RESET}  "


# Load one operand pair into both adders (USER1)
def set_operands(dev, a: int, b: int) -> None:
    # SK-RAFT: pack and write the operand pair
    dev.write_bscan(USER_OPERANDS, (b << OP_LEN) | a)


# Read the simplex adder's result (USER2)
def read_simplex_result(dev) -> int:
    # SK-RAFT: read and unpack the result
    data = dev.read_bscan(USER_SIMPLEX_RESULT)
    return int.from_bytes(data, "big") & RESULT_MASK


# Read the TMR adder's result (USER3)
def read_tmr_result(dev) -> int:
    # SK-RAFT: read and unpack the result
    data = dev.read_bscan(USER_TMR_RESULT)
    return int.from_bytes(data, "big") & RESULT_MASK


def main() -> None:
    try:
        # SK-RAFT: open the connection, then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                # SK-RAFT: upload the bitstream, EBD and XDC, then program.
                dev.uploadDesignToServer(design)
                dev.programFPGA()
                print(f"Programmed {DEVICE}.")
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
                    # Inject one random essential-bit fault in each adder
                    report_sim = dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                                                   pblock=PBLOCK_SIMPLEX)
                    report_tmr = dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                                                   pblock=PBLOCK_TMR)
                    
                    # 100 random inputs with the same upset 
                    # to exercise both circuits adequately.
                    # If at least one of these results in an error, 
                    # +1 error for the erroneous module
                    for _ in range(100):
                        a = random.randint(0, OP_MASK)
                        b = random.randint(0, OP_MASK)
                        # Precompute the result
                        expected = (a + b) & RESULT_MASK
                        # Write them to the BSCAN channel
                        set_operands(dev, a, b)
                        # Read the result of each adder
                        simplex_result = read_simplex_result(dev)
                        tmr_result = read_tmr_result(dev)
                        # Set the status
                        if simplex_result != expected:
                            simplex_ok = False
                        if tmr_result != expected:
                            tmr_ok = False
                    # Check which of the adders were erroneous
                    if not simplex_ok:
                        simplex_error += 1
                    if not tmr_ok:
                        tmr_error += 1
                    # Revert the injection on both adders. Essential bits
                    # are CRAM bits, so flipping them back uses the plain
                    # CRAM target.
                    if True: # Make False to not correct injected faults,
                              # i.e. accumulative fault injection 
                        dev.inject_at(report_sim.far, report_sim.word_index,
                                    report_sim.bit_index, TargetMemory.CRAM)
                        dev.inject_at(report_tmr.far, report_tmr.word_index,
                                    report_tmr.bit_index, TargetMemory.CRAM)
                    n += 1
                    # One status line, rewritten every trial: this trial's
                    # result per adder (green/red) and the running VFs
                    print(f"\r# of trials = {n}  ||  "
                          f"Simplex {verdict(simplex_ok)} "
                          f"VF = {simplex_error}/{n} "
                          f"({simplex_error/n * 100:.2f}%)  |  "
                          f"TMR {verdict(tmr_ok)} "
                          f"VF = {tmr_error}/{n} "
                          f"({tmr_error/n * 100:.2f}%)   ",
                          end="", flush=True)

                # Enter pressed before the first trial finished
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
