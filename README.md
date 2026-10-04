## SolidKosmos S.A.

# SK-RAFT

SK-RAFT is an EDA software tool for fault injection in AMD-Xilinx FPGAs. It emulates single-event effects (SEEs), for example single-event upsets (SEUs), in the memories of the FPGA.

This repository contains the open-source SK-RAFT Python client and the getting-started examples. The client operates only with an SK-RAFT server. The SK-RAFT server is proprietary software of SolidKosmos, and it must have a valid trial or commercial licence.

**Get a trial licence:** `<trial link: TBD>`

## Main functions

- **Injection into the configuration RAM (CRAM).** The CRAM contains the configuration of the FPGA: the CLBs, the DSPs, the clock managers, the IOBs and all other configurable resources. SK-RAFT can inject faults into all of the CRAM.
- **Injection into the application RAM (ARAM).** The ARAM contains the data of the design during operation: the contents of the BRAMs, the flip-flops and the LUTRAM.
- **Targeted fault injection.** SK-RAFT can limit the injection to:
  - The essential bits of the design.
  - The resources of a target pblock.
  - The application memories of selected components or memories in your RTL.
- **Essential-bit analysis.** SK-RAFT reads the EBD file and finds the essential bits of the design. It can also find and count the essential bits of the components in a pblock.
- **Full BSCAN support.** Your script can write inputs to the design and read outputs from the design through the BSCAN user registers (USER1 to USER4).
- **External scrubbing through JTAG.** SK-RAFT can scrub the CRAM from outside the FPGA, through JTAG. This function helps during radiation tests.
- **Programmer.** SK-RAFT can program the FPGA with a bitstream.
- **Readback with GCAPTURE.** SK-RAFT can read back the configuration frames of the FPGA. With GCAPTURE, the readback also contains the current values of the flip-flops.

## How SK-RAFT operates

SK-RAFT is a server:

- On one side, the server connects to the AMD-Xilinx FPGA through JTAG (a USB JTAG cable).
- On the other side, the server receives gRPC requests from clients through TCP/IP.

To inject a fault, your script sends a gRPC request to the server. The server does the operation on the FPGA through JTAG. Then the server sends the result back to your script. The server and your script can be on the same computer (`127.0.0.1`) or on different computers.

```
+---------------+   gRPC requests (TCP/IP)  +----------------+   JTAG (USB)   +------------+
|  Your script  |  -----------------------> |                |  ----------->  |            |
|  + skraft     |                           | SK-RAFT server |                | FPGA board |
|    client     |  <----------------------- |                |  <-----------  |            |
+---------------+         results           +----------------+                +------------+
```

The `skraft` Python client in this repository sends the gRPC requests for you. A typical script does these steps:

1. Connect to the server: `SkraftFpga.connect(ip, port)`.
2. Reserve the board with its serial number: `client.attach(serial_number)`. To find the serial numbers of the connected boards, use `client.get_devices()`.
3. Upload the design files (bitstream, EBD, LL and XDC files) to the server: `dev.uploadDesignToServer(design)`.
4. Program the FPGA: `dev.programFPGA()`.
5. Inject faults, for example: `dev.inject_random(TargetMemory.ESSENTIAL_CRAM)`.
6. Read the effect of the faults, for example through BSCAN: `dev.read_bscan(...)`.

Example:

```python
from skraft import Design, SkraftFpga, TargetMemory

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BFD452A") as dev:
        dev.uploadDesignToServer(Design(bit="top.bit", ebd="top.ebd"))
        dev.programFPGA()
        report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
        print(f"far {report.far:#010x} word {report.word_index} bit {report.bit_index}")
```

## How SK-RAFT models a device

![The application plane is on top of the configuration plane. A fault can go through the two planes at the same point. SK-RAFT can inject a fault directly into each plane.](docs/images/plane-diagram.svg)

SK-RAFT sees two physical layers ("planes") on the device:

- The **configuration plane** is the configuration RAM (CRAM), that is, the bitstream. It contains the LUT truth tables, the routing and the BRAM mode.
- The **application plane** is the application RAM (ARAM): the state of the design during operation. It contains the flip-flop values and the BRAM content.

SK-RAFT can inject faults directly into the two planes. For the full model, refer to [`docs/concepts.md`](docs/concepts.md). It explains essential bits, LUTRAM, pblocks and the location of a fault.

## Layout

```
sk-raft-deliverables/
├── api/python/                           Python client (skraft package)
├── docs/                                 Concepts and reference documents
└── examples/                             Example designs and scripts (refer to examples/README.md)
    ├── example1/ .. example4/              Python API examples (src/main.py)
    └── hw/                                 Vivado project (create_project.tcl)
        ├── sources_1/new/                   VHDL sources
        └── xdc/                             basys3/, zedboard/, custom_template/
```

## Installation

The `skraft` Python client is not on PyPI. Install it from this repository into the virtual environment of your project:

```bash
cd your-project
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install /path/to/api/python
```

To use local changes to the client without a new installation, use `pip install -e /path/to/api/python`.

## Report a problem

To report a bug in the client, the examples or the documents, open an issue in the Issues tab of this repository. Use the "Bug report" template. For more information, refer to [`CONTRIBUTING.md`](CONTRIBUTING.md).

SolidKosmos does not accept pull requests from persons outside SolidKosmos.

## Licence

- The Python client (`api/python`), the examples (`examples/`) and the documents (`docs/`) are open source under the Apache License 2.0. Refer to [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
- The SK-RAFT server is not open source. The SK-RAFT Trial Licence Agreement or the SK-RAFT End User Licence Agreement applies to the server.
- SK-RAFT and SolidKosmos are trademarks of SOLIDKOSMOS S.A. The Apache License 2.0 does not give permission to use these trademarks.
