# Example 3: Flip-flop shift register and LUTRAM injection

Two campaigns against one design over BSCAN: a feedback loop shift register built from flip-flops, (Part 1) and a distributed LUTRAM (Part 2). USER1 gates the clock of both the shift register and the LUTRAM (USER3/USER4).

Part 1 injects into the flip-flops inside `pblock_ff_sr_inst` (`TargetMemory.FF`, located from the LL file). If the pblock holds no flip-flops, the script stops. Each trial runs the clock for 2 s, freezes it, reads the shift register, upsets one flip-flop, reads it again and prints both, then resumes the clock. Upsets are never reverted. Runs until you press Enter.

Part 2 injects into the LUTRAM inside `pblock_LUTRAM` (`TargetMemory.LUTRAM`). With the clock enabled, a known pattern is written into every word and read back to confirm it round-tripped. The clock is then frozen and upsets are injected one every 0.5 s until you press Enter, then the clock is enabled again, the whole array is read back, and every word is printed with its corrupted bit positions.

```bash
python main.py
```

| Constant | Default | Meaning |
| --- | --- | --- |
| `SR_LEN` | `8` | Shift register width; must match the design's `sr_len` generic. |
| `LUT_ADDR_BITS` / `LUT_DEPTH` | `6` / `64` | LUTRAM address width and word count. |
| `LUT_DATA_LEN` | `32` | LUTRAM word width; must match the design's `lut_data_len` generic. |
| `PBLOCK_SR` / `PBLOCK_LUTRAM` | `"pblock_ff_sr_inst"` / `"pblock_LUTRAM"` | Pblocks confining Parts 1 and 2, as named in the XDC. |

Runs Part 1, reprograms, runs Part 2, then reprograms once more as a safety net. Interrupting with Ctrl-C mid-campaign can leave the device corrupted; reprogram before anything else.

Set `SK_RAFT_SERVER_IP`, `DEVICE` and `design` (`tester.bit`/`tester.ll` + XDC, uploaded to the server by the script) at the top of `main.py`.
