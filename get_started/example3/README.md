# Example 3: Flip-flop shift register and LUTRAM injection

This example does two campaigns on one design through BSCAN:

- Part 1: a shift register with a feedback loop, made of flip-flops.
- Part 2: a distributed RAM (LUTRAM).

USER1 starts and stops the clock of the shift register and of the LUTRAM. The script reads the shift register through USER2. USER3 and USER4 give access to the LUTRAM (address and data).

![Block diagram of ff_lut_top. USER1 controls a clock gate. The gated clock drives a clock divider with a shift register in one pblock, and a LUTRAM in another pblock. USER2 reads the shift register. USER3 and USER4 give the address and the data of the LUTRAM.](images/example3_ff_lut_top_abstract.svg)

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

1. Make sure that the design files are in `hw/design_examples/<board>/ff_lut_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`. The design files are `ff_lut_top.bit`, `ff_lut_top.ll` and the XDC file. The script uploads them to the server.
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

Sample output of a run on a Basys 3 (shortened). The frame addresses, the bit counts and the error counts depend on the board, the build and the seed.

```
Example 3: Flip-flop shift register and LUTRAM injection
Programmed 210183BFD452A.
Part 1: 8 flip-flop bits inside pblock_ff_sr_inst.
Press Enter to move on.
     #  FAR       WORD  BIT  BEFORE    AFTER
     1  00400f9f    97   28  00000100  00100100
     2  00400f9f    97   28  10010000  10110000
     3  00400f9f    97    4  11000010  11000011
     4  00400f9f    97   28  00001111  00101111
Part 1: done after 4 trials.
Re-programming before Part 2.
Part 2: all 64 LUTRAM words read back correctly. Injecting random upsets, not corrected - press Enter to move on.
Part 2: 2048 LUTRAM bits inside pblock_LUTRAM.
     #  FAR       WORD  BIT
     1  00000a21     3   27
     2  00000a23     3    0
...
Part 2: 7 upsets injected.
  ADDR  CORRECT                           READ                              CORRUPTED BITS
     0  10100101101001011010010110100101  10100101101001011010010110100101  -
...
     9  10100101101001011010010110101100  10100101101001011010010110100100  3
...
    55  10100101101001011010010110010010  10101101111001011010010110010010  22, 27
...
Part 2: 6/64 words are corrupted, 7 bits in total.
Re-programming to clear the device.
Example 3 done.
```

The script runs part 1, programs the FPGA again, and runs part 2. Then it programs the FPGA one more time, to make sure that the configuration is clean.

If you stop the script with Ctrl+C during a campaign, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.
