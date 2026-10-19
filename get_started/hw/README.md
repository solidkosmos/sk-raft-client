# Hardware designs for the getting-started examples

This folder contains the Vivado build script, the VHDL sources and the constraint files of the getting-started examples. Each top-level design in `sources_1/new/` uses a different fabric element (FF, LUTRAM, BRAM). The scripts control each design and read back its data through JTAG/BSCAN. Thus you can compare the results of the different elements with the same fault-injection setup.

## Designs

- `targeted_top`: two independent heartbeat counters (slow and fast) for targeted fault-injection tests.
- `bscan_adder_top`: two adders that BSCAN controls. One BSCAN write register (USER1) supplies the operands to a simplex adder and to a TMR adder. The script reads the result of the simplex adder through USER2 and the result of the TMR adder through USER3.
- `ff_lut_top`: a flip-flop shift register that operates continuously, and a LUTRAM with an address map. The JTAG interface controls the clock of the shift register. BSCAN controls the two elements.
- `brams_top`: one block RAM with a Hamming SEC code for each byte. Independent JTAG/BSCAN registers supply the address and the data.
- `bram_readback_writeback_top`: one block RAM with the built-in ECC and no output register, for the `bram_readback_writeback` example. The read port is always enabled, and JTAG/BSCAN reads the BRAM outputs directly. `design_examples.zip` does not include this design.

Each design is a full top-level design. The project has no default synthesis top.

## Prebuilt designs

`design_examples/design_examples.zip` contains the prebuilt design files of the four designs for the Basys 3 (`basys3`) and the ZedBoard (`zedboard`). To extract them, run the script for your operating system:

```
cd design_examples
./unzip_designs.sh        # Linux
unzip_designs.bat         # Windows
```

The script extracts the files to `design_examples/<board>/<top>/`. For other boards, build the designs as described below.

## Build a bitstream

The script `create_project.tcl` makes the Vivado project, sets one of the designs above as the synthesis top, and builds the bitstream. You must give only the board and the design. The script finds the XDC file of that board in `xdc/<device>/<top>.xdc`.

```
vivado -mode batch -source create_project.tcl -tclargs <device> <top> [project_name] [project_dir] [-gui]
```

Example:

```
vivado -mode batch -source create_project.tcl -tclargs basys3 brams_top
```

To open the project in the Vivado GUI after the build, add `-gui` at any position in the arguments. Vivado then stays open, and you can examine or change the project.

The script writes the bitstream to `<project_dir>/<project_name>.runs/impl_1/<top>.bit`. For `targeted_top`, `bscan_adder_top`, `ff_lut_top`, `brams_top` and `bram_readback_writeback_top`, the script also copies these files into `design_examples/<device>/<top>/`:

- The bitstream.
- The EBD and LL files, if Vivado makes them.
- The XDC file, with the name `board.xdc`.

If this folder does not exist (for example, for your own board), the script creates it. Files from `design_examples.zip` in that folder are overwritten. Thus you can run the related example immediately after the build. Set `BOARD` in its `main.py` to the name of the board.

For `brams_top`, the script sets the BRAM shadow register pass as the hook before `opt_design` (`STEPS.OPT_DESIGN.TCL.PRE` of `impl_1`). The pass is `auxiliary_components/bram_shadow_pass/bram_shadow_hook.tcl` at the root of the repository; the list `tops_with_bram_shadow` in the script selects the tops. The pass writes `bram_shadow_pass.rpt` in the `impl_1` run directory, and the script prints it after the build. Refer to the [pass README](../../auxiliary_components/bram_shadow_pass/README.md) for what it changes and why.

The known devices are `basys3` (Digilent Basys 3, `xc7a35tcpg236-1`) and `zedboard` (ZedBoard, `xc7z020clg484-1`). SolidKosmos tested and supplies only these two boards.

To add your own board:

1. Copy the template folder:
   ```
   cp -r xdc/custom_template xdc/<your_board_name>
   ```
2. In each `.xdc` file of the new folder, replace the PACKAGE_PIN and IOSTANDARD placeholders. If you use pblocks, also replace the pblock ranges.
3. In `create_project.tcl`, add an entry for `<your_board_name>` to `device_info`. Give only `part` and `clk_freq`. The script gets `g_family` from the Vivado `ARCHITECTURE` property of the part. For example:
   ```tcl
   my_board {part xc7a100tcsg324-1 clk_freq 100}
   ```
4. Build the design with the name of your board, as for all other boards:
   ```
   vivado -mode batch -source create_project.tcl -tclargs my_board brams_top
   ```

### Device family (`g_family` generic)

Two wrappers have a `g_family` generic (`"7SERIES"`, `"ULTRASCALE"` or `"ULTRASCALEPLUS"`). This generic selects the primitive that the wrapper uses:

- `bram_sdp_native_wrapper`: `RAMB36E1` or `RAMB36E2`.
- `clk_gen_wrapper`: `PLLE2_BASE`, `PLLE3_BASE` or `PLLE4_BASE`.

`create_project.tcl` sets this generic for you. It reads the Vivado `ARCHITECTURE` property of the target part. Then it gives the related `g_family` value (and `clk_freq`) as a project generic, which replaces the default value in the VHDL. For a known device, you do not set this generic yourself. The script gets it from the `part` value of the device in `device_info`.
