# TEST 2: Program the device, then inject cumulative random CRAM upsets

Same injection loop as TEST 1, but the device is programmed with a bitstream first, so every corrupted bit belongs to a known configuration you can reason about. Run TEST 1 first if you haven't, to confirm the injection path works before a design enters the picture.

## Requirements

- Python 3.9+, the `skraft` package installed.
- A running sk-raft server, target board connected over USB.
- A bitstream built for the target device, on the **server** filesystem.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `NUMBER_OF_INJECTIONS` | `1000` | Upsets to inject after programming. |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"<SK_RAFT_SERVER_IP>"` / `50051` | sk-raft server address; set the IP before running. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. |
| `BITSTREAM` | example path | `.bit` file location, resolved on the **server**, not the client. Use an absolute path. |

## Running it

```bash
python main.py
```

Programming happens once at the start (so each run begins from a clean configuration); injections are **cumulative** from there on, never corrected. Watch the design externally and cross-reference the injection number where behaviour changes against the printed FAR/word/bit log. Reprogram before anything that needs a known-good configuration.

A load failure almost always means `BITSTREAM` doesn't exist at that path *on the server*, or the server can't read it.
