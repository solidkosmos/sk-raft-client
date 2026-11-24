# Example 3: Flip-flop shift register and LUTRAM injection

This example does two campaigns on one design through BSCAN:

- Part 1: an 8-bit shift register with a feedback loop, made of flip-flops. It shifts every 0.2 s, and the LEDs of the board show its bits 3:0.
- Part 2: a 64 x 32 distributed RAM (LUTRAM): 64 words of 32 bits.

USER1 starts and stops the clock of the shift register and of the LUTRAM. The script reads the shift register through USER2. USER3 and USER4 give access to the LUTRAM (address and data).

![Block diagram of ff_lut_top. USER1 controls a clock gate. The gated clock drives a clock divider with a shift register in one pblock, and a LUTRAM in another pblock. USER2 reads the shift register. USER3 and USER4 give the address and the data of the LUTRAM.](images/example3_ff_lut_top_abstract.svg)

## Part 1: flip-flops

Part 1 injects faults into the flip-flops inside the shift-register's pblock area (`pblock_ff_sr_inst`) (`TargetMemory.FF`). The server finds the flip-flops from the LL file. If the pblock contains no flip-flops, the script stops.

Each trial does these steps:

1. It lets the shift register make two full turns (16 shifts, 3.2 s), and then it stops the clock.
2. It reads the shift register.
3. It upsets one flip-flop.
4. It reads the shift register again. It prints the two values and the flip-flop that the upset hit (FF). The server gives the name of that flip-flop in the injection report, for example `ff_sr_inst/mass_s_reg[5]` for bit 5.
5. It keeps the clock stopped for 1.5 s, so that the LEDs show the flipped bit. The LEDs show bits 3:0 of the register: an upset in bits 7:4 shows on the LEDs when it shifts down.
6. It starts the clock again.

The script does not correct the upsets. Part 1 continues until you press Enter.

## Part 2: LUTRAM

Part 2 injects faults into the LUTRAM in `pblock_LUTRAM` (`TargetMemory.LUTRAM`). The script does these steps:

1. With the clock on, it writes the pattern `0xA5A5A5A5` into each word. Then it reads back each word to make sure that it holds the pattern.
2. It stops the clock and injects one upset each 0.5 s, until you press Enter. For each upset, it prints the LUTRAM word that the upset hit (ADDR). It finds the word in the LL file of the design: the line of the hit bit ends with `Ram=<LUT>:<n>`, and for a 64-deep LUTRAM the word is 63 - n.
3. It starts the clock again and reads back the full array.
4. It prints each word that changed, in hex, with the bits that differ from the pattern.

On the Basys 3, the LUTRAM is in the frames `00400a20` to `00400a23` and `00000a20` to `00000a23`: `pblock_LUTRAM` crosses the border between two clock regions, at row Y50.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.get_devices()`, `client.attach(serial_number)` | Connect to the SK-RAFT server, select the first board that the server lists and attach to it, in `with` statements that release the device and close the connection. |
| `Design(bit, ll, xdc)`, `dev.upload_design_to_server(design)`, `dev.program_fpga(design)` | Give the design files, upload them to the server and program the FPGA. |
| `dev.configure_seed(0)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `BscanPrimitive(user, length)`, `dev.write_bscan(primitive, value)`, `dev.read_bscan(primitive)` | Start and stop the clock (USER1), read the shift register (USER2), and select, write and read a LUTRAM word (USER3, USER4). |
| `dev.bit_count(TargetMemory.FF, pblock=PBLOCK_SR)`, `dev.bit_count(TargetMemory.LUTRAM, pblock=PBLOCK_LUTRAM)` | Get the number of flip-flop bits and LUTRAM bits of each pblock. |
| `dev.inject_random(TargetMemory.FF, pblock=PBLOCK_SR)`, `report.net_name` | Part 1: inject one upset into a random flip-flop of the shift register, and get the name of that flip-flop. |
| `dev.inject_random(TargetMemory.LUTRAM, pblock=PBLOCK_LUTRAM)` | Part 2: inject one upset into a random bit of the LUTRAM. |

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/ff_lut_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`. The script attaches to the first board that the server lists. Connect only the target board to the server. The design files are `ff_lut_top.bit`, `ff_lut_top.ll` and the XDC file. The script uploads them to the server.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `SR_LEN` | `8` | The width of the shift register. It must be equal to the `sr_len` generic of the design. |
| `SHIFT_PERIOD_S` | `0.2` | The time between two shifts of the register: 2 x the `shift_interval` generic of the design (100 ms). |
| `TURNS_PER_TRIAL` | `2` | Part 1: the full turns of the register between two upsets. 2 turns are 16 shifts, 3.2 s. |
| `HOLD_AFTER_INJECTION_S` | `1.5` | Part 1: the time that the clock stays stopped after each upset, so that the LEDs show the flipped bit. |
| `LUT_ADDR_BITS` / `LUT_DEPTH` | `6` / `64` | The address width and the number of words of the LUTRAM. |
| `LUT_DATA_LEN` | `32` | The word width of the LUTRAM. It must be equal to the `lut_data_len` generic of the design. |
| `PATTERN` | `0xA5A5A5A5` | Part 2: the value that the script writes into each LUTRAM word. |
| `PBLOCK_SR` / `PBLOCK_LUTRAM` | `"pblock_ff_sr_inst"` / `"pblock_LUTRAM"` | The pblocks for parts 1 and 2, as the XDC file names them. |

## Result

Sample output of a run on a Basys 3 (shortened). The frame addresses, the bit counts and the error counts depend on the board, the build and the seed.

```
Example 3: Flip-flop shift register and LUTRAM injection
Programmed 210183BA2524A.
Part 1: 8 flip-flop bits inside pblock_ff_sr_inst.
Press Enter to move on.
FF is the flip-flop that the upset hit. BEFORE and AFTER show bit 7 on the left, bit 0 on the right.
     #  FF  FAR       WORD  BIT  BEFORE    AFTER
     1   5  00400f9f    97   28  00000001  00100001
     2   5  00400f9f    97   28  00100001  00000001
     3   0  00400f9f    97    4  00000001  00000000
     4   5  00400f9f    97   28  00000000  00100000
Part 1: done after 4 trials.
Re-programming before Part 2.
Part 2: all 64 LUTRAM words read back 0xa5a5a5a5. Injecting random upsets, not corrected - press Enter to move on.
Part 2: 2048 LUTRAM bits inside pblock_LUTRAM.
ADDR is the LUTRAM word that the upset hit.
     #  FAR       WORD  BIT  ADDR
     1  00000a21     3   27    25
     2  00000a23     3    0    55
     3  00400a21    93   15     9
     4  00400a21    97    5    45
     5  00400a22    89    8    22
     6  00400a23    91   16    55
     7  00400a23   100    8    23
     8  00400a22    98   27    16
Part 2: 8 upsets injected.
  ADDR  READ        FLIPPED BITS
     9  0xa5a5a5ad  3
    16  0xa5a5a5a4  0
    22  0xa5a1a5a5  18
    23  0xe5a5a5a5  30
    25  0xa4a5a5a5  24
    45  0xa5a5a1a5  10
    55  0xade5a5a5  22, 27
Part 2: 7/64 words are corrupted, 8 bits in total.
Re-programming to clear the device.
Example 3 done.
```

The script runs part 1, programs the FPGA again, and runs part 2. Then it programs the FPGA one more time, to make sure that the configuration is clean.

If you stop the script with Ctrl+C during a campaign, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.
