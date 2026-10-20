# BRAM hold register pass (7-series and UltraScale)

## The problem

SK-RAFT reads and writes the BRAM content through the configuration interface (readback, inject and revert). Each access to a BRAM content frame changes the **output latch** of the BRAMs in that frame. The value on `DO` changes. The stored content and the FIFO pointers do not change.

A design reads the latch each time it uses `DO` after the read cycle. If a freeze, an injection and a resume occur between the read and that use, the design gets the changed value. It does not get the word that it read.

This problem occurs only on ports **without the output register** (`DO_REG = 0`). With `DOA_REG`, `DOB_REG` or `DO_REG = 1`, the output register keeps the word while the clock is stopped. These ports do not need the pass.

## The fix: a hold register

A hold register is a flip-flop on the **opposite clock edge** of the BRAM read clock. It copies `DO` in the half cycle after each read. All the logic that used `DO` uses the hold register instead.

```vhdl
-- BRAM on rising_edge(clk), DO_REG = 0
process (clk) begin                       -- read enable, registered
  if rising_edge(clk) then ren_d <= bram_en; end if;
end process;
process (clk) begin                       -- hold register
  if falling_edge(clk) then
    if ren_d = '1' then hold <= bram_do; end if;
  end if;
end process;
-- the design uses hold, not bram_do
```

The hold register must load **only directly after a read**. Its clock enable (CE) is the registered read enable. A falling-edge register that loads on each cycle is not a hold register: after the resume, it loads the changed latch.

`bram_hold_pass.tcl` adds this structure to the netlist. You do not change the source.

## Requirements on the design

1. **The clock must stop after an edge of the hold register.** Between the last read edge and the freeze, an edge of the hold register must occur. For a BRAM on the rising edge, gate the clock with a buffer that stops **low**: BUFGCE, or BUFGCTRL with `INIT_OUT = 0`. Do not use BUFGCE_1. For a BRAM with an inverted clock (`IS_CLK*_INVERTED = 1`), do the opposite. The pass gives a warning if a gating buffer stops on the wrong level.
2. **You are responsible for the timing of the half-cycle paths.** The path from the BRAM to the hold register gets half a clock period. The path from the hold register to its loads also gets half a clock period. The pass adds no constraints, and Vivado times these paths normally. If they fail, decrease the clock frequency or use `DO_REG = 1` on that port.
3. **Inject only while the clock is stopped.** The hold register keeps the word that the design read before the freeze. It does not make an access to a BRAM safe while the clock runs.
4. **Exclude the BRAMs from power optimization.** Add this line to the XDC:

   ```tcl
   set_power_opt -exclude_cells [get_cells -hier -filter {REF_NAME =~ RAMB*}]
   ```

   This prevents the tool from changing how the BRAMs do their reads. Without this line, the power optimization of `opt_design` runs after the pass and can add gating logic to a read enable, also to a read enable that is tied to 1. Then the BRAM reads less frequently than the pass expects. The XDC files of the examples in this repository have this line.

## What the pass does

The pass examines each BRAM read port of these primitives: RAMB18E1, RAMB36E1, FIFO18E1 and FIFO36E1 (7-series), and RAMB18E2, RAMB36E2, FIFO18E2 and FIFO36E2 (UltraScale).

| Case | Action |
| --- | --- |
| `DO_REG = 1`. This includes all asynchronous and FWFT 7-series FIFOs, and the UltraScale FIFOs with `REGISTER_MODE` other than UNREGISTERED. | Skipped |
| No output pin of the port has a load. | Skipped |
| The port enable is tied to 0. | Skipped |
| Each load is already a hold register (opposite edge, CE = the read enable registered on the BRAM edge). | Skipped |
| The loads are opposite-edge flip-flops with a different CE. | Protected (see below) and reported |
| 64K x 1 cascade (`RAM_EXTENSION`). | Hold register on the UPPER output. Its enable includes both halves. The LOWER output has no loads and is skipped. |
| All other ports with `DO_REG = 0`. | Hold register added |
| UltraScale RAMB*E2 with full-width read (`READ_WIDTH_A` = 72 or 36). | One read port on port A: DOUTADOUT, DOUTBDOUT, the parity outputs and the ECC outputs |
| Other UltraScale RAMB*E2. | Ports A and B separately (DOUTADOUT and DOUTBDOUT) |
| UltraScale cascades (`CASCADE_ORDER` other than NONE), FWFT FIFO*E2 without the output register, and URAM. | Reported, not changed |

