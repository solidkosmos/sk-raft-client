import time
import serial
import csv
import random

import bscan_helpers as bscan
from skraft import SkraftFpga, DesignFiles, ServerPath

# --- User-specific settings: update these for your setup ---
DESIGN_DIR  = "/path/to/designs/neorv"               # directory on the SK-RAFT server holding the bit/ebd/ll files
RESULTS_DIR = "/path/to/injection_results"           # directory on this machine to write campaign results to
UART_PORT   = "/dev/ttyUSBx"                         # serial port of the DUT's UART
# -------------------------------------------------------------


# CRC-16 algorithm matching the hardware implementation on the DUT
def python_crcu8(data: int, crc: int) -> int:
    for _ in range(8):
        x16  = (data & 1) ^ (crc & 1)
        data >>= 1
        if x16:
            crc = ((crc ^ 0x4002) >> 1) | 0x8000
        else:
            crc = (crc >> 1) & 0x7FFF
    return crc


def random_step_start() -> list:
    """Return a 2-element step list that sums to total_cycles with a random split.
    The split point determines when the fault is injected during the benchmark."""
    total_cycles    = 8678667 * 2
    operating_cycles = 8678667
    max_u32          = 4294967295
    fs        = random.randint(0, min(operating_cycles, max_u32))
    remaining = total_cycles - fs
    if remaining > max_u32:
        return [fs, max_u32, remaining - max_u32]
    return [fs, remaining]


def first_run_step_start() -> list:
    """Return steps for the golden run (fixed 13 000 000 cycle duration)."""
    total   = 13_000_000
    max_u32 = 4_294_967_295
    if total <= max_u32:
        return [total]
    return [max_u32, total - max_u32]


