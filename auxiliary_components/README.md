# Auxiliary components

Reusable building blocks for designs that are tested with SK-RAFT. Each
one is independent and has its own README with the details.

| Component | What it does | Why you need it |
| --- | --- | --- |
| [`bscan/`](bscan/README.md) | VHDL for up to four JTAG USER registers (USER1 to USER4) through the BSCANE2 primitive, with a read path and a write path. | Lets the SK-RAFT client talk to your design over the same JTAG cable it uses for injection: set inputs, read results, control the clock. No UART or extra pins. |
| [`safe_clk_gen/`](safe_clk_gen/README.md) | `clk_gen_wrapper`: a PLL that makes the design clock (any output frequency) and keeps it off until the PLL has locked. 7-series, UltraScale and UltraScale+. | A clean design clock that starts without glitches. It is the clock that a BSCAN-controlled clock gate (BUFGCE) stops during an injection. |
| [`bram_hold_pass/`](bram_hold_pass/README.md) | A Vivado Tcl netlist pass that adds a hold register behind every block RAM output without an output register. | An SK-RAFT access to BRAM content frames (readback, inject, revert) overwrites the BRAM output latch. Without the hold register, the design reads that wrong value after the clock resumes. |

## How they fit together

A typical fault-injection setup with SK-RAFT stops the design, changes the
configuration memory, and starts the design again:

1. `safe_clk_gen` makes the design clock.
2. A BUFGCE gates that clock. Its enable comes from a `bscan` USER register
   (for example USER1), so the SK-RAFT client can stop and start the
   design with `write_bscan`.
3. With the clock stopped, the client injects (and reverts) bits.
4. The client starts the clock again and reads the result through other
   `bscan` USER registers.
5. `bram_hold_pass` makes sure that step 3 does not change the words the
   design read from its block RAMs before the freeze.

The `bscan` README shows the clock gate (USER1 + BUFGCE) in VHDL, with the
XDC lines and the Python calls.

## Used in

- `get_started/` (the getting-started examples): BSCAN registers, safe
  clock, and the hold pass for `brams_top` (example 4).
- `application_examples/test_neo_hardened/` (NEORV32): BSCAN registers,
  safe clock, and the hold pass.

The examples keep their own copies of the VHDL files. The copies in this
folder are the reference versions.
