# SK-RAFT getting-started examples

## Layout

```
get_started/
├── example1/ .. example5/               SK-RAFT client examples (src/main.py)
├── list_devices.py                      lists the boards connected to the server
└── hw/                                  Vivado project (create_project.tcl)
    ├── design_examples/                 design files: design_examples.zip and build output
    ├── sources_1/new/                   VHDL sources
    └── xdc/                             basys3/, zedboard/, custom_template/
```

## Examples

| # | Example | Design | Purpose |
| --- | --- | --- | --- |
| 1 | [example1](example1/README.md) | [`targeted_top`](hw/sources_1/new/targeted_top.vhd) (fast and slow heartbeat counters, each in its own pblock) | Showing how to perform fault injection (FI) into random CRAM bits, random essential CRAM bits, and targeted FI into a Pblock. |
| 2 | [example2](example2/README.md) | [`bscan_adder_top`](hw/sources_1/new/bscan_adder_top.vhd) (simplex adder and TMR adder, each in its own pblock. Input and output are provided via BSCAN) | Showing how to set up and control a design during fault campaigns through BSCAN. |
| 3 | [example3](example3/README.md) | [`ff_lut_top`](hw/sources_1/new/ff_lut_top.vhd) (flip-flop shift register and LUTRAM) | Showing how to inject faults into the ARAM layer, e.g., flip-flop and LUTRAM contents. |
| 4 | [example4](example4/README.md) | [`brams_top`](hw/sources_1/new/brams_top.vhd) (one BRAM with a Hamming SEC code for each byte), and [`bram_readback_writeback_top`](hw/sources_1/new/bram_readback_writeback_top.vhd) in [`readback_writeback/`](example4/readback_writeback/README.md) (one BRAM with the built-in ECC, no output register) | Showing how to inject faults into the BRAMs: You corrupt CRAM bits and content data (ARAM). `readback_writeback/` shows what the BRAM outputs during and after an injection into its content: a wrong word while the clock is stopped, then the flipped bit with no ECC error. |
| 5 | [example5](example5/README.md) | [`targeted_top`](hw/sources_1/new/targeted_top.vhd) (the design of example 1: the two heartbeats are components of the design hierarchy) | Showing how to list the components of a design as a tree, from the flip-flop nets of the LL file, and how to perform random fault injection into the flip-flops of one component, with the net of each flip-flop that an upset hits. |

Each example operates with one design. The README of each example shows how to create the files that the SK-RAFT client script uploads to the SK-RAFT server for testing. These files are the bitstream and the EBD, LL and XDC files where necessary. Vivado builds these files from the `sources_1/new/*.vhd` files of that design in [`hw`](hw/).

## Requirements

- Tested with Vivado 2025.2. 
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- SK-RAFT server
- Target FPGA board connected via JTAG to the SK-RAFT server.
- The design files are listed in each example's README. The script uploads these files to the server.

## Prebuilt design files

SolidKosmos supplies prebuilt design files for the Basys 3 (`basys3`) and the ZedBoard (`zedboard`) in `hw/design_examples/design_examples.zip`. To extract them, run the script for your operating system:

```bash
cd hw/design_examples
./unzip_designs.sh        # Linux
.\unzip_designs.bat       # Windows
```

The script extracts the bitstream and the EBD, LL and XDC files of each design to `hw/design_examples/<board>/<top>/`. Then set `BOARD` in the `main.py` of the example to your board.

For all other boards, build the design as described below.

## Build a design

The script `create_project.tcl` (in `hw/`) does the full build, from synthesis to bitstream. Then it copies the results to the folder where the `main.py` of that example expects them. You can run the example immediately after the build.

```bash
cd hw
vivado -mode batch -source create_project.tcl -tclargs <device> <top>
```

`<device>` selects the board. `<top>` selects the example:

| `<top>` | Example |
| --- | --- |
| `targeted_top` | example1, example5 |
| `bscan_adder_top` | example2 |
| `ff_lut_top` | example3 |
| `brams_top` | example4 |
| `bram_readback_writeback_top` | example4 (`readback_writeback/`) |

SolidKosmos tested and supplies only `basys3` and `zedboard` as `<device>`. To add your own board, refer to "Build a bitstream" in [`hw/README.md`](hw/README.md#build-a-bitstream). That section tells you how to:

1. Copy `xdc/custom_template/`.
2. Write the pins of your board.
3. Add your board to `device_info`.
4. Run the build command.

To open the project in the Vivado GUI after the build, add `-gui` at any position in the arguments. Vivado then stays open. For example:

```bash
vivado -mode batch -source create_project.tcl -tclargs zedboard brams_top -gui
```

After a successful build, the script copies the bitstream, the EBD file, the LL file and `board.xdc` into `hw/design_examples/<device>/<top>/`. If this folder does not exist (for example, for your own board), the script creates it. You do not have to copy files manually.

### BRAM hold register pass (`brams_top`)

For `brams_top`, the build runs the BRAM hold register pass before `opt_design`. The pass is in [`auxiliary_components/bram_hold_pass`](../auxiliary_components/bram_hold_pass/README.md).

An SK-RAFT access to BRAM content frames (readback, inject, revert) overwrites the output latch of the block RAMs without an output register. The stored content does not change, but the design would read the overwritten value after the clock resumes. The pass adds a hold register (a flip-flop on the opposite clock edge) behind each BRAM output in use, so the design keeps the word it read before the freeze.

The build prints the report of the pass, and also writes it to `bram_hold_pass.rpt` in the `impl_1` run directory. For `brams_top`, the report shows the read port of `stock_bram` as held. The other tops have no block RAM, so the build does not run the pass for them.

The prebuilt `brams_top` files in `design_examples.zip` were built with the pass.

## Run an example

```bash
cd exampleN/src
python main.py
```

The examples do not use command-line options. To configure an example, change the constants at the top of its `main.py`: `SK_RAFT_SERVER_IP`, `SERIAL_NUMBER`, `BOARD` and the other constants of that example. Then run the script. To find the serial number of your board, run `python list_devices.py` in this folder.

Each example ends with exit code 0 when it is done, 1 on an error and 130 after Ctrl+C.

Examples 1 to 5 inject faults until you press Enter. Then the example continues to its next step, or it stops. The `readback_writeback` script of example 4 injects one fault and runs without input.

Examples 1 and 2 correct each upset. Examples 3, 4 and 5 program the FPGA again at the end.

Each example programs the FPGA at the start. Thus you can run the examples in any order, also after you stop one with Ctrl+C. If you write your own script, program the FPGA first.

