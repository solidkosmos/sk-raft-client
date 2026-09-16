# TEST 2: Program the device, then inject cumulative random CRAM upsets

This example programs the target FPGA with a bitstream of your choosing and then
runs the same injection loop as TEST 1 against it. The injection behaviour is
identical. The difference is that every corrupted bit now belongs to a known
configuration, so any change in behaviour can be traced back to a design you
have the sources for.

Run TEST 1 first if you have not already. It confirms the injection path works
before a design is added to the picture.

## What the test does

1. Connects to a running sk-raft server over TCP.
2. Attaches to the target device (`xc7a35t` by default).
3. Loads the bitstream and programs the device.
4. Performs 1000 random single-bit injections into the CRAM address space.
5. Prints the location of every injected upset.
6. Detaches and closes the connection.

Programming happens once, at the start. Injections are **cumulative** from that
point on: nothing is scrubbed or repaired between iterations, so upsets build up
in the configuration memory for the duration of the run. Each fresh run of the
script starts from a clean, known-good configuration, because step 3 rewrites
the whole of CRAM.

## Requirements

* Python 3.9 or later.
* The `skraft` Python package installed in your environment.
* A running sk-raft server with the target board connected to the host over USB.
* A bitstream built for the target device, present on the **server** filesystem.

## Configuration

Five constants at the top of the script control the run. Edit them to match your
setup.

| Constant | Default | Meaning |
| --- | --- | --- |
| `NUMBER_OF_INJECTIONS` | `1000` | How many single-bit upsets to inject after programming. |
| `SK_RAFT_SERVER_IP` | `"127.0.0.1"` | Address of the sk-raft server. Use the host's IP if the server runs on another machine. |
| `SK_RAFT_SERVER_PORT` | `50051` | Port the sk-raft server is listening on. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. Must match a device the server can see. |
| `BITSTREAM` | example path | Location of the `.bit` file to program. |

### About `ServerPath`

The bitstream path is wrapped in `ServerPath`, and that wrapper is not
decoration. It marks the path as one to be resolved on the sk-raft server's
filesystem, not on the machine running the script. The client never opens the
file and never uploads it.

When client and server are the same machine this distinction makes no
difference. When the server runs elsewhere, on a lab machine or a shared
injection rig, the file has to exist at that path **on the server**, and the
server process needs permission to read it. Pointing `ServerPath` at a file that
only exists on your laptop is the most common way this example fails.

Use absolute paths. Relative paths are resolved against the server's working
directory, which is rarely what you expect.

## Running the test

Start the sk-raft server first, then:

```bash
python main.py
```

## Interpreting the results

The script prints nothing about the design itself, so the useful signal comes
from watching the design while the run progresses: status LEDs, serial output,
link state, a checker running in the fabric, or whatever else the design
exposes. Note the injection number at which behaviour departs from normal, then
cross-reference that number against the printed log to recover the FAR, word
index and bit index of the bit responsible.

Points to keep in mind:

* Only a fraction of CRAM bits are essential to any given design. Most random
  injections land in unused logic or routing and have no visible effect. That is
  expected, and the ratio of visible failures to total injections is itself a
  useful figure, roughly the design's sensitive-bit fraction as sampled by this
  run.
* Because injections are cumulative, once the design has failed you cannot tell
  which of the later upsets matter. For pinpointing individual sensitive bits,
  use a shorter run, or reprogram and repeat with a fresh accumulation.
* Addresses are drawn at random with replacement, so the same bit can be
  selected more than once. A second hit on the same bit flips it back rather
  than adding a new upset. Over 1000 injections on a device of this size the
  effect is negligible, but it matters if you scale the count up considerably.
* CRAM includes frames holding BRAM content and interconnect configuration, so
  an upset can corrupt stored data as readily as it can break routing.

## After the run

The device is left with all injected upsets still in place. Rerunning the script
restores a clean configuration as its first action, so no manual cleanup is
needed between runs. Reprogram before any other test that expects a known-good
configuration.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `TEST 2 failed:` with a connection error | The server is not running, or the IP and port do not match. Check that the port is reachable if the server is remote. |
| `TEST 2 failed:` on attach | The device identifier does not match anything in the chain, or another process holds the USB connection. Close any open Vivado hardware manager session. |
| `TEST 2 failed:` on load, file not found | The path does not exist on the server, or it points at a file that only exists on the client machine. See the `ServerPath` note above. |
| `TEST 2 failed:` on load, permission denied | The server process cannot read the file. Check ownership and permissions of the bitstream and every directory above it. |
| `TEST 2 failed:` on program | Usually a part mismatch. The bitstream must be built for the same device as `DEVICE`. |
| Programming succeeds but the design never runs | Check that the design is not waiting on a clock or reset the board does not supply, and that no external configuration source is reloading over the top. |
| Injections start, then fail partway through | Usually the USB cable or board power dropping out. Reseat the cable and restart the server. |

For anything not covered here, contact SolidKosmos support with the full console
output and the sk-raft server log.
