# SK-RAFT example suite

Eight scripts, each a self-contained demonstration of one sk-raft API capability, ordered so each one builds on the last: whole-CRAM injection, then essential-bit targeting, then spatial confinement to a pblock, then progressively more realistic designs (BSCAN-driven adders, DSP48 multipliers, a flip-flop shift register, LUTRAM, and BRAM with ECC).

These are demonstrations of the API and the tool's capabilities, not validated fault-injection test methodologies - they show *how* to drive sk-raft for a given scenario, not what a rigorous campaign against your own design should look like. Read the code's comments and the target VHDL for the specifics of each one; every README below is a quick-start, not a full explanation.

## Examples

| # | Example | Design required | Description |
| --- | --- | --- | --- |
| 1 | [example1](example1/README.md) | none -- no design is loaded, works on an unprogrammed device | Cumulative random CRAM injection on an unprogrammed device - no bitstream needed. |
| 2 | [example2](example2/README.md) | any bitstream ([`adder_top`](../../hw/getting_started_examples_hw/sources_1/new/adder_top.vhd) suggested as a simple default) | Same as example1, but the device is programmed first, so corrupted bits belong to a known configuration. |
| 3 | [example3](example3/README.md) | any bitstream + matching EBD ([`adder_top`](../../hw/getting_started_examples_hw/sources_1/new/adder_top.vhd) suggested as a simple default) | Injection narrowed to the design's essential bits (from the EBD), random or exhaustive. |
| 4 | [example4](example4/README.md) | [`targeted_top`](../../hw/getting_started_examples_hw/sources_1/new/targeted_top.vhd) (fast/slow heartbeat generators, one per pblock) | Injection confined to a single pblock, read from the XDC. |
| 5 | [example5](example5/README.md) | [`bscan_adder_top`](../../hw/getting_started_examples_hw/sources_1/new/bscan_adder_top.vhd) (simplex + TMR adder, each in its own pblock) | JTAG/BSCAN-driven adder: simplex vs. TMR, single-bit-upset trials comparing failure rates. |
| 6 | [example6](example6/README.md) | [`dsp_target_top`](../../hw/getting_started_examples_hw/sources_1/new/dsp_target_top.vhd) (clean + target DSP48 multiplier, each in its own pblock) | JTAG/BSCAN-driven signed multiply: a clean DSP48 reference vs. a fault-injection target. |
| 7 | [example7](example7/README.md) | [`ff_lut_top`](../../hw/getting_started_examples_hw/sources_1/new/ff_lut_top.vhd) (FF shift register + LUTRAM) | Flip-flop shift register and LUTRAM injection over BSCAN, two campaigns in one script. |
| 8 | [example8](example8/README.md) | [`brams_top`](../../hw/getting_started_examples_hw/sources_1/new/brams_top.vhd) (stock BRAM + byte-lane Hamming SEC) | BRAM injection: config bits, content corruption, and ECC recovery. |

For 2 and 3, any design works since neither exercises design-specific logic over BSCAN -- `adder_top` is just a simple, easy-to-watch-externally default. For 4-8, the script's BSCAN register mapping and pblock names are written against that specific design's `sources_1/new/*.vhd` in [`getting_started_examples_hw`](../../hw/getting_started_examples_hw/) -- build that one (with a matching XDC/EBD/LL as each example's own README lists) before running.

## Requirements

- Python 3.9+ and the `skraft` package installed (`api/python`).
- A running sk-raft server, with the target board connected over USB.
- Each example's own README lists the design files (bitstream, and where needed EBD/LL/XDC) it expects on the **server**.

## Running an example

```bash
cd exampleN/src
python main.py
```

Each script prints an `Example N: ...` banner naming itself, then follows its own README's Configuration section for what to change before running. Most examples leave the device corrupted when they finish or are interrupted - reprogram before running anything else that expects a clean configuration.
