# get_started_examples

FPGA fault-injection / side-channel testing tool. Each top-level design in
`sources_1/new/` exercises a different fabric element (FF, LUTRAM, BRAM)
driven and read back over JTAG/BSCAN, so results can be compared across
elements under the same fault-injection setup.

## Examples

- `targeted_top` -- two independent heartbeat counters (slow, fast) for
  targeted fault-injection experiments.
- `bscan_adder_top` -- JTAG/BSCAN-driven adder: two BSCAN write channels feed
  a single adder and a TMR adder, with the single adder's sum and the TMR's
  result each read back over their own channel.
- `ff_lut_top` -- free-running FF shift register (JTAG clock-gated) and an
  address-mapped LUTRAM, both driven over BSCAN.
- `brams_top` -- stock Block RAM with byte-lane Hamming SEC, driven over
  independent JTAG/BSCAN address and data channels.

Each is a self-contained top -- there is no single default synthesis top for
the project.

## Building a bitstream

`create_project.tcl` creates the Vivado project, picks one of the examples
above as the synthesis top, and builds straight through to a bitstream. You
only need to name the board and the example -- the script looks up that
board's dedicated XDC from `xdc/<device>/<top>.xdc`, shipped next to it:

```
vivado -mode batch -source create_project.tcl -tclargs <device> <top> [project_name] [project_dir] [-gui]
```

Example:

```
vivado -mode batch -source create_project.tcl -tclargs basys3 brams_top
```

Add `-gui` (anywhere in the args) to open the built project in the Vivado
GUI afterward -- for inspection or further changes -- instead of exiting.

The bitstream lands at `<project_dir>/<project_name>.runs/impl_1/<top>.bit`,
and for `targeted_top`/`bscan_adder_top`/`ff_lut_top`/`brams_top` it (plus
EBD/LL where produced, and the XDC as `board.xdc`) is also copied straight
into that top's `example<N>/src/design_files/`, so the matching example is
runnable right after the build with no manual copying.

Known devices: `basys3` (Digilent Basys-3) and `zedboard` (Zedboard,
`xc7z020clg484-1`) -- only these two are tested/shipped. To add your own
board:

1. `cp -r xdc/custom_template xdc/<your_board_name>`
2. Fill in the PACKAGE_PIN/IOSTANDARD placeholders (and pblock ranges, if
   used) in each `.xdc` file there.
3. Add a `<your_board_name>` entry to `device_info` in `create_project.tcl`
   with just `part` and `clk_freq` -- `g_family` is derived straight from
   the part's Vivado `ARCHITECTURE` property, not something you supply:
   ```tcl
   my_board {part xc7a100tcsg324-1 clk_freq 100}
   ```
4. Build it the same way as any other board, using the name you picked:
   ```
   vivado -mode batch -source create_project.tcl -tclargs my_board brams_top
   ```

`get_started_examples_portable.zip` contains this script, `xdc/`, and every
VHDL source, ready to run as above without anything else.

### Device family (`g_family` generic)

Two wrappers take a `g_family` generic (`"7SERIES"`, `"ULTRASCALE"`, or
`"ULTRASCALEPLUS"`) that selects which primitive they instantiate:

- `bram_sdp_native_wrapper` -- `RAMB36E1` vs `RAMB36E2`
- `clk_gen_wrapper` -- `PLLE2_BASE` vs `PLLE3_BASE` vs `PLLE4_BASE`

`create_project.tcl` sets this for you: it queries the target part's
Vivado `ARCHITECTURE` property and passes the matching `g_family` (plus
`clk_freq`) as a project generic, overriding the VHDL default. You don't
set or override this yourself for a known device -- it's derived from
whatever `part` you give that device in `device_info`.