- The pass connects each load according to the clock edge on which the load samples the word. A load can be a register, or logic that goes to registers.

  | Load samples on | Connected to | Reason |
  | --- | --- | --- |
  | The BRAM edge | The hold register | The hold register has the word half a cycle before the load samples it. The timing does not change. |
  | The opposite edge | A multiplexer (one LUT3 for each bit). It selects `DO` in the half cycle after a read, and the hold register at all other times. | The hold register loads on the same edge as the load, so a load behind it gets the word one cycle late. The multiplexer gives the load `DO` directly after a read, as before. |
  | No clock edge (for example an output port) | The hold register | |
  | Both edges (logic that goes to registers on both edges) | The multiplexer, with a warning | The pass cannot split the logic. A register on the BRAM edge behind this logic is not protected if a read occurs on the last edge before a freeze. Correct this logic manually. |

  If the port enable is tied to 1, the opposite-edge loads stay on `DO`. The port reads on each cycle, so a new word replaces the changed latch before these loads sample it. This is correct only with requirement 4.
- Only output pins with loads get a hold flip-flop.
- The CE of the hold register is the OR of the port enable and the output latch reset (RAMB18E1 and RAMB36E1), registered on the BRAM edge. Ports with the same clock and the same enable signals share one enable flip-flop. If the enable is tied to 1, the pass adds no enable flip-flop.
- The pass uses the `IS_*_INVERTED` properties of the BRAM clock, enable and reset pins.
- All the cells that the pass adds have `DONT_TOUCH`.
- The pass does not add hold registers to the FIFO flags (EMPTY, FULL and the other flags). The flags do not come from the output latch.

## Running it

In a project, set the pass as the hook before `opt_design`. Do this before you start `impl_1`:

```tcl
set_property STEPS.OPT_DESIGN.TCL.PRE \
    /path/to/auxiliary_components/bram_hold_pass/bram_hold_hook.tcl \
    [get_runs impl_1]
```

The examples do this in their `create_project.tcl` files: `get_started/hw/create_project.tcl` (for `brams_top`) and `application_examples/test_neo_hardened/create_project.tcl`.

The pass writes its report to `bram_hold_pass.rpt` in the `impl_1` run directory. To give options, copy `bram_hold_hook.tcl` and add the options to the `bram_hold::run` line.

In a non-project flow, run the pass after `synth_design` or `link_design`:

```tcl
source bram_hold_pass.tcl
bram_hold::run
```

Options:

| Option | Effect |
| --- | --- |
| `-dry_run` | Writes the report only. Changes nothing. |
| `-report file` | The name of the report file. The default is `bram_hold_pass.rpt`. |
| `-exclude {pattern ...}` | Does not change the BRAM cells whose names match a pattern (glob). |
| `-trust_existing` | Accepts each opposite-edge flip-flop as a hold register. The pass does not examine its CE. |

Use `-exclude` for BRAMs that you protect yourself. Use `-trust_existing` only if you know that your opposite-edge registers load only after reads.

## Reading the report

The header gives the number of ports and cells for each decision. Then the report has one line for each BRAM:

- `held N pins`: the pass added N hold flip-flops.
- `(K of these pins feed only opposite-edge flip-flops that are not hold registers ...)`: the CE of these registers is not the registered read enable. The pass protected them.
- `(K opposite-edge loads get DO in the half cycle after a read, the hold otherwise)`: K loads are connected through the multiplexer.
- `WARNING: K loads reach registers on both clock edges`: refer to the table above, and examine this logic manually.
- `already held`: the source already has the hold structure.
- `DO_REG = 1`, `no loads`, `port never enabled`, `excluded`: the pass skipped the port.
- `WARNING: clock buffer ... stops on the wrong level`: correct the clock gating (requirement 1). If you do not, the hold register does not protect a read on the last edge before a freeze.
- `ERROR`: the pass cannot process the cell (for example, a protected IP). The cell does not change.

## Known limits

- **Built-in ECC** (`EN_ECC_WRITE = TRUE`): the hold register also keeps the ECC outputs. But an SK-RAFT injection into such a BRAM never causes an ECC error. When SK-RAFT writes the frame, the ECC encoder of the BRAM calculates new ECC bits for the changed data. Thus the stored word is a valid ECC word, and the flipped bit is silent data corruption. The ECC does not detect or correct it.
- **UltraScale**: the pass supports RAMB*E2 and FIFO*E2. The latch behaviour is the same as on 7-series. The pass reports RAMB*E2 output cascades (`CASCADE_ORDER`, `CASDOMUX`), FWFT FIFO*E2 without the output register, and URAM, but does not change them.
- **Latch reset in FIFOs**: the CE of a FIFO hold register is the registered `RDEN`.
