# NEORV32 fault-injection campaign

`run_injection.py` runs a fault-injection campaign on the NEORV32 hardening
design. It measures the observed error rate (AVF) against a golden run.
`bscan_routine_helpers.py` has the BSCAN register access (reset, step count,
root clock, CRC read).

## The calls of the example

| Function | Calls |
| --- | --- |
| Connection | `SkraftFpga.connect()` and `client.attach()`, in `with` statements that release the device and close the connection |
| Design | `Design` (`.bit`, `.ebd`, `.ll`, `.xdc`), `dev.uploadDesignToServer()` and `dev.programFPGA(design)` |
| Pblock exclusion | `exclude_pblock` of `dev.inject_random()`: SK-RAFT does not inject into the harness pblock |
| BSCAN | `BscanPrimitive`, `dev.write_bscan()` and `dev.read_bscan()` |
| Fault injection | `TargetMemory` (essential bits, BRAM, FF, LUTRAM), `dev.inject_random()`, and `dev.inject_at()` to flip the bit back after the run |

## Run the example

Build the design first. Refer to the [README of the example](../README.md).
The script reads the `.bit`, `.ebd` and `.ll` files from
`../test_neo/test_neo.runs/impl_1/` (`IMPL_DIR`), and the XDC from
`../hw/xdc/basys3.xdc`. Set the constants at the top of the script, then run
the script from this folder:

```bash
pip install ../../../api/python pyserial
python run_injection.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `SERIAL_NUMBER` | `"210183BFD452A"` | The serial number of the board. `get_devices()` gives the connected boards. |
| `UART_PORT` | `"COM5"` | The serial port of the UART of the board. |
| `TARGET` | `"EBITS"` | The memory type of the campaign: `"EBITS"` (essential CRAM bits), `"BRAM"`, `"FF"` or `"LUT"`. |
| `RUNS` | `200` | The number of runs. |
| `PROGRESS_EVERY` | `25` | The script prints a progress line after this number of runs. |

`UART_BAUD` (500000) must be equal to the baud rate of the firmware.

### Run time

On the Basys 3, the attach, the programming and the golden run take about
1.5 min. Then one run takes about 1.8 s (`TARGET = "EBITS"`). The 200 runs of
the default take about 6 min. A statistically useful AVF needs thousands of
runs: for example, 14000 runs take about 7 h.

The script prints a progress line after each `PROGRESS_EVERY` runs, with the
errors, the AVF and the time that is left. It prints a line for each run with
a CRC difference (refer to "Result").

### Stop the campaign

Press Ctrl+C at any time. The script stops at once, and prints and saves the
results of the runs that completed. It does not count the run that Ctrl+C
stopped. That run can leave an injected fault in the
FPGA: program the FPGA again before you use the design.

The exit code is 0 when the campaign is done, 1 on an error and 130 after
Ctrl+C.

## Result

The script compares each run with the golden run on three CRCs: the CRC in
the UART message, the CRC that the script calculates from the message, and the
hardware CRC (USER1). If all three CRCs are different, the message gives the
status:

| Status | Message |
| --- | --- |
| `ERROR` | An exception report of the runtime (`NEORV32-RTE`) |
| `DETECTED` | An `[ALERT]` and a wrong or missing `crcfinal` |
| `SDC` | No `[ALERT]`, and a wrong or missing `crcfinal` |
| `HUNG` | One of the above, and the processor did not finish |

The script does not count an `[ALERT]` with a correct `crcfinal` as an error.
AVF = errors / runs.

A run with a CRC difference that is not an error shows as `MISMATCH`. For
example, the hardware CRC is correct but the UART text that the script
captured is incomplete, or an `[ALERT]` with a correct `crcfinal`. A
`MISMATCH` is not an error and is not in the AVF. The summary gives the
number of `MISMATCH` runs. Its `HW CRC mismatches` and `UART mismatches`
lines count only the runs in which not all three CRCs differ.

`injection_results/csvs/` has one line for each error, and the summary as
the last line. `injection_results/raw_data/` has the UART output of each run
with a CRC difference, errors and `MISMATCH` runs.
