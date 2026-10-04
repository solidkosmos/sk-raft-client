# Example 3: Flip-flop shift register and LUTRAM injection

This example does two campaigns on one design through BSCAN:

- Part 1: a shift register with a feedback loop, made of flip-flops.
- Part 2: a distributed RAM (LUTRAM).

USER1 starts and stops the clock of the shift register and of the LUTRAM. The script reads the shift register through USER2. USER3 and USER4 give access to the LUTRAM (address and data).

## Part 1: flip-flops

Part 1 injects faults into the flip-flops in `pblock_ff_sr_inst` (`TargetMemory.FF`). The server finds the flip-flops from the LL file. If the pblock contains no flip-flops, the script stops.

Each trial does these steps:

1. It lets the clock operate for 2 s, and then it stops the clock.
2. It reads the shift register.
3. It upsets one flip-flop.
4. It reads the shift register again and prints the two values.
5. It starts the clock again.

The script does not correct the upsets. Part 1 continues until you press Enter.

## Part 2: LUTRAM

Part 2 injects faults into the LUTRAM in `pblock_LUTRAM` (`TargetMemory.LUTRAM`). The script does these steps:

1. With the clock on, it writes a known pattern into each word. Then it reads back each word to make sure that the pattern is correct.
2. It stops the clock and injects one upset each 0.5 s, until you press Enter.
3. It starts the clock again and reads back the full array.
4. It prints each word with the positions of its incorrect bits.

## Run the example

1. Make sure that the design files are in `src/design_files/`. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`, `DEVICE` and `design`. The design files are `ff_lut_top.bit`, `ff_lut_top.ll` and the XDC file. The script uploads them to the server.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `SR_LEN` | `8` | The width of the shift register. It must be equal to the `sr_len` generic of the design. |
| `LUT_ADDR_BITS` / `LUT_DEPTH` | `6` / `64` | The address width and the number of words of the LUTRAM. |
| `LUT_DATA_LEN` | `32` | The word width of the LUTRAM. It must be equal to the `lut_data_len` generic of the design. |
| `PBLOCK_SR` / `PBLOCK_LUTRAM` | `"pblock_ff_sr_inst"` / `"pblock_LUTRAM"` | The pblocks for parts 1 and 2, as the XDC file names them. |

## Result

The script runs part 1, programs the FPGA again, and runs part 2. Then it programs the FPGA one more time, to make sure that the configuration is clean.

If you stop the script with Ctrl+C during a campaign, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.
