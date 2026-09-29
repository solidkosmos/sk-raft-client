# SK-RAFT example suite

Four scripts. 
Example 1 walks through sk-raft's core targeting mechanics against one design in a single script - whole-device CRAM, then essential-bit targeting, then spatial confinement to a pblock. 
Example 2 introduces BSCAN interfacing with the internal design through SK-RAFT, with BSCAN-driven adders, a Simplex and TMR one and comparing resilience between them. 
Example 3 performs injection into Flip-Flops and Distributed RAM(LUTRAM) via targeting a feedback loop flip-flop shift register and watching the faults propagate further through the shift register's chain, and a LUTRAM memory array, where we fill it up with known words and inject into it, finally reading back where the flips landed via BSCAN.
Example 4 shows the different configuration plain of a BRAM primitive resource (protected by fabric ECC, not it's own), by injecting into it's configuration frames first then intotheir contents.

These are demonstrations of the API and the tool's capabilities, not validated fault-injection test methodologies - they show *how* to drive sk-raft for a given scenario, not what a rigorous campaign against your own design should look like. Read the code's comments and the target VHDL for the specifics of each one; every README below is a quick-start.

## Examples

| # | Example | Design required | Description |
| --- | --- | --- | --- |
| 1 | [example1](example1/README.md) | [`targeted_top`](hw/getting_started_examples_hw/sources_1/new/targeted_top.vhd) (fast/slow heartbeat generators, one per pblock) | Three widening steps against one design: whole-device CRAM, essential-bit targeting, then confined to a pblock's essential bits. |
| 2 | [example2](example2/README.md) | [`bscan_adder_top`](hw/getting_started_examples_hw/sources_1/new/bscan_adder_top.vhd) (simplex + TMR adder, each in its own pblock) | JTAG/BSCAN-driven adder: simplex vs. TMR, single-bit-upset trials comparing failure rates. |
| 3 | [example3](example3/README.md) | [`ff_lut_top`](hw/getting_started_examples_hw/sources_1/new/ff_lut_top.vhd) (FF shift register + LUTRAM) | Flip-flop shift register and LUTRAM injection over BSCAN, two campaigns in one script. |
| 4 | [example4](example4/README.md) | [`brams_top`](hw/getting_started_examples_hw/sources_1/new/brams_top.vhd) (stock BRAM + byte-lane Hamming SEC) | BRAM injection: config bits, content corruption, and ECC recovery. |

Every example is written against a specific design - each one's own README lists exactly which files (bitstream, and where needed EBD/LL/XDC) it uploads to the server, built from that design's `sources_1/new/*.vhd` in [`getting_started_examples_hw`].

## Requirements

- Vivado (2025.2 or compatible), to build the bitstream for your board.
- Python 3.9+ and the `skraft` package installed (`api/python`).
- A running sk-raft server, with the target board connected over USB.
- The design files each example's README lists (bitstream, and where needed EBD/LL/XDC); the script uploads them to the server.

## Building a design

Each example needs its target design built and loaded before you run it.
`create_project.tcl` (in `hw/getting_started_examples_hw/`) does the whole
build -- synthesis through bitstream -- and drops the results exactly where
that example's `main.py` expects them, so it's runnable right after:

```bash
cd hw/getting_started_examples_hw
vivado -mode batch -source create_project.tcl -tclargs <device> <top>
```

`<device>` selects the board; `<top>` selects which example you're building
for:

| `<top>` | Builds for |
| --- | --- |
| `targeted_top` | example1 |
| `bscan_adder_top` | example2 |
| `ff_lut_top` | example3 |
| `brams_top` | example4 |

Only `basys3` and `zedboard` are tested/shipped as `<device>` today. To add
your own board, see "Building a bitstream" in
[`hw/getting_started_examples_hw/README.md`](hw/getting_started_examples_hw/README.md#building-a-bitstream)
-- it walks through copying `xdc/custom_template/`, filling in your pins,
registering the board in `device_info`, and the exact build command to run
once that's done.

Add `-gui` anywhere in the args to open the finished project in the Vivado
GUI afterward instead of exiting, e.g.:

```bash
vivado -mode batch -source create_project.tcl -tclargs zedboard brams_top -gui
```

On success the bitstream (and EBD/LL/`board.xdc`, where that example needs
them) are copied straight into `example<N>/src/design_files/` -- nothing to
copy by hand before the next step.

## Running an example

```bash
cd exampleN/src
python main.py
```

No CLI flags anywhere in the suite - every example is configured by editing the constants of its `main.py` (`SK_RAFT_SERVER_IP`, `DEVICE`, `design`, and whatever else that example needs), then run as-is. Every example injects until you press Enter, then moves on to its next stage or finishes.

Examples 1 and 2 revert every upset and example 3 reprograms when it finishes; example 4 leaves its faults in place. Interrupting any of them with Ctrl-C can leave the device corrupted - reprogram before running anything else that expects a clean configuration.
