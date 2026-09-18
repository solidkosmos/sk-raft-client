# get_started_examples

FPGA fault-injection / side-channel testing tool. Each top-level design in
`sources_1/new/` exercises a different fabric element (FF, LUTRAM, BRAM,
DSP48) driven and read back over JTAG/BSCAN, so results can be compared
across elements under the same fault-injection setup.

## Examples

- `adder_top` -- static combinational adder (+5) driving LEDs directly from
  switch inputs; first example in the get-started series.
- `targeted_top` -- two independent heartbeat counters (slow, fast) for
  targeted fault-injection experiments.
- `bscan_adder_top` -- JTAG/BSCAN-driven adder: two BSCAN write channels feed
  a single adder and a TMR adder, with the single adder's sum and the TMR's
  result each read back over their own channel.
- `dsp_target_top` -- two identical DSP48-multiplier instances (clean
  reference vs. fault-injection target), each fed its own JTAG/BSCAN
  operand-write channel, results read back independently for A/B comparison.
- `ff_lut_top` -- free-running FF shift register (JTAG clock-gated) and an
  address-mapped LUTRAM, both driven over BSCAN.
- `brams_top` -- stock and ECC Block RAM instances driven over independent
  JTAG/BSCAN address and data channels, for A/B fault-injection comparison.

Each is a self-contained top -- there is no single default synthesis top for
the project. Set whichever example you're building as the top before
synthesis:

```tcl
set_property top adder_top [get_filesets sources_1]
update_compile_order -fileset sources_1
```

## Recreating the project

`create_project.tcl` rebuilds the Vivado project from the sources next to it,
targeting whatever part and constraints file you supply -- nothing about the
target device or board is hardcoded.

```
vivado -mode batch -source create_project.tcl -tclargs <part> <xdc_path> [project_name] [project_dir]
```

Example (Basys-3):

```
vivado -mode batch -source create_project.tcl -tclargs xc7a35tcpg236-1 C:/boards/Basys-3-Master.xdc
```

`get_started_examples_portable.zip` contains this script plus every VHDL
source, ready to drop next to your own XDC and run as above.

### Device family (`g_family` generic)

Three wrappers take a `g_family` generic (`"7SERIES"`, `"ULTRASCALE"`, or
`"ULTRASCALEPLUS"`) that selects which primitive they instantiate:

- `bram_sdp_native_wrapper` -- `RAMB36E1` vs `RAMB36E2`
- `dsp_wrapper` -- targets the DSP48 slice appropriate to the family
- `clk_gen_wrapper` -- `PLLE2_BASE` vs `PLLE3_BASE` vs `PLLE4_BASE`

This is set in VHDL where each example instantiates the wrapper, not as a
project property, so `create_project.tcl` cannot set it for you -- make sure
it matches the `-part` family you build with, for all three wrappers.
