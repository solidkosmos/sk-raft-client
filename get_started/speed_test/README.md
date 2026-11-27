# Speed test: the time of the SK-RAFT functions

This test measures how long the main SK-RAFT functions take, as your script sees them: from the call in Python to the return of its result. Use the times to plan a campaign, for example to calculate how many injections or scrub cycles fit in a beam run.

The script runs each test several times. It prints the minimum, the median, the 95th percentile and the maximum of each test, in milliseconds.

## Design

The test uses [`brams_top`](../hw/sources_1/new/brams_top.vhd), the design of [example 4](../example4/README.md): one BRAM in the pblock `pblock_soft_sec_bram`, with flip-flops around it (the ECC, the hold register and the BSCAN registers). Thus the test can measure the injection into the flip-flops and into the BRAM content.

The script uses the clock enable of the design (BSCAN USER1). It stops the clock during the flip-flop and BRAM injections, as the [general guidelines](../../docs/general_guidelines.md#2-stop-the-clock-during-application-memory-injection) require.

## Tests

| Test | Function | Measurements |
| --- | --- | --- |
| `program` | `dev.program_fpga()` | 5 |
| `read_1` | `dev.readback_range()` of 1 frame | 50 |
| `read_1000` | `dev.readback_range()` of 1000 frames | 10 |
| `write_1` | `dev.write_frame()` of 1 frame | 50 |
| `read_all` | `dev.readback()`: all the frames of the CRAM | 3 |
| `inject_ff` | `dev.inject_random(TargetMemory.FF)` | 50 |
| `inject_bram` | `dev.inject_random(TargetMemory.BRAM, pblock="pblock_soft_sec_bram")` | 50 |
| `scrub_cram` | One scrub cycle of all the frames of the CRAM | 5 |
| `scrub_essential` | One scrub cycle of the frames with essential bits | 5 |

Before the `read_1`, `read_1000`, `write_1`, `inject_ff` and `inject_bram` measurements, the script makes 3 calls that it does not measure. For the tests on more than one frame, the script also prints the number of frames and the median time of one frame.

### The scrub cycles

A scrub cycle reads back the checked frames, compares each frame with its golden frame and writes back each frame that is different. The golden frames are the readback after the programming. As in [`readback_scrubbing`](../../application_examples/readback_scrubbing/README.md), the script checks neither the dummy (pad) frames nor the BRAM content frames.

| Test | Checked frames | Readback |
| --- | --- | --- |
| `scrub_cram` | All the frames of the CRAM | One `dev.readback()` of all the frames |
| `scrub_essential` | The frames with essential bits (`dev.essential_frames()`) | One `dev.readback_range()` for each group of consecutive frames |

Before each scrub cycle, the script injects one upset into a checked frame: `TargetMemory.CRAM` for `scrub_cram`, `TargetMemory.ESSENTIAL_CRAM` for `scrub_essential`. The time of the cycle does not include the injection. After the cycles, the script prints how many of the upsets the cycles corrected (expected: all).

## What the script does

1. It connects to the server, attaches the first board that the server lists and uploads `brams_top`.
2. It programs the FPGA 5 times, and measures each programming.
3. It measures the frame reads and the frame write. The write writes back the frame that the script read, so it does not change the design. Then the script reads the frame again, and prints a message if it changed.
4. It stops the clock of the design, and measures the flip-flop and BRAM injections. The upsets add up, so the script programs the FPGA again after these tests.
5. It reads the golden frames and measures the scrub cycles.
6. It programs the FPGA again at the end, and prints the results.

The script runs without input. On a Basys 3, it takes about 40 s.

## Run the test

You need:

- Python 3.9 or a later version, with the `skraft` package installed.
- An SK-RAFT server in operation, with the target board connected through USB.
- The bitstream and the EBD, LL and XDC files of `brams_top` in `hw/design_examples/<board>/brams_top/`. Use the prebuilt files in `design_examples.zip`, or build them with `hw/create_project.tcl`. Refer to [Prebuilt design files](../README.md#prebuilt-design-files) and [Build a design](../README.md#build-a-design).

Set these constants at the top of `src/main.py`:

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` | `127.0.0.1` | The address of the SK-RAFT server. |
| `BOARD` | `basys3` | Your board: `basys3` or `zedboard`. |
| `PROGRAM_REPEATS`, `REPEATS`, `BATCH_REPEATS`, `READBACK_REPEATS`, `SCRUB_CYCLES` | `5`, `50`, `10`, `3`, `5` | The number of measurements of each test. |

The script attaches to the first board that the server lists. Connect only the target board to the server. Then run the script:

```bash
cd src
python main.py
```

## Use your own design

You can run the test on your own design if you have its files available:

| File | Use in the test |
| --- | --- |
| The bitstream (`.bit`) | `program`, and the programming between the tests. |
| The essential bits (`.ebd`) | The essential bits, for `scrub_essential`. |
| The logic location file (`.ll`) | The flip-flop and BRAM bits, for `inject_ff` and `inject_bram`. |
| The constraints (`.xdc`) | The pblocks, for `inject_bram` with a pblock. |

The design must have flip-flops and at least one BRAM. Set these values at the top of `src/main.py`:

| Value | Set it to |
| --- | --- |
| `design` | The paths of the four files of your design, relative to `src/`. |
| `PBLOCK_BRAM` | A pblock of your design with a BRAM in it, or `None` to inject into all the BRAMs of the design. |
| `USER_CLK_EN` | The BSCAN register that stops the clock of your design: 0 stops the clock and 1 starts it. Refer to the clock gate in [`auxiliary_components/bscan`](../../auxiliary_components/bscan/README.md#example-clock-gate-on-user1). Use `None` if your design has no clock gate. Then the clock runs during the flip-flop and BRAM injections, which the general guidelines do not allow in a campaign. |

## Result

Output of a run on a Basys 3, with the SK-RAFT server on the same Windows computer as the client. The run took 41 s.

```
Speed test: the time of the SK-RAFT functions
SK-RAFT client 1.0.1, server 1.0.3
Board 210183BA2524A, design ../../hw/design_examples/basys3/brams_top/brams_top.bit.
Measuring the programming...
Measuring the frame reads and writes...
Measuring the injections into the flip-flops and the BRAM...
Measuring the scrub cycles...
scrub_cram: 4518 checked frames, 5 of 5 upsets corrected.
scrub_essential: 549 checked frames in 38 range readbacks, 5 of 5 upsets corrected.
Programming the FPGA again to clear the device.

TEST                N        MIN     MEDIAN        P95        MAX  FRAMES  /FRAME   (ms)
program             5   1799.286   1805.302   1827.316   1827.316
read_1             50      1.044      1.124      1.353      1.375
read_1000          10    287.096    293.760    300.895    300.895    1000   0.294
write_1            50      0.769      0.825      0.964      1.052
read_all            3   1653.255   1690.035   1706.988   1706.988    5568   0.304
inject_ff          50      3.225      3.773      4.593      9.822
inject_bram        50      1.777      2.004      2.310      8.124
scrub_cram          5   1715.058   1770.407   1776.553   1776.553    4518   0.392
scrub_essential     5    193.014    193.906    235.070    235.070     549   0.353

Speed test done.
```

How to read the output:

- `FRAMES` is the number of frames of one call. For the scrub tests, it is the number of checked frames. `/FRAME` is the median divided by `FRAMES`.
- The two `scrub_` lines before the table give the number of checked frames, and how many of the injected upsets the scrub cycles corrected.
- On the Basys 3, one frame takes about 0.3 ms to read, in `read_1000` and in `read_all`.
- `scrub_cram` reads all the 5568 frames of the device. Thus it takes about the time of `read_all`, plus the comparison in Python and the write of the frames that are different.
- `scrub_essential` reads only the 549 frames with essential bits of `brams_top`, with 38 range readbacks. Thus it takes about one ninth of the time of `scrub_cram`. Its time depends on the design: the number of frames with essential bits, and the number of groups of consecutive frames.

The times depend on the device, the JTAG clock (TCK), the USB connection, and the computers of the client and the server. Compare times only from the same setup.

## The calls of the test

| Call | Use in the test |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.get_devices()`, `client.attach(serial_number)` | Connect to the SK-RAFT server, select the first board that the server lists and attach to it, in `with` statements that release the device and close the connection. |
| `Design(bit, ebd, ll, xdc)`, `dev.upload_design_to_server(design)`, `dev.program_fpga(design)` | Give the design files, upload them to the server and program the FPGA. |
| `dev.configure_seed(0)` | Set the seed of the random injections. |
| `dev.far_list()`, `dev.decode_far(far)` | Get the frame addresses of the device, and the block type of each frame. |
| `BscanPrimitive(1, 1)`, `dev.write_bscan(primitive, value)` | Start and stop the clock of the design (USER1). |
| `dev.readback_range(start_far, end_far)`, `dev.readback(ReadbackOption.READBACK)`, `dev.write_frame(frame)` | The frame reads, the full readback and the frame writes. |
| `dev.inject_random(target, pblock=...)`, `dev.inject_at(far, word_index, bit_index, target)` | The injections. `inject_at` flips back an upset that lands outside the checked frames of a scrub test. |
| `dev.essential_frames()` | Get the frames with essential bits, for `scrub_essential`. |
