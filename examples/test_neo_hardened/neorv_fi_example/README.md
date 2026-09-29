# NEORV32 Fault Injection Example

Runs a fault-injection campaign against a NEORV32 RISC-V core on an FPGA and
measures the observed error rate (AVF) by comparing UART/CRC output against a
golden run. `run_injection.py` drives the campaign; `bscan_helpers.py` wraps
the low-level BSCAN register access used to control/read the DUT.

## SK-RAFT features exercised

- **Connection & device reservation** — `SkraftFpga.connect()`, `client.attach()`, `dev.release()`, `client.disconnect()`
- **Design loading** — `DesignFiles` + `ServerPath`, resolved server-side (bitstream, `.ebd`, `.ll`)
- **Frame exclusion** — `client.extract_fars_from_bitstream()` to pull FARs from a partial bitstream, plus `dev.exclude_frames()` to keep injection away from the clock-cycle controller
- **Programming** — `dev.program()`
- **BSCAN primitives** — `BscanPrimitive`, `dev.write_bscan()` / `dev.read_bscan()`, used in `bscan_helpers.py` to drive reset, step counters, and CRC read-back over JTAG
- **Fault injection** — `InjectionArea` to target CRAM, BRAM, flip-flops, or LUTRAM; `dev.inject_random()` to inject a random single-bit fault and get back an `FpgaRandomInjectionReport` (FAR, word index, bit index, target)
- **Fault reversal** — `dev.inject_at()` to flip the same bit back after a run completes

UART handling (`pyserial`) and CRC validation logic are example-specific glue, not part of the skraft API.

## Running

```bash
pip install skraft
python run_injection.py
```

