# TEST 3: Targeted injection into essential bits

TEST 1 and TEST 2 pick bits from the whole of CRAM, so most upsets land on unused logic and do nothing. This one narrows the target to the design's **essential bits** (from the EBD file) - the bits the design actually uses - so every upset is guaranteed to hit something real. Essential is not the same as critical: only a subset of essential bits actually cause a functional failure, and finding that subset is what the run is for.

Two modes, chosen interactively at start-up: **random** samples `NUMBER_OF_INJECTIONS` essential bits with replacement; **exhaustive** walks every essential bit exactly once (cumulative and uncorrected, so the design will typically stop working well before the sweep finishes).

## Requirements

- Python 3.9+, the `skraft` package installed.
- A running sk-raft server, target board connected over USB.
- A bitstream and its matching EBD file, on the **server** filesystem.

Generate the EBD alongside the bitstream:

```tcl
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
write_bitstream -force tester.bit
```

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `NUMBER_OF_INJECTIONS` | `1000` | Upsets in random mode; ignored in exhaustive mode. |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"<SK_RAFT_SERVER_IP>"` / `50051` | sk-raft server address; set the IP before running. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. |
| `BITSTREAM` / `EBD` | example paths | `.bit` / `.ebd` files, resolved on the **server**. Must come from the same implementation run. |
| `PROGRESS_EVERY` | `100` | How often a progress line is printed. |

## Running it

```bash
python main.py
```

Prompts for the mode before connecting to anything; for an unattended run pipe the answer in (`echo r | python main.py`). Reprogram the device afterwards - both modes leave the design corrupted.
