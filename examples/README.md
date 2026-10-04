## SolidKosmos S.A.

# SK-RAFT getting-started examples

This folder contains example designs and Python scripts for SK-RAFT. SK-RAFT is the EDA tool of SolidKosmos that emulates single-event effects (SEEs) on COTS FPGAs and SoCs.

There are four example scripts:

- **Example 1** shows the CRAM injection functions of SK-RAFT step by step on one design. First it injects into the full device, then into the essential bits only, then into the essential bits of one pblock only.
- **Example 2** shows how SK-RAFT accesses the design through BSCAN. It compares the fault tolerance of a simplex adder and a TMR adder.
- **Example 3** injects faults into flip-flops and into distributed RAM (LUTRAM):
  - Part 1 injects into a shift register with a feedback loop. It shows how a fault moves along the chain of the shift register.
  - Part 2 writes known words into a LUTRAM array and injects faults into the array. Then it reads back the array through BSCAN and shows the location of each flip.
- **Example 4** shows that a BRAM has two separate frame types: configuration and content. It injects faults into the configuration frames first, and then into the content frames. ECC logic in the fabric protects the content. The example does not use the built-in ECC of the BRAM.

The examples show how to use the API and the functions of the tool. They are not validated fault-injection test methods. They show *how* to operate SK-RAFT in a given scenario. They do not show how to design a complete campaign for your own design. For the details of each example, read the comments in the code and the VHDL of the target design. Each README below is a quick start.

## Layout

```
examples/
├── example1/ .. example4/             Python API examples (src/main.py)
└── hw/                                 Vivado project (create_project.tcl)
    ├── sources_1/new/                   VHDL sources
    └── xdc/                             basys3/, zedboard/, custom_template/
```

## Examples

| # | Example | Design | Description |
| --- | --- | --- | --- |
| 1 | [example1](example1/README.md) | [`targeted_top`](hw/sources_1/new/targeted_top.vhd) (fast and slow heartbeat counters, each in its own pblock) | Three steps on one design, each step more selective: full-device CRAM, essential bits, then the essential bits of one pblock. |
| 2 | [example2](example2/README.md) | [`bscan_adder_top`](hw/sources_1/new/bscan_adder_top.vhd) (simplex adder and TMR adder, each in its own pblock) | Adders that BSCAN controls: simplex adder against TMR adder, with single-bit upset trials that compare the failure rates. |
| 3 | [example3](example3/README.md) | [`ff_lut_top`](hw/sources_1/new/ff_lut_top.vhd) (flip-flop shift register and LUTRAM) | Injection into a flip-flop shift register and into LUTRAM through BSCAN. Two campaigns in one script. |
| 4 | [example4](example4/README.md) | [`brams_top`](hw/sources_1/new/brams_top.vhd) (one BRAM with a Hamming SEC code for each byte) | BRAM injection: configuration bits, content errors and ECC recovery. |

Each example operates with one design. The README of each example gives the files that the script uploads to the server. These files are the bitstream, and the EBD, LL and XDC files where necessary. Vivado builds these files from the `sources_1/new/*.vhd` files of that design in [`hw`](hw/).

## Requirements

- Vivado 2025.2 or a compatible version, to build the bitstream for your board.
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- An SK-RAFT server in operation, with the target board connected through USB.
- The design files that the README of each example gives. The script uploads these files to the server.

## Prebuilt design files (Basys 3)

Each example folder contains the file `src/design_files.zip`. This file contains the design files for the Digilent Basys 3 board (`xc7a35tcpg236`), built with Vivado 2025.2. If you use a Basys 3 board, you do not have to build the design. Extract the file in the `src` folder of the example:

```bash
cd example1/src
unzip design_files.zip
```

On Windows, you can also use `tar -xf design_files.zip`. For all other boards, build the design (refer to the next section).

## Build a design

Before you run an example, build its target design. The script `create_project.tcl` (in `hw/`) does the full build, from synthesis to bitstream. Then it copies the results to the folder where the `main.py` of that example expects them. You can run the example immediately after the build.

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

Examples 1 and 2 correct each upset. Example 3 programs the FPGA again at the end. Example 4 does not correct its faults. After example 4, program the FPGA again before you run a different script.

If you stop an example with Ctrl+C, the configuration of the device can stay incorrect. In that case, program the FPGA again before you run a different script.
