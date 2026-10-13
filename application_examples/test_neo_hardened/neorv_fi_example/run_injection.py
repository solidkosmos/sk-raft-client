# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""NEORV32 hardening example: fault-injection campaign.

The script uploads the design to the SK-RAFT server and programs the FPGA.
The design under test (DUT) is the NEORV32. The script does one golden
run of CoreMark without a fault, then a campaign of runs. Each run does
these steps:

  1. Reset the DUT and stop its clock at a random cycle.
  2. Inject one random fault into the selected memory type (essential
     bits, BRAM, FF or LUT).
  3. Finish the benchmark.
  4. Compare the CRCs and the UART message with the golden run.

The script writes the results to a CSV file. It writes the UART data of
each run that has a different CRC to a raw-data file.
"""

from __future__ import annotations

import csv
import os
import random
import re
import time

import serial
from skraft import Design, FpgaDevice, SkraftError, SkraftFpga

import bscan_routine_helpers as bscan

# --- User-specific settings: update these for your setup ---
# The address of the SK-RAFT server.
SK_RAFT_SERVER_IP = "127.0.0.1"
# The port of the SK-RAFT server.
SK_RAFT_SERVER_PORT = 50051
# The serial number of the target board.
SERIAL_NUMBER = "210183BFD452A"
# The design files (paths relative to this folder). The script uploads them
# to the server. The Generate Bitstream run of the project from
# create_project.tcl writes the .bit, .ebd and .ll files to IMPL_DIR. Change
# IMPL_DIR if you gave the project another name.
IMPL_DIR    = "../test_neo/test_neo.runs/impl_1"
# Constraints, with HARNESS_PBLOCK
XDC_FILE    = "../hw/xdc/basys3.xdc"
# File names of the design files: <TOP>.bit/.ebd/.ll
TOP         = "neorv32_test_setup_bootloader"
# Pblock of the test harness in the XDC; the campaign never injects into it
HARNESS_PBLOCK = "harness_pblock"
# Campaign results, relative to this folder (created if missing)
RESULTS_DIR = "injection_results"
# The serial port of the UART of the DUT.
UART_PORT = "COM5"
# This value must be equal to BAUD_RATE of the firmware (see README).
UART_BAUD = 500000
# -------------------------------------------------------------

# Cycle counts of the benchmark (clock cycles of the NEORV32)
# The cycles in which the script injects a fault.
BENCHMARK_CYCLES = 8_678_667
# The cycles of one campaign run.
CAMPAIGN_CYCLES = 2 * BENCHMARK_CYCLES
# The cycles of the golden run.
GOLDEN_RUN_CYCLES = 13_000_000
# The largest step count of one U2 write.
MAX_U32 = 0xFFFF_FFFF

# The start value of the CRC of the UART message.
CRC_INIT = 0xE9F5

# U2 values at the end of a run: count at zero, or UART drain sentinel
COUNT_ZERO        = bytes(4)
TX_DRAIN_SENTINEL = bytes([0x00, 0x00, 0xBE, 0xEF])

# Golden run: read the UART until no new byte arrives for UART_QUIET_S
# seconds, for UART_MAX_S seconds at most
UART_QUIET_S = 0.2
UART_MAX_S   = 5.0

# Patterns in the UART output of the DUT
# CoreMark result
CRCFINAL_RE    = re.compile(rb"crcfinal\s*:\s*(0x[0-9a-fA-F]+)")
# Trap/exception report of the runtime environment
EXCEPTION_MARK = b"NEORV32-RTE"
# Correction/parity alert of the hardening handlers
ALERT_MARK     = b"[ALERT]"


def python_crcu8(data: int, crc: int) -> int:
    """Add one byte to the CRC-16. This function uses the same algorithm as
    the CRC hardware on the DUT."""
    for _ in range(8):
        x16  = (data & 1) ^ (crc & 1)
        data >>= 1
        if x16:
            crc = ((crc ^ 0x4002) >> 1) | 0x8000
        else:
            crc = (crc >> 1) & 0x7FFF
    return crc


def crcfinal_of(data: bytes) -> bytes | None:
    """Return the CoreMark crcfinal value in the UART output (bytes), or
    None if there is none."""
    match = CRCFINAL_RE.search(data)
    return match.group(1) if match else None


def pblock_fars(dev: FpgaDevice, pblock_name: str) -> list[int]:
    """Return the frame addresses (FARs) that the named pblock of the XDC
    covers."""
    pblocks = {pblock.name: pblock for pblock in dev.pblocks()}
    if pblock_name not in pblocks:
        raise SystemExit(f"Pblock '{pblock_name}' is not in the XDC. "
                         f"Pblocks found: {sorted(pblocks) or 'none'}")
    fars = set()
    for clause in pblocks[pblock_name].clauses:
        fars.update(entry.far for entry in dev.pblock_by_clause(clause))
    return sorted(fars)


def random_step_start() -> list[int]:
    """Return the step counts of one campaign run, with a random split. The
    sum is CAMPAIGN_CYCLES. The first step count sets the cycle of the
    injection."""
    fs        = random.randint(0, min(BENCHMARK_CYCLES, MAX_U32))
    remaining = CAMPAIGN_CYCLES - fs
    if remaining > MAX_U32:
        return [fs, MAX_U32, remaining - MAX_U32]
    return [fs, remaining]


def first_run_step_start() -> list[int]:
    """Return steps for the golden run (GOLDEN_RUN_CYCLES cycles)."""
    if GOLDEN_RUN_CYCLES <= MAX_U32:
        return [GOLDEN_RUN_CYCLES]
    return [MAX_U32, GOLDEN_RUN_CYCLES - MAX_U32]


def flush_uart(dev: FpgaDevice, ser: serial.Serial) -> None:
    """Stop the DUT output and empty the UART input, so that a run gets only
    its own data."""
    # Root clock on (U3 = 1): it is off after each programming of the FPGA
    bscan.enable_root_clock(dev)
    # Hold the DUT in reset (U1 = 0): the DUT stops sending, also if the
    # previous run crashed and still prints
    bscan.assert_reset(dev)
    # Let the bytes that are still in the USB-UART bridge arrive, then
    # discard them
    time.sleep(0.05)
    ser.reset_input_buffer()


def read_uart_until_quiet(ser: serial.Serial) -> bytearray:
    """Read the UART until no new byte arrives for UART_QUIET_S seconds, or
    for UART_MAX_S seconds at most. Returns the bytes read."""
    data = bytearray()
    start_time = last_byte_time = time.time()
    while time.time() - start_time < UART_MAX_S:
        chunk = ser.read_all()
        if chunk:
            data.extend(chunk)
            last_byte_time = time.time()
        elif time.time() - last_byte_time >= UART_QUIET_S:
            break
        else:
            time.sleep(0.01)
    return data


def run_campaign(dev: FpgaDevice, ser: serial.Serial) -> None:
    """Upload and program the design, do the golden run, then the injection
    campaign."""

    # Give the paths of the design files. The next call uploads them from
    # this computer to the server.
    design = Design(
        bit=f"{IMPL_DIR}/{TOP}.bit",
        ebd=f"{IMPL_DIR}/{TOP}.ebd",
        ll=f"{IMPL_DIR}/{TOP}.ll",
        xdc=XDC_FILE,
    )
    dev.uploadDesignToServer(design)

    # Exclude the frames of the harness pblock (taken from the XDC), so that
    # faults injected there do not disturb the clock-cycle controller
    harness_fars = pblock_fars(dev, HARNESS_PBLOCK)
    dev.exclude_frames(harness_fars)
    print(f"Excluded {len(harness_fars)} frames of pblock '{HARNESS_PBLOCK}'.")

    # Program the FPGA with the uploaded bitstream.
    dev.programFPGA()

    # Markers used to extract the benchmark report from the UART stream
    msg_start_marker = b"TOTAL REPORT:\n"
    msg_end_marker   = b"no HPMs available"

    date = time.strftime("%Y%m%d-%H%M%S")

    # Golden run: run the benchmark without a fault. Its CRC values are
    # the reference values for the campaign runs.
    print("GOLDEN RUN")
    calculated_crc = CRC_INIT

    steps = first_run_step_start()

    # Flush the UART before the run.
    flush_uart(dev, ser)

    # Run the benchmark: reset the DUT and run the first step count. Then
    # run the remaining step counts to the end. One U2 write holds MAX_U32
    # steps at most. Thus send the step counts one after the other.
    if bscan.start_clean_run(dev, steps[0]) == 0:
        for idx in range(len(steps) - 1):
            if bscan.send_steps(dev, steps[idx + 1]) == 0:
                bscan.run_to_end(dev)

    # Read the benchmark output from the UART, until it is quiet.
    data = read_uart_until_quiet(ser)
    ser.reset_input_buffer()

    # Get the reference values from the report: the message CRC, the
    # calculated CRC, the hardware CRC and crcfinal
    final_msg_bytes = b""
    if msg_start_marker in data and msg_end_marker in data:
        final_msg_bytes = (data.split(msg_start_marker)[1]
                           .split(msg_end_marker)[0])

    golden_msg_crc = b""
    if b"MSG CRC : " in data:
        golden_msg_crc = (data.split(b"MSG CRC : ")[1]
                          .strip().split()[0])[2:7]
    for byte in final_msg_bytes:
        calculated_crc = python_crcu8(byte, calculated_crc)
    golden_calculated_crc = calculated_crc
    golden_hw_crc         = bscan.read_crc(dev).hex()
    golden_crcfinal       = crcfinal_of(data)

    print(f"Golden CRCs  MSG: {golden_msg_crc}  "
          f"CALC: {golden_calculated_crc:04x}  HW: {golden_hw_crc}  "
          f"crcfinal: {golden_crcfinal}")
    if golden_crcfinal is None:
        raise SystemExit("The golden run has no crcfinal line in its UART "
                         "output.")

    # Injection campaign configuration
    # Set target_idx to select the target memory type for this campaign
    categories  = ["EBITS", "BRAM", "FF", "LUT"]
    run_counts  = [14000, 14000, 14000, 14000]
    # 0=EBITS (essential CRAM bits)  1=BRAM  2=FF  3=LUT
    target_idx = 0

    category_list              = [False, False, False, False]
    category_list[target_idx]  = True
    injection_type             = categories[target_idx]

    csv_filename      = (f"{RESULTS_DIR}/csvs/csvs_{injection_type}/"
                         f"injection_results_{injection_type}_{date}.csv")
    raw_data_filename = (f"{RESULTS_DIR}/raw_data/raw_data_{injection_type}/"
                         f"injection_raw_data_{injection_type}_{date}.txt")

    # Create the output directories if they do not exist.
    os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
    os.makedirs(os.path.dirname(raw_data_filename), exist_ok=True)

    print(f"Target: {injection_type}  Runs: {run_counts[target_idx]}")
    print(f"CSV: {csv_filename}")

    observed_error = restarts = done = not_done = 0
    hw_error = uart_error = corrections = 0
    # Errors by kind (ERROR = exception, DETECTED = flagged by the
    # hardening, SDC = silent, HUNG)
    status_counts = {"ERROR": 0, "DETECTED": 0, "SDC": 0, "HUNG": 0}
    data = bytearray()

    with open(csv_filename, mode='w', newline='') as csv_file:

        writer = csv.writer(csv_file)
        writer.writerow(["RUN #", "FAR_Address", "Word_Index", "Bit_Index",
                         "Status"])
        for run in range(run_counts[target_idx]):

            calculated_crc = CRC_INIT
            # Random split of the benchmark cycles. The script injects the
            # fault after steps[0] cycles.
            steps = random_step_start()

            # Inject the fault: reset the DUT, run to a random cycle, inject,
            # then finish the benchmark. If a step does not go correctly,
            # program the FPGA again and do the run again. Thus each run has
            # one fault.
            retry = True
            while retry:
                # Flush the UART before each attempt.
                flush_uart(dev, ser)
                flag, inject_report, bscan_counter = bscan.start_run_n_inject(
                    dev, steps[0], *category_list
                )

                if flag != 0:
                    print(f"[ERROR] r-{run+1}: injection failed, "
                          f"reprogramming.")
                    dev.programFPGA()
                    restarts += 1
                    continue

                # Run the remaining step counts to the end of the benchmark.
                for idx in range(len(steps) - 1):
                    if bscan.send_steps(dev, steps[idx + 1]) == 0:
                        bscan_counter = bscan.run_to_end(dev)
                        retry = False
                    else:
                        print(f"[ERROR] r-{run+1}: step send failed, "
                              f"reprogramming.")
                        dev.programFPGA()
                        retry = True
                        restarts += 1
                        break

                # At the end of a correct run, the counter shows zero or the
                # UART drain sentinel. Another value shows a failed run. Then
                # program the FPGA and do the run again.
                if bscan_counter not in (TX_DRAIN_SENTINEL, COUNT_ZERO):
                    print(f"[ERROR] r-{run+1}: unexpected counter "
                          f"{bscan_counter}, reprogramming.")
                    dev.programFPGA()
                    retry = True
                    restarts += 1

            # Read the UART bytes that remain, for 0.5 s at most. The
            # classification below uses these bytes.
            start_time = time.time()
            while ser.in_waiting:
                chunk = ser.read_all()
                data.extend(chunk)
                if not chunk or time.time() - start_time > 0.5:
                    break
            ser.reset_input_buffer()

            # Inject a fault at the same bit again. This sets the bit to its
            # correct value, so the next run starts with a correct
            # configuration.
            dev.inject_at(inject_report.far, inject_report.word_index,
                          inject_report.bit_index, inject_report.target)

            # Parse the benchmark report from the UART buffer
            final_msg_bytes = msg_crc = b""
            if msg_start_marker in data and msg_end_marker in data:
                try:
                    final_msg_bytes = (data.split(msg_start_marker)[1]
                                       .split(msg_end_marker)[0])
                except Exception:
                    pass
                try:
                    if b"MSG CRC : " in data:
                        msg_crc = (data.split(b"MSG CRC : ")[1]
                                   .strip().split()[0])[2:7]
                except Exception:
                    pass

            for byte in final_msg_bytes:
                calculated_crc = python_crcu8(byte, calculated_crc)
            hw_crc = bscan.read_crc(dev).hex()

            # If hw_crc starts with "8", the DUT finished the benchmark.
            finished      = hw_crc[0] == "8"
            crc_deviated  = (msg_crc        != golden_msg_crc        and
                             hw_crc         != golden_hw_crc         and
                             calculated_crc != golden_calculated_crc)


            # All three CRCs deviate: classify the run by the message it
            # sent
            #   exception in the message -> ERROR
            #     (the runtime reported a trap)
            #   ALERT and crcfinal correct -> no error
            #     (the hardening handled the fault)
            #   ALERT and crcfinal wrong or missing -> DETECTED
            #     (error, flagged by the hardening)
            #   no ALERT and crcfinal wrong or missing -> SDC
            #     (silent data corruption)
            #   otherwise (crcfinal correct, only other lines changed)
            #     -> no error
            error_kind = None
            reason     = ""
            if crc_deviated:
                crcfinal    = crcfinal_of(data)
                crcfinal_ok = crcfinal == golden_crcfinal
                alert       = ALERT_MARK in data
                if EXCEPTION_MARK in data:
                    error_kind, reason = "ERROR", "exception"
                elif alert and crcfinal_ok:
                    reason = "ALERT, crcfinal correct"
                elif not crcfinal_ok:
                    error_kind = "DETECTED" if alert else "SDC"
                    found = crcfinal.decode() if crcfinal else "missing"
                    reason     = (f"{'ALERT, ' if alert else 'no ALERT, '}"
                                  f"crcfinal {found} "
                                  f"(golden {golden_crcfinal.decode()})")
                else:
                    reason = "message changed, crcfinal correct"

            # An error where the DUT did not finish is HUNG.
            status = (None if error_kind is None
                      else error_kind if finished else "HUNG")

            # The CRCs of this run next to the golden CRCs
            golden_msg = golden_msg_crc.decode(errors="replace")
            crc_line = (f"MSG CRC: {msg_crc.decode(errors='replace')} "
                        f"(golden {golden_msg})  "
                        f"CALC CRC: {calculated_crc:04x} "
                        f"(golden {golden_calculated_crc:04x})  "
                        f"HW CRC: {hw_crc} (golden {golden_hw_crc})")
            any_deviation = (msg_crc        != golden_msg_crc or
                             hw_crc         != golden_hw_crc  or
                             calculated_crc != golden_calculated_crc)

            # If one or more CRCs deviate: print the CRCs, and save the UART
            # data of the run with a RUN tag above it
            if any_deviation:
                label = status or "MISMATCH"
                why = reason + "  " if reason else ""
                print(f"[{label}] r-{run+1}: {why}{crc_line}")
                with open(raw_data_filename, mode='ab') as raw_data_file:
                    raw_data_file.write(
                        f"\n---------------- RUN {run+1} "
                        f"----------------\n".encode())
                    raw_data_file.write(
                        f"{label}  {why}{crc_line}\n".encode())
                    raw_data_file.write(
                        f"INJECTION CYCLE: {steps[0]}  "
                        f"FAR: {inject_report.far}  "
                        f"WORD: {inject_report.word_index}  "
                        f"BIT: {inject_report.bit_index}  "
                        f"NET: {inject_report.net_name}\n".encode())
                    raw_data_file.write(data)

            # Count the runs with a correction message (BRAM and FF
            # campaigns only). This count shows the ECC hardening in DMEM,
            # the register file and the execute engine. Do not subtract
            # these runs from the AVF. A run with a correction and a correct
            # crcfinal is not an error.
            if categories[target_idx] in ("BRAM", "FF"):
                corrections += 1 if b"correction" in data else 0

            if status:
                observed_error += 1
                status_counts[status] += 1
                writer.writerow([run+1, inject_report.far,
                                 inject_report.word_index,
                                 inject_report.bit_index, status])
                if not finished:
                    dev.programFPGA()
                    not_done += 1
                else:
                    dev.programFPGA()
                    done += 1
            else:
                # Run without an error: count the small differences of the
                # hardware CRC and of the UART CRCs separately. Do not count
                # them for a run where all three CRCs are different. The
                # classification above examines that run.
                if not crc_deviated:
                    if golden_hw_crc != hw_crc:
                        hw_error += 1
                    if (golden_calculated_crc != calculated_crc
                            and msg_crc != golden_msg_crc):
                        uart_error += 1
                done += 1

            data = bytearray()

        avf = observed_error / (run + 1) * 100
        writer.writerow(["OBSERVED ERROR RATE:",
                         f"Observed errors: {observed_error}",
                         f"Total runs: {run+1}",
                         f"AVF: {avf:.2f}",
                         f"Corrections : {corrections}",
                         *(f"{kind}: {count}"
                           for kind, count in status_counts.items())])

    print(f"\nCompleted: {run+1}  Done: {done}  Hung: {not_done}  "
          f"Restarts: {restarts}")
    print(f"AVF: {avf:.2f}%")
    print("Errors by kind: " + "  ".join(
        f"{kind}: {count}" for kind, count in status_counts.items()))
    print(f"HW CRC mismatches: {hw_error}  UART mismatches: {uart_error}")
    if categories[target_idx] in ("BRAM", "FF"):
        print(f"Corrected faults : {corrections}")


def main() -> None:
    """Connect to the server, attach the device, open the UART and run the
    campaign. The with statements close the UART port, release the device
    and close the server connection. They also do this if an error or
    Ctrl+C stops the script. Thus the server and the device stay usable
    for the next run."""
    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                # Open the UART connection to the DUT.
                with serial.Serial(port=UART_PORT, baudrate=UART_BAUD,
                                   bytesize=8, timeout=0.1) as ser:
                    run_campaign(dev, ser)
    except SkraftError as e:
        print(f"NEORV32 injection campaign failed: {e}")
        return
    except serial.SerialException as e:
        print(f"UART error: {e}")
        return
    except KeyboardInterrupt:
        # An injected fault can remain in the FPGA. Program the FPGA again
        # before you use the design.
        print("\nInterrupted")
        return

    print("NEORV32 injection campaign done.")


if __name__ == "__main__":
    main()
