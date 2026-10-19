# BRAM hold register pass (7-series and UltraScale)

## The problem

SK-RAFT reads and writes BRAM content through the configuration interface
(readback, inject, revert). Every such access to a BRAM content frame
overwrites the **output latch** of the BRAMs in that frame: the value on
`DO` changes, the stored content and the FIFO pointers do not.

A design reads the latch whenever it uses `DO` after the read cycle. If a
freeze, an injection and a resume fall between the read and that use, the
design takes the overwritten value instead of the word it read.

Only ports **without the output register** (`DO_REG = 0`) are affected.
With `DOA_REG`/`DOB_REG`/`DO_REG = 1` the output register holds the word
while the clock is stopped, and nothing is needed.

## The fix: a hold register

A flip-flop on the **opposite clock edge** of the BRAM read clock copies
`DO` in the half cycle after each read. Everything that used `DO` uses the
hold register instead.

```vhdl
-- BRAM on rising_edge(clk), DO_REG = 0
process (clk) begin                       -- read enable, registered
  if rising_edge(clk) then ren_d <= bram_en; end if;
end process;
process (clk) begin                       -- hold
  if falling_edge(clk) then
    if ren_d = '1' then hold <= bram_do; end if;
  end if;
end process;
-- the design uses hold, not bram_do
```

The hold register must load **only right after a read** (CE = the registered
enable). A falling-edge register that loads every cycle is not a hold register:
after the resume it loads the overwritten latch.

`bram_hold_pass.tcl` inserts this structure into the netlist, so the
source needs no change.

## Requirements on the design

1. **The clock must stop after the edge of the hold register.** Between the
   last read edge and the freeze there must be an edge of the hold register. For a BRAM on the
   rising edge, gate the clock with a buffer that stops **low** (BUFGCE,
   or BUFGCTRL with `INIT_OUT = 0`), never BUFGCE_1. For a BRAM with an
   inverted clock (`IS_CLK*_INVERTED = 1`), the opposite. The pass warns
   when it sees a gating buffer that stops on the wrong level.
2. **Timing of the half-cycle paths is yours.** BRAM clock-to-out to the
   hold register, and the hold register to its loads, each get half a clock period. The pass
   adds no constraints; Vivado times these paths normally. If they fail,
   lower the clock or use `DO_REG = 1` on that port.
3. **Injections happen with the clock stopped.** The hold register protects the
   word read before the freeze. It does not make access to a running BRAM
   safe.

## What the pass does

Per BRAM read port (7-series RAMB18E1, RAMB36E1, FIFO18E1, FIFO36E1;
UltraScale RAMB18E2, RAMB36E2, FIFO18E2, FIFO36E2):

| Case | Action |
| --- | --- |
| `DO_REG = 1` (includes every asynchronous and FWFT 7-series FIFO); UltraScale FIFO with `REGISTER_MODE` other than UNREGISTERED | skipped |
| no output pin of the port has a load | skipped |
| port enable tied off | skipped |
| every load is already a hold register (opposite edge, CE = enable registered on the BRAM edge) | skipped |
| loads are opposite-edge flip-flops with another CE | protected (see below; reported) |
| cascade 64K x 1 (`RAM_EXTENSION`) | hold register on the UPPER output; enable covers both halves; LOWER skipped (no loads) |
| anything else with `DO_REG = 0` | hold register inserted |
| UltraScale RAMB*E2 with full-width read (`READ_WIDTH_A` = 72 / 36) | one read port on port A: DOUTADOUT, DOUTBDOUT, parity, ECC outputs |
| UltraScale RAMB*E2 otherwise | ports A and B separately (DOUTADOUT / DOUTBDOUT) |
| UltraScale cascades (`CASCADE_ORDER` not NONE), FWFT FIFO*E2 without output register, URAM | reported, not changed |

