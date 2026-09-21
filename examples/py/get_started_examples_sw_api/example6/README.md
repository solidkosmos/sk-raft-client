# JTAG/BSCAN-driven flip-flop shift register and LUTRAM injection

Two campaigns against one design: a free-running shift register built from flip-flops (Part 1) and a distributed LUTRAM (Part 2), both reachable over BSCAN. USER1 gates the shift register's clock and has no bearing on the LUTRAM - USER3/USER4 address it directly regardless of clock state.

Part 1 confines injection to the flip-flop bits inside `pblock_ff_sr_inst`, as declared in the XDC. Flip Flop (.LL) based targeting - narrowing that pblock down to only its true flip-flop bits - is coming in a later release. `REPEATS` trials then each run the clock for `RUN_S` seconds, freeze it, upset one random site inside the pblock, and run the clock for `RUN_S` seconds more; upsets are never reverted, so later trials run against whatever earlier ones left behind.

Part 2 needs no pblock: `InjectionArea.LUTRAM` already confines injection to the LUTRAM bits the LL file names. A known pattern (`0xA5A5A5A5 ^ address`) is written into every word, `LUT_INJECTIONS` random LUTRAM bits are upset back to back with no reads in between, and only then is the whole array read back and compared; every corrupted word is reported with the value it should hold beside what it actually holds.

Neither part corrects what it injects, so the device is reprogrammed between the two parts and again at the end.

## BSCAN register mapping

| Register | Width | Direction | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | write | Shift register clock enable |
| USER2 | `sr_len` bits | read | Shift register readback |
| USER3 | `lut_addr_bits` bits | write | LUTRAM address select |
| USER4 | `lut_data_len` bits | read/write | LUTRAM data |

## Requirements

- Python 3.9+, the `skraft` package installed, `reporting.py` alongside `main.py`.
- A running sk-raft server, target board connected over USB.
- A bitstream, LL, and the XDC declaring `pblock_ff_sr_inst`, all on the **server**.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `SR_LEN` | `8` | Shift register width; must match the design's `sr_len` generic. |
| `LUT_ADDR_BITS` / `LUT_DEPTH` | `4` / `10` | LUTRAM address width and actual word count (addresses 10-15 are unused). |
| `LUT_DATA_LEN` | `32` | LUTRAM word width; must match the design's `lut_data_len` generic. |
| `REPEATS` / `RUN_S` | `5` / `2.0` | Part 1 trials, and seconds the clock runs either side of each freeze. |
| `LUT_INJECTIONS` | `20` | Part 2 random LUTRAM bits injected back to back before the readback. |
| `PBLOCK` | `"pblock_ff_sr_inst"` | Pblock name confining Part 1, as in the XDC. |

## Running it

```bash
python main.py
```

Runs Part 1, reprograms, runs Part 2, then reprograms once more as a safety net. Interrupting with Ctrl-C mid-campaign can leave the device corrupted; reprogram before anything else.
