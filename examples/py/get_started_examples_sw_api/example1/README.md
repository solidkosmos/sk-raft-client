# TEST 1: Cumulative random CRAM injection

Injects random single-bit upsets into the device's configuration memory (CRAM). No design file is loaded and the device is never programmed, so this works on a blank device or on one already programmed by someone else - no bitstream needed either way. The simplest test in the suite; a good first run after bringing up the server.

## Requirements

- Python 3.9+, the `skraft` package installed.
- A running sk-raft server, target board connected over USB.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `NUMBER_OF_INJECTIONS` | `1000` | Upsets to inject. |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"<SK_RAFT_SERVER_IP>"` / `50051` | sk-raft server address; set the IP before running. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. |

## Running it

```bash
python main.py
```

Injections are **cumulative** and never corrected - nothing is scrubbed between iterations. Prints the FAR/word/bit of every upset. If a design is loaded, watch it externally (LEDs, a checker, etc.) and cross-reference the injection number where behaviour changes against the log. The device is left with all upsets in place; reprogram before anything that needs a known-good configuration.

For connection/attach errors, check the server is running and the device isn't held by another process (e.g. an open Vivado hardware manager session).
