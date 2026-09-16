# LUTRAM injection with a BSCAN memory self-test

Every earlier example upsets configuration memory, which changes the circuit
itself. This one upsets LUTRAM, the distributed memory built out of the LUT
storage cells in a slice. The distinction matters more than it first appears:

* A **CRAM** upset alters a LUT truth table, a routing switch or a control bit.
  The circuit is now wired differently and stays that way until the device is
  reconfigured or the bit is scrubbed.
* A **LUTRAM** upset alters data the design wrote at runtime. The cells live in
  the same physical storage as configuration and are addressed through the same
  configuration path, but their contents belong to the running design, not to
  the bitstream.

That overlap has a consequence worth understanding before interpreting any
result here. Because LUTRAM contents sit inside the configuration frames, a
readback of those frames returns runtime data rather than what the bitstream
loaded, and a blind scrub would overwrite live memory with stale initial values.

The design under test is a small memory in LUTRAM, reachable over JTAG. A known
pattern is written into it, the clock is stopped so nothing but an injected
fault can change it, and then the LUTRAM bits are upset and the memory read
back. Every corrupted word is reported with the value it should hold beside the
value it actually holds.

## The design under test

Three BSCAN USER registers form the interface:

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | read/write | `CLK_EN`, clock enable |
| USER2 | 4 bits | read/write | address select |
| USER3 | 32 bits | read/write | data at the selected address |

Reading a word means writing the address to USER2 and reading USER3. 
The script uses ten words of thirty-two bits, 320 bits of
memory in total.

## How injection is confined

No pblock and no XDC are involved here, and none are needed. The logic location
file names every LUTRAM bit in the design, the server reads it, and
`InjectionArea.LUTRAM` narrows injection to exactly those bits. Nothing outside
the memory is ever touched.

That is worth dwelling on, because it also protects the measurement. USER1 to
USER3 are the only way in or out of the design, so if an upset could land in the
BSCAN interface or the logic around it, a wrong value on USER3 would be
ambiguous: corrupted memory, or a corrupted path reporting perfectly good
memory, with nothing in the output to tell the two apart. Restricting the
injection area to LUTRAM rules that out by construction. Everything reported is
the fault under test rather than the instrument failing.

## The pattern and the stopped clock

Before injecting, the script writes a known value to each of the ten words:

```
pattern(address) = 0xA5A5A5A5 ^ (address * 0x01010101)
```

Alternating bits mean a single upset anywhere in a word is visible in the
readback, and a different value at every address means a mis-addressed read
shows up as clearly as a corrupted one. Address 0 holds `0xa5a5a5a5`, address 1
holds `0xa4a4a4a4`, address 2 holds `0xa7a7a7a7`, and so on.

The clock runs while the pattern is written and is then stopped through USER1.
With the design frozen the memory contents are stable, so any difference in a
later readback can only have come from an injected upset.

The pattern is read straight back as a baseline before anything is injected. If
that read does not match, the run stops immediately.

## What the test does

1. Connects to a running sk-raft server over TCP.
2. Attaches to the target device (`xc7a35t` by default).
3. Loads the bitstream and LL file, then programs the device.
4. Writes the pattern into all ten words and stops the clock.
5. Reads it back as a baseline and stops if it does not match.
6. Injects into LUTRAM, in one of the two modes below.
7. Reports every word that no longer holds the value it was given.

Upsets are **not corrected**. A flipped LUTRAM bit is a corrupted memory cell,
so the corruption stays for the rest of the run and the memory ends it dirty.

## Requirements

* Python 3.9 or later.
* The `skraft` Python package installed in your environment.
* `reporting.py`, which ships with these examples, importable from the same
  directory.
* A running sk-raft server with the target board connected to the host over USB.
* A bitstream and its logic location file, both on the **server** filesystem.

## Preparing the design

The LL file is produced by asking the bitstream writer for it:

```tcl
write_bitstream -logic_location_file -force tester.bit
```

This writes `tester.ll` next to `tester.bit`, listing each memory bit with its
position and the net it belongs to. Both files must come from the same
implementation run, or injection will be aimed at locations that no longer
correspond to where the memory sits.

