# Readback scrubbing in Python

This example corrects upsets in the configuration memory (CRAM) of the FPGA with a readback scrubber that runs on the client. The script uses only the readback and the frame write of SK-RAFT. Thus you can see each step of the scrubber, and change it.

You can select:

- The frames to scrub (`SCRUB_TARGET`): the whole CRAM, or only the essential CRAM (the frames with essential bits). In both cases, the scrubber does not check the BRAM content frames.
- The number of frames that the scrubber reads back at a time (`FRAMES_PER_READBACK`). All the frames, or N frames. Each scrub cycle checks all the configuration frames in both cases.

For the whole CRAM, the script does not need design files, and it does not program the FPGA. It scrubs the design that is in the FPGA. For the essential CRAM, the script programs the FPGA with a design that has an essential bits (EBD) file.

To show the scrubber at work, the script injects one random upset into the checked frames before each scrub cycle. Each scrub cycle starts when the previous one ends.

The output has this form (the values are only an example):

```
Device: serial number 210183BFD452A, part number XC7A35T
Scrub target: whole CRAM, frames per readback: all
Golden frames: 5568, checked frames: 4512, readbacks per cycle: 1
--------------------------------------------------------------------------------
Cycle  1: 1 upset(s) corrected | correction 0.012 s | cycle 2.100 s
    far 0x00401f00 word  12 bit  7 (golden 0x00000000, read 0x00000080)
    injected far 0x00401f00 word  12 bit  7: corrected
```

## How the scrubber works

1. For the essential CRAM, the script programs the FPGA with the design, and gets the frames with essential bits.
2. The script reads back all the frames of the CRAM. These frames are the golden frames.
3. The script selects the checked frames. The frames of the scrub target, without the frames in the table below.
4. In each scrub cycle, the script reads back all the checked frames, all at once or N frames at a time, and compares each frame with its golden frame.
5. For each frame that is different, the script writes the golden frame back, at its frame address (FAR).

The script does not check these frames:

| Frames | Why |
| --- | --- |
| Dummy (pad) frames | The first and the last frame of a readback, and each frame with the same FAR as the frame before it. A dummy frame does not hold configuration data. |
| BRAM content frames (block type 1) | The contents of the BRAMs change during operation. |
| Frames without essential bits | Only for the essential CRAM. |

### The frames of each readback

Each scrub cycle checks all the checked frames. `FRAMES_PER_READBACK` sets the number of checked frames that the scrubber reads back at a time:

| `FRAMES_PER_READBACK` | Each scrub cycle |
| --- | --- |
| `0` | Reads back all the frames of the CRAM with `dev.readback`, and then compares all the checked frames. |
| `1` | Reads back the next checked frame with `dev.readback_range`, and compares it. Then it does the same for the next frame, up to the last checked frame. |
| N (2, 3, ...) | Reads back the next N checked frames with `dev.readback_range`, and compares them. Then it does the same for the next N frames, up to the last checked frame. The last readback can have fewer frames. |

N must be smaller than the number of frames of the device. The output shows the number of readbacks of each cycle (`readbacks per cycle`). The scrubber corrects the frames of a readback before the next readback.

`dev.readback_range` reads back all the frames from the lowest to the highest FAR of the N frames. For the essential CRAM, the result can also have frames without essential bits, between the checked frames. The script does not compare them.

The scrubber has these limits:

- The golden frames come from the readback at the start of the script. If an upset is in the CRAM before this readback, the scrubber does not correct it.
- For the essential CRAM, the script compares all the bits of each frame with essential bits, not only the essential bits.
- At the start, the script decodes the FAR of each frame that it can check (one `dev.decode_far` call for each frame), to find the BRAM content frames. On a large device, this takes some time.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `dev.far_list()` | Get the frame addresses of the device, to check `FRAMES_PER_READBACK`. |
| `dev.upload_design_to_server(design)`, `dev.program_fpga(design)` | Upload the design and program the FPGA. The server gets the essential bits from the EBD file when it programs the FPGA. |
| `dev.essential_frames()` | Only for the essential CRAM. Get the frames with essential bits. The script uses only their frame addresses. |
| `dev.readback(ReadbackOption.READBACK)` | Read back all the frames of the CRAM, for the golden frames, and in each scrub cycle with `FRAMES_PER_READBACK = 0`. |
| `dev.readback_range(start_far, end_far)` | Read back the next N checked frames, with `FRAMES_PER_READBACK` = N > 0. |
| `dev.write_frame(frame)` | Write a golden frame back, at its frame address. |
| `dev.decode_far(far)` | Get the block type of a frame, to find the BRAM content frames. |
| `dev.configure_seed(seed)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `dev.inject_random(SCRUB_TARGET)` | Inject one upset into a random bit of the CRAM, or of the essential CRAM. The server does not inject into the dummy frames, and into the frames that it excludes, for example the frames of the IOBs. |

## Requirements

- SK-RAFT server, with the FPGA board connected through JTAG.
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- Only for the essential CRAM. The bitstream (`.bit`) and the essential bits file (`.ebd`) of a design for your board. The default is the `targeted_top` design in `get_started/hw/design_examples/<board>/`. Extract `design_examples.zip` there first.

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`, `SCRUB_TARGET` and `FRAMES_PER_READBACK`. For the essential CRAM, also set `BOARD` (or `DESIGN`). The script attaches to the first board that the server lists. Connect only the target board to the server.
2. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `SCRUB_TARGET` | `TargetMemory.CRAM` | The frames to scrub: `TargetMemory.CRAM` (the whole CRAM) or `TargetMemory.ESSENTIAL_CRAM` (only the frames with essential bits). |
| `FRAMES_PER_READBACK` | `0` | The number of frames that the scrubber reads back at a time: `0` for all the frames, or N for N frames. N must be smaller than the number of frames of the device. |
| `BOARD` | `"basys3"` | Only for the essential CRAM: the board of the default design (`basys3` or `zedboard`). |
| `DESIGN` | `targeted_top` of `BOARD` | Only for the essential CRAM: the `.bit` and `.ebd` files of the design. |
| `SCRUB_CYCLES` | `10` | The number of scrub cycles. Each cycle starts when the previous one ends. |
| `INJECT_UPSETS` | `True` | If `True`, the script injects one upset into the checked frames before each scrub cycle. |
| `SEED` | `42` | The seed of the random injections. |

## Result

In each cycle, the script shows the corrected bits, and if it corrected the injected bit. The script also shows:

| Value | Meaning |
| --- | --- |
| correction | The time of the frame writes of the cycle. |
| cycle | The time that the full scrub cycle took. The readbacks, the comparison and the frame writes. The injection before the cycle is not part of it. |
