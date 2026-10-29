# Readback scrubbing in Python

This example corrects upsets in the configuration memory (CRAM) of the FPGA with a readback scrubber that runs on the client. The script uses only the readback and the frame write of SK-RAFT. It does not use the scrubbing of the server (`dev.scrub()`). Thus you can see each step of the scrubber, and change it.

The script does not need design files, and it does not program the FPGA. It scrubs the design that is in the FPGA.

To show the scrubber at work, the script injects one random upset into the CRAM before each scrub cycle. The upset stays in the CRAM until the next scrub cycle.

The output has this form (the values are only an example):

```
Device: serial number 210183BFD452A, part number XC7A35T
Golden frames: 9200, checked frames: 9000
--------------------------------------------------------------------------------
Cycle  1: 1 upset(s) corrected | correction 0.012 s | cycle 2.100 s | idle 5.000 s
    far 0x00401f00 word  12 bit  7 (golden 0x00000000, read 0x00000080)
    injected far 0x00401f00 word  12 bit  7: corrected
```

## How the scrubber works

1. At the start, the script reads back all the frames of the CRAM. These frames are the golden frames.
2. In each scrub cycle, the script reads back all the frames again, and compares each frame with its golden frame.
3. For each frame that is different, the script writes the golden frame back, at its frame address (FAR).

The script does not check these frames:

| Frames | Why |
| --- | --- |
| Dummy (pad) frames | The first and the last frame of a readback, and each frame with the same FAR as the frame before it. A dummy frame does not hold configuration data. Its FAR is the FAR of a real frame, thus a write would change the real frame. |
| BRAM content frames (block type 1) | The contents of the BRAMs change during operation. |

The SK-RAFT scrubber on the server does the same steps. The script is different in these points:

- The golden frames come from the readback at the start of the script. If an upset is in the CRAM before this readback, the scrubber does not correct it.
- The script does not tell essential upsets from non-essential upsets.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `dev.readback(ReadbackOption.READBACK)` | Read back all the frames of the CRAM, for the golden frames and in each scrub cycle. |
| `dev.write_frame(frame)` | Write a golden frame back, at its frame address. |
| `dev.decode_far(far)` | Get the block type of a frame. The script decodes only the frames that it needs, and keeps the result. |
| `dev.configure_seed(seed)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `dev.inject_random(TargetMemory.CRAM)` | Inject one upset into a random bit of the CRAM. The server does not inject into the dummy frames, and into the frames that it excludes, for example the frames of the IOBs. |
| `dev.inject_at(far, word, bit, TargetMemory.CRAM)` | Flip an injected bit again, if it is in a BRAM content frame. Then the script injects again. |

## Requirements

- SK-RAFT server, with the FPGA board connected through JTAG. The server must support the frame write (`FpgaWriteFrame`).
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`.
2. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `SERIAL_NUMBER` | `"210183BFD452A"` | The serial number of the target board. `get_devices()` gives the connected boards. |
| `SCRUB_CYCLES` | `10` | The number of scrub cycles. |
| `SCRUB_PERIOD_S` | `5.0` | The time from the start of one scrub cycle to the start of the next, in seconds. |
| `INJECT_UPSETS` | `True` | If `True`, the script injects one upset before each scrub cycle. |
| `SEED` | `42` | The seed of the random injections. |

## Result

In each cycle, the script shows the corrected bits, and if it corrected the injected bit. The script also shows:

| Value | Meaning |
| --- | --- |
| correction | The time of the frame writes of the cycle. |
| cycle | The time of the full scrub cycle: the readback, the comparison and the frame writes. |
| idle | The time from the end of the previous cycle (or of the golden readback) to the start of this cycle. |

Each cycle also shows that the correction of the previous cycle operated: if a write did not correct a bit, the next cycle shows the bit again.

## Troubleshooting

| Problem | Cause | Solution |
| --- | --- | --- |
| The script corrects upsets in each cycle, also with `INJECT_UPSETS = False` | The design in the FPGA has configuration bits that change during operation, for example LUTRAM or SRL bits. The script compares all the bits of the checked frames. | Use a design that does not have these bits. |
| `failed to write frame ...: unknown method FpgaWriteFrame ...` | The SK-RAFT server is older than the client, and does not support the frame write. | Update the SK-RAFT server. |