if __name__ == "__main__":

    # Connect to the SK-RAFT server and reserve the target device
    client = SkraftFpga.connect("127.0.0.1", 50052)
    dev    = client.attach("XC7A35T-1CPG236C", "FT2232H")

    # Load design files (paths are resolved on the SK-RAFT server)
    dev.load(DesignFiles(
        bitstream=ServerPath(f"{DESIGN_DIR}/neorv32_test_setup_bootloader.bit"),
        ebd=ServerPath(f"{DESIGN_DIR}/neorv32_test_setup_bootloader.ebd"),
        ll=ServerPath(f"{DESIGN_DIR}/neorv32_test_setup_bootloader.ll"),
    ))

    # Exclude frames belonging to the clock-cycle controller partial reconfiguration block
    # so that faults injected there do not disturb the timing infrastructure
    farExcluded = client.extract_fars_from_bitstream(
        ServerPath(f"{DESIGN_DIR}/neorv32_test_setup_bootloader_pblock_clk_cyc_ctrlr_partial.bit")
    )
    dev.exclude_frames(farExcluded)
    dev.exclude_frames([0x00400a9f, 0x00400a1f])

    dev.program()

    # Open UART connection to the DUT
    ser = serial.Serial(port=UART_PORT, baudrate=500000, bytesize=8, timeout=0.1)

    # Markers used to extract the benchmark report from the UART stream
    msg_start_marker = b"TOTAL REPORT:\n"
    msg_end_marker   = b"no HPMs available"

    date = time.strftime("%Y%m%d-%H%M%S")

    # Golden run: execute the benchmark without fault injection to capture
    # the reference CRC values that correct operation should produce
    print("GOLDEN RUN")
    calculated_crc = 0xe9f5
    data           = bytearray()

    steps = first_run_step_start()

    if bscan.start_clean_run(dev, steps[0]) == 0:
        for idx in range(len(steps) - 1):
            if bscan.send_steps(dev, steps[idx + 1]) == 0:
                bscan.run_to_end_and_read(dev, ser)

    while ser.in_waiting:
        chunk = ser.read_all()
        data.extend(chunk)
        if not chunk:
            break
    ser.reset_input_buffer()

    # Extract the report body and compute all three CRC reference values
    final_msg_bytes = b""
    if msg_start_marker in data and msg_end_marker in data:
        final_msg_bytes = data.split(msg_start_marker)[1].split(msg_end_marker)[0]

    golden_msg_crc = (data.split(b"MSG CRC : ")[1].strip().split()[0])[2:7] if b"MSG CRC : " in data else b""
    for byte in final_msg_bytes:
        calculated_crc = python_crcu8(byte, calculated_crc)
    golden_calculated_crc = calculated_crc
    golden_hw_crc         = bscan.read_crc(dev).hex()

    print(f"Golden CRCs  MSG: {golden_msg_crc}  CALC: {golden_calculated_crc:04x}  HW: {golden_hw_crc}")

    # Injection campaign configuration
    # Set one flag to True to select the target memory type for this run
    categories  = ["CRAM", "BRAM", "FF", "LUT"]
    run_counts  = [14000, 14000, 14000, 14000]
    target_idx  = 1   # 0=CRAM  1=BRAM  2=FF  3=LUT

    category_list              = [False, False, False, False]
    category_list[target_idx]  = True
    injection_type             = categories[target_idx]

    csv_filename      = f"{RESULTS_DIR}/csvs/csvs_{injection_type}/injection_results_{injection_type}_{date}.csv"
    raw_data_filename = f"{RESULTS_DIR}/raw_data/raw_data_{injection_type}/injection_raw_data_{injection_type}_{date}.txt"

    print(f"Target: {injection_type}  Runs: {run_counts[target_idx]}")
    print(f"CSV: {csv_filename}")

    observed_error = restarts = done = not_done = hw_error = uart_error = corrections = 0
    data = bytearray()

    with open(csv_filename, mode='w', newline='') as csv_file, \
         open(raw_data_filename, mode='ab') as raw_data_file:

        writer = csv.writer(csv_file)
        writer.writerow(["RUN #", "FAR_Address", "Word_Index", "Bit_Index", "Status"])

        for run in range(run_counts[target_idx]):

            calculated_crc = 0xe9f5
            ser.reset_input_buffer()
            steps = random_step_start()

            # Inject fault: reset DUT, run to a random cycle, inject, then finish the benchmark
            retry = True
            while retry:
                flag, inject_report, bscan_counter = bscan.start_run_n_inject(
                    dev, steps[0], *category_list
                )

                if flag != 0:
                    print(f"[ERROR] r-{run+1}: injection failed, reprogramming.")
                    dev.program()
                    restarts += 1
                    continue

                for idx in range(len(steps) - 1):
                    if bscan.send_steps(dev, steps[idx + 1]) == 0:
                        bscan_counter = bscan.run_to_end_and_read(dev, ser)
                        retry = False
                    else:
                        print(f"[ERROR] r-{run+1}: step send failed, reprogramming.")
                        dev.program()
                        retry = True
                        break

                # Validate that the counter reached an expected sentinel value
                if bscan_counter not in (bytes([0x00, 0x00, 0xbe, 0xef]),
                                         bytes([0x00, 0x00, 0x00, 0x00])):
                    print(f"[ERROR] r-{run+1}: unexpected counter {bscan_counter}, reprogramming.")
                    dev.program()
                    retry = True
                    restarts += 1

            # Drain any remaining UART bytes
            start_time = time.time()
            while ser.in_waiting:
                chunk = ser.read_all()
                data.extend(chunk)
                if not chunk or time.time() - start_time > 0.5:
                    break
            ser.reset_input_buffer()

            if not retry:
                # Reverse the injected fault by flipping the same bit back
                dev.inject_at(inject_report.far, inject_report.word_index,
                              inject_report.bit_index, inject_report.target)

                # Parse the benchmark report from the UART buffer
                final_msg_bytes = msg_crc = b""
                if msg_start_marker in data and msg_end_marker in data:
                    try:
                        final_msg_bytes = data.split(msg_start_marker)[1].split(msg_end_marker)[0]
                    except Exception:
                        pass
                    try:
                        if b"MSG CRC : " in data:
                            msg_crc = (data.split(b"MSG CRC : ")[1].strip().split()[0])[2:7]
                    except Exception:
                        pass

                for byte in final_msg_bytes:
                    calculated_crc = python_crcu8(byte, calculated_crc)
                hw_crc = bscan.read_crc(dev).hex()

                # A leading "8" in hw_crc means the processor completed successfully
                finished      = hw_crc[0] == "8"
                crc_deviated  = (msg_crc        != golden_msg_crc        and
                                 hw_crc         != golden_hw_crc         and
                                 calculated_crc != golden_calculated_crc)

                status = "ERROR" if finished and crc_deviated else "HUNG" if not finished and crc_deviated else None
                
                # Add to corrections to subtract in the final AVF calculation, 
                # only for BRAMS and FFs to show ECC hardening in DMEM, REG File and EXE ENGINE 
                if injection_type in ("BRAM", "FF"):
                    corrections += 1 if b"correction" in data else 0
                
                if status:
                    print(f"[{status}] r-{run+1}: CRC deviation detected.")
                    observed_error += 1
                    writer.writerow([run+1, inject_report.far, inject_report.word_index,
                                     inject_report.bit_index, status])
                    raw_data_file.write(f"\n\n---------------- RUN {run+1} ----------------n".encode())
                    raw_data_file.write(data)
                    raw_data_file.write(f"\nHW CRC: {hw_crc}  INJECTION CYCLE: {steps[0]}\n".encode())
                    if not finished:
                        dev.program()
                        not_done += 1
                    else:
                        dev.program()
                        done += 1
                else:
                    # Clean run: track any minor comms discrepancies separately
                    if golden_hw_crc != hw_crc:
                        hw_error += 1
                    if golden_calculated_crc != calculated_crc and msg_crc != golden_msg_crc:
                        uart_error += 1
                    done += 1

                data = bytearray()

            else:
                print(f"[RESTART] r-{run+1}: discarding run.")

        avf = observed_error - corrections / (run + 1) * 100
        writer.writerow(["OBSERVED ERROR RATE:",
                         f"Observed errors: {observed_error}",
                         f"Total runs: {run+1}",
                         f"AVF: {avf:.2f}",
                         f"Corrections : {corrections}"])

    print(f"\nCompleted: {run+1}  Done: {done}  Hung: {not_done}  Restarts: {restarts}")
    print(f"AVF: {avf:.2f}%")
    print(f"HW CRC mismatches: {hw_error}  UART mismatches: {uart_error}")
    print(f"Corrected faults : {corrections}") if injection_type in ("BRAM", "FF") else None
    if ser.is_open:
        ser.close()

    dev.release()
    client.disconnect()
