# BRAM shadow register pass (7-series and UltraScale)

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

## The fix: a shadow register

A flip-flop on the **opposite clock edge** of the BRAM read clock copies
`DO` in the half cycle after each read. Everything that used `DO` uses the
shadow instead.

```vhdl
-- BRAM on rising_edge(clk), DO_REG = 0
process (clk) begin                       -- read enable, registered
  if rising_edge(clk) then ren_d <= bram_en; end if;
end process;
process (clk) begin                       -- shadow
  if falling_edge(clk) then
    if ren_d = '1' then shadow <= bram_do; end if;
  end if;
end process;
-- the design uses shadow, not bram_do
```

The shadow must load **only right after a read** (CE = the registered
enable). A falling-edge register that loads every cycle is not a shadow:
after the resume it loads the overwritten latch.

`bram_shadow_pass.tcl` inserts this structure into the netlist, so the
source needs no change.

## Requirements on the design

1. **The clock must stop after the shadow edge.** Between the last read
   edge and the freeze there must be a shadow edge. For a BRAM on the
   rising edge, gate the clock with a buffer that stops **low** (BUFGCE,
   or BUFGCTRL with `INIT_OUT = 0`), never BUFGCE_1. For a BRAM with an
   inverted clock (`IS_CLK*_INVERTED = 1`), the opposite. The pass warns
   when it sees a gating buffer that stops on the wrong level.
2. **Timing of the half-cycle paths is yours.** BRAM clock-to-out to the
   shadow, and shadow to its loads, each get half a clock period. The pass
   adds no constraints; Vivado times these paths normally. If they fail,
   lower the clock or use `DO_REG = 1` on that port.
3. **Injections happen with the clock stopped.** The shadow protects the
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
| every load is already a shadow (opposite edge, CE = enable registered on the BRAM edge) | skipped |
| loads are opposite-edge flip-flops with another CE | protected (see below; reported) |
| cascade 64K x 1 (`RAM_EXTENSION`) | shadow on the UPPER output; enable covers both halves; LOWER skipped (no loads) |
| anything else with `DO_REG = 0` | shadow inserted |
| UltraScale RAMB*E2 with full-width read (`READ_WIDTH_A` = 72 / 36) | one read port on port A: DOUTADOUT, DOUTBDOUT, parity, ECC outputs |
| UltraScale RAMB*E2 otherwise | ports A and B separately (DOUTADOUT / DOUTBDOUT) |
| UltraScale cascades (`CASCADE_ORDER` not NONE), FWFT FIFO*E2 without output register, URAM | reported, not changed |

- Each load is connected according to the edge on which it samples the
  word (directly, or through logic: the registers its logic reaches):

  | Load samples on | Connected to | Why |
  | --- | --- | --- |
  | the BRAM edge | the shadow | the shadow has the word half a cycle before the load samples it: timing unchanged |
  | the opposite edge | `ren_d ? DO : shadow` (one LUT3 per bit) | the shadow loads on that same edge, so a load behind it would be one cycle late; the mux gives it DO in the half cycle after a read, as before, and the shadow otherwise |
  | no clock edge (output port, ...) | the shadow | |
  | both edges (logic reaching registers on both) | the mux, with a WARNING | the logic cannot be split; a register on the BRAM edge behind it is not protected when a read is on the last edge before a freeze: fix by hand |

  With the port enable tied on, opposite-edge loads stay on `DO` (the port
  reads every cycle, so a fresh word replaces the overwritten one before
  they sample).
- Only output pins with loads get a shadow flip-flop.
- Shadow CE = OR of the port enable and the output latch reset
  (RAMB18E1/RAMB36E1), registered on the BRAM edge. One enable flip-flop
  is shared by every port with the same clock and enable terms; with the
  enable tied on, no enable flip-flop is used.
- `IS_*_INVERTED` on the BRAM clock, enable and reset pins is followed.
- Every added cell has `DONT_TOUCH`.
- FIFO flags (EMPTY, FULL, ...) are not shadowed; they are not read from
  the output latch.

## Running it

In a project, as the hook before `opt_design` (set it before you launch
`impl_1`):

```tcl
set_property STEPS.OPT_DESIGN.TCL.PRE \
    /path/to/auxiliary_components/bram_shadow_pass/bram_shadow_hook.tcl \
    [get_runs impl_1]
```

