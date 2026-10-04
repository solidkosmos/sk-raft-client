# SK-RAFT getting-started examples

## Layout

```
examples/
├── example1/ .. example4/             SK-RAFT client examples (src/main.py)
└── hw/                                 Vivado project (create_project.tcl)
    ├── sources_1/new/                   VHDL sources
    └── xdc/                             basys3/, zedboard/, custom_template/
```

## Examples

| # | Example | Design | Description |
| --- | --- | --- | --- |
| 1 | [example1](example1/README.md) | [`targeted_top`](hw/sources_1/new/targeted_top.vhd) (fast and slow heartbeat counters, each in its own pblock) | Showing how to perform fault injection (FI) into random CRAM bits, random essential CRAM bits, and targeted FI into a Pblock. |
| 2 | [example2](example2/README.md) | [`bscan_adder_top`](hw/sources_1/new/bscan_adder_top.vhd) (simplex adder and TMR adder, each in its own pblock. Input and output are provided via BSCAN) | Showing how to evaluate and compare the soft-error vulnerability of two circuits. |
| 3 | [example3](example3/README.md) | [`ff_lut_top`](hw/sources_1/new/ff_lut_top.vhd) (flip-flop shift register and LUTRAM) | Showing how to inject faults into the ARAM plane, e.g., flip-flop and LUTRAM contents. |
| 4 | [example4](example4/README.md) | [`brams_top`](hw/sources_1/new/brams_top.vhd) (one BRAM with a Hamming SEC code for each byte) | Showing how to inject faults into the BRAMs: You corrupt CRAM bits and content data (ARAM). |

Each example operates with one design. The README of each example shows how to create the files that the SK-RAFT client script uploads to the SK-RAFT server for testing. These files are the bitstream and the EBD, LL and XDC files where necessary. Vivado builds these files from the `sources_1/new/*.vhd` files of that design in [`hw`](hw/).

## Requirements

- Tested with Vivado 2025.2. 
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- SK-RAFT server
- Target FPGA board connected via JTAG to the SK-RAFT server.
- The design files are listed in each example's README. The script uploads these files to the server.

## Prebuilt design files

We provide ready-to-use examples for various development boards. Extract the files (bitstream and the EBD, LL and XDC files) in the following directory:

```bash
cd example1/prebuild/board
unzip design_files.zip 
```

For all other boards not listed in the prebuild directory, you can build the design as described below.

## Build a design

The script `create_project.tcl` (in `hw/`) does the full build, from synthesis to bitstream. Then it copies the results to the folder where the `main.py` of that example expects them. You can run the example immediately after the build.

```bash
cd hw
vivado -mode batch -source create_project.tcl -tclargs <device> <top>
```

`<device>` selects the board. `<top>` selects the example:

| `<top>` | Example |
| --- | --- |
| `targeted_top` | example1 |
| `bscan_adder_top` | example2 |
| `ff_lut_top` | example3 |
| `brams_top` | example4 |

SolidKosmos tested and supplies only `basys3` and `zedboard` as `<device>`. To add your own board, refer to "Build a bitstream" in [`hw/README.md`](hw/README.md#build-a-bitstream). That section tells you how to:

1. Copy `xdc/custom_template/`.
2. Write the pins of your board.
3. Add your board to `device_info`.
4. Run the build command.

To open the project in the Vivado GUI after the build, add `-gui` at any position in the arguments. Vivado then stays open. For example:

```bash
vivado -mode batch -source create_project.tcl -tclargs zedboard brams_top -gui
```

After a successful build, the script copies the bitstream into `example<N>/src/design_files/`. If the example uses them, the script also copies the EBD file, the LL file and `board.xdc`. You do not have to copy files manually.

## Run an example

```bash
cd exampleN/src
python main.py
```

The examples do not use command-line options. To configure an example, change the constants at the top of its `main.py`: `SK_RAFT_SERVER_IP`, `DEVICE`, `design` and the other constants of that example. Then run the script.

Each example injects faults until you press Enter. Then the example continues to its next step, or it stops.

Examples 1 and 2 correct each upset. Example 3 programs the FPGA again at the end. Example 4 does not correct its faults. 

**[COMMENT --> We need to do this] After example 4, program the FPGA again before you run a different script.**



**[COMMENT --> We need to do this. At the start of each script, RECONFIGURE THE FPGA]** If you stop an example with Ctrl+C, the device configuration may remain incorrect. In that case, reprogram the FPGA before you run a different script.

