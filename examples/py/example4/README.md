# Essential-bit injection with a BSCAN adder self-test

The earlier examples inject upsets and leave you to watch the board for signs of
trouble. This one closes the loop. The design under test is a small adder
reachable over JTAG through the BSCAN USER registers, so the script can drive
operands in, read the sum back out and decide for itself whether a given upset
mattered. No extra cabling, no serial console, no external checker.

The default configuration flips one essential bit, tests the adder, then flips
the same bit back. Flipping a bit twice restores it, so each round starts from a
clean design and sees exactly one live fault. That is what makes it possible to
say which individual bits are critical, rather than only that the design broke
somewhere during a cumulative run.

Run TEST 3 first if you have not. This example uses the same essential bits
machinery and assumes you already have a working EBD flow.

## The design under test

The adder exposes three BSCAN USER registers:

| Register | Width | Direction | Contents |
| --- | --- | --- | --- |
| USER1 | 8 bits | shifted in | operand A |
| USER2 | 8 bits | shifted in | operand B |
| USER3 | 16 bits | shifted out | result, A + B |

Your design must instantiate the corresponding BSCAN primitives with these USER
slots and widths, or the ids and sizes in the script must be changed to match
what the design actually implements. The script checks this before it injects
anything: it runs the test vectors once against the freshly programmed device
and stops if they fail.

## What the test does

1. Connects to a running sk-raft server over TCP.
2. Attaches to the target device (`xc7a35t` by default).
3. Loads the bitstream and EBD file, then programs the device.
4. Runs the test vectors as a baseline and stops if they do not pass.
5. Reads the essential frames and expands them into individual bit locations.
6. For each selected bit: injects, runs the test vectors, records the verdict,
   and flips the bit back if `CORRECT` is set.
7. Prints a per-injection table and a summary of how many upsets broke the
   adder.

## Requirements

* Python 3.9 or later.
* The `skraft` Python package installed in your environment.
* `reporting.py`, which ships with these examples, importable from the same
  directory. The script will not start without it.
* A running sk-raft server with the target board connected to the host over USB.
* A bitstream and matching EBD file on the **server** filesystem, built with
  `BITSTREAM.SEU.ESSENTIALBITS YES` set before `write_bitstream`.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` | `"127.0.0.1"` | Address of the sk-raft server. |
| `SK_RAFT_SERVER_PORT` | `50051` | Port the sk-raft server is listening on. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. |
| `BITSTREAM` | example path | Location of the `.bit` file, on the server. |
| `EBD` | example path | Location of the matching `.ebd` file, on the server. |
| `MODE` | `"random"` | `"random"` samples `INJECTIONS` bits; `"exhaustive"` sweeps every essential bit in order. |
| `INJECTIONS` | `1000` | Number of upsets in random mode. Ignored when exhaustive. |
| `CORRECT` | `True` | Restore each bit after its test. Set to `False` to let faults accumulate. |
| `USER_A`, `USER_B`, `USER_RESULT` | USER1/2/3 | BSCAN register ids and widths. Must match the design. |
| `TEST_VECTORS` | two pairs | Operand pairs applied after each upset. |
| `LOG_PATH` | `"bscan_adder.log"` | Transcript file. Set to `None` to disable. |
| `VERBOSE` | `False` | Set to `True` to print the result of every individual vector. |

Both file paths are wrapped in `ServerPath`, which means they are resolved on the
sk-raft server's filesystem, not on the machine running the script. When the
server runs on another machine, the files must exist at those paths on the
server and the server process must be able to read them. Use absolute paths.

### The test vectors

Two operand pairs are applied after each upset. `0x5A` and `0xA5` are
complementary alternating patterns, which catch a bit stuck in either operand
register. `0xFF` and `0xFF` is the upper limit, and the only pair here that
exercises the carry out of bit 7.

This matters more than it looks. A bit is reported as harmless if the vectors
happen not to exercise the logic it broke, so the critical bit count this test
produces is a lower bound, and its quality is the quality of your vectors. If
you care about the absolute number, widen `TEST_VECTORS` and expect the count to
rise. Adding vectors costs time linearly across the whole run, so there is a
real trade-off between coverage and how long a sweep takes.

### `CORRECT`

With `CORRECT` set to `True`, each bit is flipped, tested and flipped back, so
every round sees exactly one fault against an otherwise clean design. This is
the mode to use for characterising individual bits. Restoring works even when
the injected fault has broken the design badly, because configuration writes go
through the configuration port and do not depend on the fabric functioning.

With `CORRECT` set to `False`, upsets are left in place and accumulate. The
adder will typically fail at some point and stay failed, so the per-injection
verdicts after that are not attributable to any single bit. The device is
reprogrammed automatically at the end of the run to clear the accumulated
faults. Use this mode to see how quickly a design degrades under a growing
fault load, not to identify which bits matter.

## Running the test

Start the sk-raft server first, then:

```bash
python main.py
```

Interrupting with Ctrl-C is safe. The run reports how long it got through and
closes the log cleanly. If `CORRECT` was `False`, reprogram the device yourself
afterwards, since the automatic reprogramming at the end will have been skipped.

## Expected output

```
Connecting to the SK-RAFT server at 127.0.0.1:50051
Connected, server version 1.4.2
Programmed xc7a35t, 248193 essential CRAM bits
Baseline passed
Reading the essential frames (EBD)
248193 essential bits found
Random injection: 1000 upsets, corrected after each test
   #  FAR         WORD  BIT  ADDER      ELAPSED
   1  0x00020e80    47   19  ok           0:00:04
   2  0x00401a00     3   28  FAIL 2/2     0:00:05
   3  0x00020e84    12    7  ok           0:00:06