The examples do this in their `create_project.tcl`:
`get_started/hw/create_project.tcl` (for `brams_top`) and
`application_examples/test_neo_hardened/create_project.tcl`.

The report is `bram_shadow_pass.rpt` in the impl_1 run directory. To pass
options, copy `bram_shadow_hook.tcl` and add them to the `bram_shadow::run`
line.

Non-project flow, after `synth_design` or `link_design`:

```tcl
source bram_shadow_pass.tcl
bram_shadow::run
```

Options:

| Option | Effect |
| --- | --- |
| `-dry_run` | report only, change nothing |
| `-report file` | report file name (default `bram_shadow_pass.rpt`) |
| `-exclude {pattern ...}` | leave BRAM cells whose name matches a pattern (glob) alone |
| `-trust_existing` | accept any opposite-edge flip-flop as a shadow (the CE is not checked) |

Use `-exclude` for BRAMs you protect yourself, and `-trust_existing` only
when you know your opposite-edge registers load only after reads.

## Reading the report

The header counts ports and cells per decision. Then one line per BRAM:

- `shadowed N pins`: N shadow flip-flops added.
- `(K of these pins feed only opposite-edge flip-flops that are not
  shadows ...)`: those registers had a CE that is not the registered
  enable; they were protected.
- `(K opposite-edge loads get DO in the half cycle after a read, the
  shadow otherwise)`: K loads got the DO/shadow mux.
- `WARNING: K loads reach registers on both clock edges`: see the table
  above; check that logic by hand.
- `already shadowed`: the source already has the shadow structure.
- `DO_REG = 1`, `no loads`, `port never enabled`, `excluded`: skipped.
- `WARNING: clock buffer ... stops on the wrong level`: fix the gating
  (requirement 1), or the shadow does not protect a read on the last edge
  before a freeze.
- `ERROR`: the cell could not be processed (for example a protected IP);
  it is left unchanged.

## Known limits

- **Built-in ECC** (`EN_ECC_WRITE = TRUE`): the shadow covers the ECC
  outputs, but an SK-RAFT injection into such a BRAM never produces an ECC
  error. The BRAM ECC encoder rewrites the stored ECC bits on the frame
  write, so the flipped bit becomes a valid codeword: silent data
  corruption, not a detected or corrected error.
- **UltraScale**: RAMB*E2 and FIFO*E2 are supported and checked by
  name with `us_naming_test` (the latch behaviour is the same as on
  7-series). RAMB*E2 output cascades (`CASCADE_ORDER`,
  `CASDOMUX`), FWFT FIFO*E2 without the output register and URAM are
  reported, not changed.
- **Latch reset in FIFOs**: the FIFO shadow CE is the registered `RDEN`.

## Naming test (UltraScale, no board)

`us_naming_test/` checks that the pass finds and handles every UltraScale
primitive case. It synthesizes `us_naming_top.v` (one RAMB36E2 / RAMB18E2 /
FIFO36E2 per case), runs the pass, checks the number of shadow flip-flops
and the report line of each instance, and implements the result to a
bitstream. It needs no board and no license: by default it uses the first
installed part of a list of free UltraScale devices (xcku025, xcku035,
xcau10p, xcau15p).

```
cd us_naming_test
vivado -mode batch -source run_naming_test.tcl
vivado -mode batch -source run_naming_test.tcl -tclargs <part>
```

The log ends with each check and `NAMING TEST: PASS` or `FAIL`. The pass
report is `us_naming_test/us_naming_pass.rpt`.

## Tests

On the Basys 3 (the designs are in `bug_tests/` of this repository, 1000
freeze-inject-resume repetitions each, with a control built without the
pass):

| Test | Result |
| --- | --- |
| `bram_shadow_tcl`: SDP x36, consumer on `DO` | with the pass 0 / 1000 failures; without 999 / 1000 |
| `bram_shadow_casc`: 64K x 1 cascade | with the pass 0 / 1000; without 486 / 1000 (1-bit data) |
| `bram_shadow_pipe`: falling-edge register with CE = 1, plus a register that checks it is not delayed | with the pass 0 / 1000, timing unchanged; without (and with `-trust_existing`) 999 / 1000 |
| `bram_shadow_tcl/check_designs.tcl`: dry run on every bug_tests netlist | every decision as expected |

UltraScale: `us_naming_test` PASS on xcku025-ffva1156-1-c (all 9 cases,
shadow cells kept through routing, bitstream written).