- Each load is connected according to the edge on which it samples the
  word (directly, or through logic: the registers its logic reaches):

  | Load samples on | Connected to | Why |
  | --- | --- | --- |
  | the BRAM edge | the hold register | the hold register has the word half a cycle before the load samples it: timing unchanged |
  | the opposite edge | `ren_d ? DO : hold` (one LUT3 per bit) | the hold register loads on that same edge, so a load behind it would be one cycle late; the mux gives it DO in the half cycle after a read, as before, and the hold register otherwise |
  | no clock edge (output port, ...) | the hold register | |
  | both edges (logic reaching registers on both) | the mux, with a WARNING | the logic cannot be split; a register on the BRAM edge behind it is not protected when a read is on the last edge before a freeze: fix by hand |

  With the port enable tied on, opposite-edge loads stay on `DO` (the port
  reads every cycle, so a fresh word replaces the overwritten one before
  they sample).
- Only output pins with loads get a hold flip-flop.
- Hold register CE = OR of the port enable and the output latch reset
  (RAMB18E1/RAMB36E1), registered on the BRAM edge. One enable flip-flop
  is shared by every port with the same clock and enable terms; with the
  enable tied on, no enable flip-flop is used.
- `IS_*_INVERTED` on the BRAM clock, enable and reset pins is followed.
- Every added cell has `DONT_TOUCH`.
- FIFO flags (EMPTY, FULL, ...) are not held; they are not read from
  the output latch.

## Running it

In a project, as the hook before `opt_design` (set it before you launch
`impl_1`):

```tcl
set_property STEPS.OPT_DESIGN.TCL.PRE \
    /path/to/auxiliary_components/bram_hold_pass/bram_hold_hook.tcl \
    [get_runs impl_1]
```

The examples do this in their `create_project.tcl`:
`get_started/hw/create_project.tcl` (for `brams_top`) and
`application_examples/test_neo_hardened/create_project.tcl`.

The report is `bram_hold_pass.rpt` in the impl_1 run directory. To pass
options, copy `bram_hold_hook.tcl` and add them to the `bram_hold::run`
line.

Non-project flow, after `synth_design` or `link_design`:

```tcl
source bram_hold_pass.tcl
bram_hold::run
```

Options:

| Option | Effect |
| --- | --- |
| `-dry_run` | report only, change nothing |
| `-report file` | report file name (default `bram_hold_pass.rpt`) |
| `-exclude {pattern ...}` | leave BRAM cells whose name matches a pattern (glob) alone |
| `-trust_existing` | accept any opposite-edge flip-flop as a hold register (the CE is not checked) |

Use `-exclude` for BRAMs you protect yourself, and `-trust_existing` only
when you know your opposite-edge registers load only after reads.

## Reading the report

The header counts ports and cells per decision. Then one line per BRAM:

- `held N pins`: N hold flip-flops added.
- `(K of these pins feed only opposite-edge flip-flops that are not
  hold registers ...)`: those registers had a CE that is not the registered
  enable; they were protected.
- `(K opposite-edge loads get DO in the half cycle after a read, the
  hold otherwise)`: K loads got the DO/hold mux.
- `WARNING: K loads reach registers on both clock edges`: see the table
  above; check that logic by hand.
- `already held`: the source already has the hold structure.
- `DO_REG = 1`, `no loads`, `port never enabled`, `excluded`: skipped.
- `WARNING: clock buffer ... stops on the wrong level`: fix the gating
  (requirement 1), or the hold register does not protect a read on the last edge
  before a freeze.
- `ERROR`: the cell could not be processed (for example a protected IP);
  it is left unchanged.

## Known limits

- **Built-in ECC** (`EN_ECC_WRITE = TRUE`): the hold register covers the ECC
  outputs, but an SK-RAFT injection into such a BRAM never produces an ECC
  error. The BRAM ECC encoder rewrites the stored ECC bits on the frame
  write, so the flipped bit becomes a valid codeword: silent data
  corruption, not a detected or corrected error.
- **UltraScale**: RAMB*E2 and FIFO*E2 are supported (the latch
  behaviour is the same as on 7-series). RAMB*E2 output cascades (`CASCADE_ORDER`,
  `CASDOMUX`), FWFT FIFO*E2 without the output register and URAM are
  reported, not changed.
- **Latch reset in FIFOs**: the CE of the FIFO hold register is the registered `RDEN`.
