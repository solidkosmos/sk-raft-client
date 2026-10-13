# NEORV32 Fault Injection Example

`run_injection.py` runs a fault-injection campaign on the NEORV32 hardening
design and measures the observed error rate (AVF) against a golden run.
`bscan_routine_helpers.py` holds the BSCAN register access (reset, step
count, root clock, CRC read).

## SK-RAFT features used

- **Connection** — `SkraftFpga.connect()` and `client.attach()`, in `with`
  statements that release the device and close the connection
- **Design** — `Design` (`.bit`, `.ebd`, `.ll`, `.xdc`) and
  `dev.uploadDesignToServer()`, `dev.programFPGA()`
- **Pblock exclusion** — `exclude_pblock` of `dev.inject_random()`: no
  injection into the harness pblock
- **BSCAN** — `BscanPrimitive`, `dev.write_bscan()`, `dev.read_bscan()`
- **Fault injection** — `TargetMemory` (essential bits, BRAM, FF, LUTRAM),
  `dev.inject_random()`, and `dev.inject_at()` to flip the bit back after
  the run

## Running

Build the design first (see the [README of the example](../README.md)). The
script reads the `.bit`, `.ebd` and `.ll` files from
`../test_neo/test_neo.runs/impl_1/` (`IMPL_DIR`) and the XDC from
`../hw/xdc/basys3.xdc`. Set `SERIAL_NUMBER`, `UART_PORT` and the target
memory (`target_idx`) in the script, then run it from this folder:

```bash
pip install -e ../../../api/python pyserial
python run_injection.py
```

`UART_BAUD` (500000) must match the baud rate of the firmware.

## Results

Each run is compared with the golden run on three CRCs: the CRC in the
UART message, the CRC that the script calculates from the message, and the
hardware CRC (USER1). If all three differ, the message gives the status:

Status | Message
------ | -------
`ERROR` | an exception report of the runtime (`NEORV32-RTE`)
`DETECTED` | an `[ALERT]` and a wrong or missing `crcfinal`
`SDC` | no `[ALERT]` and a wrong or missing `crcfinal`
`HUNG` | one of the above, and the processor did not finish

An `[ALERT]` with a correct `crcfinal` is not flagged as an error. AVF = errors / runs. `injection_results/csvs/` has one
line per error; `injection_results/raw_data/` has the UART output of each
run with a CRC difference.
