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
`../hw/xdc/basys3.xdc`. Set `SERIAL_NUMBER`, `UART_PORT` and the target memory
(`target_idx`) in the script. Then run the script from this folder:

```bash
pip install -e ../../../api/python pyserial
python run_injection.py
```

`UART_BAUD` (500000) must be equal to the baud rate of the firmware.

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
AVF = errors / runs. `injection_results/csvs/` has one line for each error.
`injection_results/raw_data/` has the UART output of each run with a CRC
difference.