...
1000 upsets broke the adder
Done in 0:18:32
```

The `ADDER` column is the verdict for that upset: `ok` if every vector returned
the correct sum, or `FAIL n/m` giving how many of the vectors were wrong. Setting
`VERBOSE` to `True` adds a line per vector showing the operands, the expected
result and what came back, which is worth turning on when a result looks odd.

Everything printed also goes to the file named by `LOG_PATH`.

## Interpreting the results

The headline figure is the ratio at the end: how many of the injected upsets
broke the adder, out of how many were tried. With `CORRECT` set to `True` and
random mode, this is a clean estimate of the critical bit fraction within the
essential bit set, sampled uniformly. Multiply it by the essential bit count
reported at programming time for an estimate of the design's critical bit count.

Points to keep in mind:

* Random mode samples with replacement, so the same bit can be tested more than
  once and a critical bit hit twice contributes twice to the total. On a large
  essential set this hardly registers, but if you sample a sizeable share of the
  bits, deduplicate the target list before drawing conclusions about unique
  critical bits.
* The verdict only covers behaviour the vectors exercise. See the note above.
* A failure means the adder returned the wrong answer, which is not quite the
  same as the adder being broken. An upset can also corrupt the BSCAN path
  itself, so what you are really measuring is the sensitivity of the design plus
  its test access, taken together. For a small design like this one the BSCAN
  logic is a meaningful share of the total, so bear it in mind before
  generalising the ratio to a larger design.
* Exhaustive mode with `CORRECT` set to `True` gives a complete bit-by-bit
  characterisation, and it is the only configuration here that does. It also
  takes as long as the design has essential bits, with each round costing an
  injection, two register writes and a read per vector, and a second injection
  to restore. Measure the rate from a random run and multiply before you start
  one. A design with a few hundred thousand essential bits is an overnight job
  at best.

## After the run

With `CORRECT` set to `True` the configuration is left as it started, since
every bit was restored. With `CORRECT` set to `False` the script reprograms the
device before exiting. Either way, reprogram if a run was interrupted partway
through and you need a known-good configuration.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `ModuleNotFoundError: reporting` | `reporting.py` is not in the same directory or on the Python path. Copy it alongside `main.py`. |
| `Failed:` with a connection error | The server is not running, or the IP and port do not match. |
| `Failed:` on attach | The device identifier does not match anything in the chain, or another process holds the USB connection. Close any open Vivado hardware manager session. |
| `Failed:` on load, file not found | One of the paths does not exist on the server, or points at a file that only exists on the client machine. Use absolute server paths. |
| `Failed:` on program | Usually a part mismatch. The bitstream must be built for the same device as `DEVICE`. |
| `The adder is already wrong before any injection` | The USER register widths do not match the design, or the bitstream is not the adder design at all. Check the BSCAN primitives against `USER_A`, `USER_B` and `USER_RESULT`. |
| Baseline passes but every injection fails | Something is corrupting state between rounds. Check that `CORRECT` is doing what you expect, and try a short run with `VERBOSE` on. |
| `0 essential bits found` | The EBD was not generated with `BITSTREAM.SEU.ESSENTIALBITS` set, or it does not correspond to the loaded bitstream. Rebuild both together. |
| Very few upsets break the adder | Plausible, since only a subset of essential bits are critical. If the fraction looks implausibly low, widen `TEST_VECTORS`. |

For anything not covered here, contact SolidKosmos support with the log file and
the sk-raft server log.