Confirm the array was actually inferred into LUTRAM. A memory this small can end
up in registers, and the tools sometimes reach for a block RAM instead. Either
way there would be no LUTRAM bits to find, so force it where it matters:

```tcl
set_property RAM_STYLE distributed [get_cells mem_inst/mem_reg]
```

No EBD file is needed. Essential bits describe configuration memory, and this
example does not target it.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` | `"127.0.0.1"` | Address of the sk-raft server. |
| `SK_RAFT_SERVER_PORT` | `50051` | Port the sk-raft server is listening on. |
| `DEVICE` | `"xc7a35t"` | Target device identifier. |
| `BITSTREAM` | example path | Location of the `.bit` file, on the server. |
| `LL` | example path | Location of the matching `.ll` file, on the server. |
| `MODE` | `"random"` | `"random"` injects one bit at a time; `"exhaustive"` sweeps every LUTRAM bit in a single call. |
| `INJECTIONS` | `50` | Number of upsets in random mode. |
| `MEMORY_DEPTH` | `10` | Words reachable through USER2. Must match the design. |
| `USER_CLK_EN`, `USER_ADDR`, `USER_DATA` | USER1, USER2, USER3 | BSCAN register ids and widths. Must match the design. |
| `LOG_PATH` | `"lutram_injection.log"` | Transcript file. `None` disables it. |
| `VERBOSE` | `False` | Print the net name of each injected bit and the fill detail. |

Both paths are wrapped in `ServerPath`, which means they are resolved on the
sk-raft server's filesystem, not on the machine running the script. When the
server runs elsewhere, the files must exist at those paths on the server and the
server process must be able to read them. Use absolute paths.

## Running the test

Start the sk-raft server first, then:

```bash
python main.py
```

Interrupting with Ctrl-C is safe. The device is left corrupted either way.

## Interpreting the results

### Rows marked `no change`

These are the interesting rows in a random run, and the usual explanation is
benign: the LUTRAM the tools allocated is larger than the part the script reads.
A four-bit address gives sixteen possible words, `MEMORY_DEPTH` is ten, and the
distributed RAM primitives the tools choose have their own fixed depths. Any bit
belonging to a word the script never addresses is upset perfectly well but
cannot be observed through USER3.

Other explanations, worth checking if the proportions do not fit:

* The clock did not actually stop, so the design overwrote the corrupted value
  between injection and readback. Confirm USER1 gates a real clock enable.
* The design contains LUTRAM outside this memory, which the LL file lists and
  the injection area therefore includes.

### The two counts

The line reporting how many upsets corrupted a word counts injections. The line
reporting how many words are corrupted counts memory locations at the end of the
run. They measure different things and there is no reason for them to agree: one
word can be hit many times over, and forty upsets spread across ten words leaves
at most ten corrupted words.

A subtler case is a word that is hit twice in the same bit position. The second
upset restores the bit, so it counts as a change in its row but leaves the word
matching its pattern again in the final report.

## After the run

The memory is left corrupted and the script does not reprogram on the way out.
Reprogram the device before running anything else against the board.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `ModuleNotFoundError: reporting` | `reporting.py` is not in the same directory or on the Python path. |
| `Failed:` with a connection error | The server is not running, or the IP and port do not match. |
| `Failed:` on attach | The device identifier does not match anything in the chain, or another process holds the USB connection. Close any open Vivado hardware manager session. |
| `Failed:` on load, file not found | One of the two paths does not exist on the server, or points at a file that only exists on the client machine. Use absolute server paths. |
| `Failed:` on program | Usually a part mismatch. The bitstream must be built for the same device as `DEVICE`. |
| `0 LUTRAM bits in the design` | The bitstream was written without `-logic_location_file`, or the LL does not correspond to it. Also confirm the memory was inferred as distributed RAM rather than block RAM or registers. |
| The memory changes with no injection | The clock is still running. Check that USER1 gates it rather than merely being written. |
| Exhaustive mode leaves some words uncorrupted | Unexpected. The sweep should invert every readable bit, so a clean word suggests part of the memory is not being read where you think it is. |

For anything not covered here, contact SolidKosmos support with the log file and
the sk-raft server log.
