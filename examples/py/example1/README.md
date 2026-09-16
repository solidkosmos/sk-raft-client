# TEST 1: Cumulative random CRAM injection

This example injects a sequence of random single-bit upsets into the configuration
memory (CRAM) of a target FPGA. The script itself loads no design file and never
programs the device. It simply attaches to whatever is in the JTAG chain and
starts flipping configuration bits.

It is the simplest test in the suite and a good first thing to run after
installing sk-raft and bringing up the server. On a blank device it exercises
the injection path on its own, with no design-dependent behaviour getting in the
way.

It is equally useful on a device that is already programmed, where it injects
into the live configuration of the design currently loaded and you can observe
how that design responds. Because no bitstream, netlist or design database is
needed, this works even when the design is not yours. It is the usual starting
point for characterising a board delivered by a third party, or a design
supplied under NDA where only the programmed hardware is available.

## What the test does

1. Connects to a running sk-raft server over TCP.
2. Attaches to the target device (`xc7a35t` by default).
3. Performs 1000 random single-bit injections into the CRAM address space.
4. Prints the location of every injected upset.
5. Detaches and closes the connection.

The device is never programmed, erased or reconfigured by the script. Whatever
configuration is present when the run starts is what gets hit.

Injections are **cumulative**. Nothing is scrubbed or repaired between
iterations, so upsets accumulate in the configuration memory for the duration of
the run.

## Requirements

* Python 3.9 or later.
* The `skraft` Python package installed in your environment.
* A running sk-raft server with the target board connected to the host over USB.
* The device present in the JTAG chain. It may be blank or already programmed.
  No bitstream or design file is required either way.

Install the client package into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install skraft
```

## Configuration

Four constants at the top of the script control the run. Edit them to match
your setup.

| Constant | Default | Meaning |
| --- | --- | --- |
| `NUMBER_OF_INJECTIONS` | `1000` | How many single-bit upsets to inject. |
| `SK_RAFT_SERVER_IP` | `"127.0.0.1"` | Address of the sk-raft server. Use the host's IP if the server runs on another machine. |
| `SK_RAFT_SERVER_PORT` | `50051` | Port the sk-raft server is listening on. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. Must match a device the server can see. |

## Interpreting the results

### On a blank device

There is no functional behaviour to observe and no golden output to compare
against. Success means the run completed without raising `SkraftError` and that
the reported addresses fall within the expected ranges for the target device.
What the test tells you is:

* the client can reach the server and attach to the device,
* random address generation covers the CRAM address space,
* the read-modify-write injection path works end to end,
* the sustained injection rate you can expect on your hardware.

### On a device that is already programmed

The injected upsets act on the live configuration, so the design can change
behaviour or stop working at any point during the run. Since the script prints
nothing about the design itself, the useful signal comes from watching the board
while the run progresses: status LEDs, serial output, link state, a checker
running on the design, or whatever else the board exposes.

The practical method is to run the injections while monitoring the design
externally, note the injection number at which behaviour departs from normal,
and cross-reference that number against the printed log to recover the FAR,
word index and bit index of the bit responsible. That gives you a concrete
sensitive location without ever needing the bitstream.

Because injections are cumulative, once the design has failed you cannot tell
which of the later upsets matter. For pinpointing individual sensitive bits,
use a shorter run, or reload the design and repeat with a fresh accumulation.

### Points to keep in mind

* Addresses are drawn at random with replacement, so the same bit can be
  selected more than once. A second hit on the same bit flips it back rather
  than adding a new upset. Over 1000 injections on a device of this size the
  effect is negligible, but it matters if you scale the count up considerably.
* Only a fraction of CRAM bits are essential to any given design. Most random
  injections land in unused logic or routing and have no visible effect. This
  is expected, and the ratio of visible failures to total injections is itself
  a useful figure.
* CRAM includes frames holding BRAM content and interconnect configuration, so
  an upset can corrupt stored data as readily as it can break routing.

## After the run

The device is left with all injected upsets still in place. Reprogram it, or
issue a full configuration reset, before running any test that depends on a
known-good configuration.

If the device arrived already programmed and you do not hold the bitstream, be
careful here. Configuration memory is volatile: a power cycle or a reset clears
it, and the design only comes back if the board reloads it automatically from
attached flash or a configuration controller. On a board that was programmed
over JTAG alone, the design is gone for good once power drops. Confirm how the
board configures itself before you start, and keep a way to restore it.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `TEST 1 failed:` with a connection error | The server is not running, or the IP and port do not match. Check that the port is reachable if the server is remote. |
| `TEST 1 failed:` on attach | The device identifier does not match anything in the chain, or another process holds the USB connection. Close any open Vivado hardware manager session. |
| Injections start, then fail partway through | Usually the USB cable or board power dropping out. Reseat the cable and restart the server. |
| Run is slower than expected | Each injection is a read-modify-write over JTAG. Throughput scales with the configured JTAG clock frequency. |

For anything not covered here, contact SolidKosmos support with the full console
output and the sk-raft server log.
