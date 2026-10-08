# SK-RAFT getting-started examples

## Layout

```
get_started/
├── example1/ .. example4/             SK-RAFT client examples (src/main.py)
└── hw/                                 Vivado project (create_project.tcl)
    ├── design_examples/                 design files: design_examples.zip and build output
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

SolidKosmos supplies prebuilt design files for the Basys 3 (`basys3`) and the ZedBoard (`zedboard`) in `hw/design_examples/design_examples.zip`. To extract them, run the script for your operating system:

```bash
cd hw/design_examples
./unzip_designs.sh        # Linux
unzip_designs.bat         # Windows
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

After a successful build, the script copies the bitstream, the EBD file, the LL file and `board.xdc` into `hw/design_examples/<device>/<top>/`. If this folder does not exist (for example, for your own board), the script creates it. You do not have to copy files manually.

## Run an example

```bash
cd exampleN/src
python main.py
```

The examples do not use command-line options. To configure an example, change the constants at the top of its `main.py`: `SK_RAFT_SERVER_IP`, `SERIAL_NUMBER`, `BOARD` and the other constants of that example. Then run the script.

Each example injects faults until you press Enter. Then the example continues to its next step, or it stops.

Examples 1 and 2 correct each upset. Examples 3 and 4 program the FPGA again at the end.

Each example programs the FPGA at the start. Thus you can run the examples in any order, also after you stop one with Ctrl+C. If you write your own script, program the FPGA first.

