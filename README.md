<img alt="SK-RAFT by SolidKosmos" src="docs/images/sk-raft-logo-light-bg.svg">

**Getting-started examples for SK-RAFT.** 

SK-RAFT is an EDA software tool for fault injection in AMD-Xilinx FPGAs. It emulates single-event upsets (SEUs).

This repository contains open-source getting-started examples for the SK-RAFT server. The SK-RAFT server is proprietary SolidKosmos software and requires a valid trial or commercial licence.

**Get a trial licence:** `<trial link: TBD>`

## Main functions

- **Injection into the configuration RAM (CRAM).** The CRAM contains the FPGA configuration: CLBs, DSPs, clock managers, IOBs, and all other configurable resources. SK-RAFT can inject faults into all of the CRAM. 
- **Injection into the application RAM (ARAM).** The ARAM contains the design data during operation: the contents of the BRAMs, the flip-flops, and the LUTRAM. 
- **Targeted fault injection.** SK-RAFT can limit the injection to:
  - The essential bits of the design.
  - The essential bits of a specific Pblock.
  - The application memories of selected components in your RTL hierarchy.
- **Essential-bit analysis.** SK-RAFT reads the Vivado-generated EBD file and finds the essential bits of the design or specific Pblocks.
- **Full BSCAN support.** Your script can write inputs to the design and read outputs from the design through the BSCAN user registers (USER1 to USER4).
- **External scrubbing through JTAG.** SK-RAFT can scrub the CRAM from outside the FPGA, through JTAG. This function helps during radiation tests.
- **Programmer.** SK-RAFT can program the FPGA with a bitstream.
- **XADC and System Monitor access.** SK-RAFT can read the temperature and voltage sensors of the XADC (7 series) and of the System Monitor (UltraScale, UltraScale+) through JTAG. It can also set and clear their alarms.
- **TLS connection.** The client can connect to the SK-RAFT server through TLS, with the certificates of the server and of the client.
- **Readback with GCAPTURE.** SK-RAFT can read back the FPGA's configuration frames. With GCAPTURE, the readback also contains the current values of the flip-flops.

## How SK-RAFT operates

SK-RAFT is a server:

- On one side, the server connects to the AMD-Xilinx FPGA through FTDI JTAG (a USB JTAG cable).
- On the other side, the server receives gRPC requests from clients through TCP/IP.

To inject a fault, your script sends a gRPC request to the server. The server does the operation on the FPGA through JTAG. Then the server sends the result back to your script. The server and your script can be on the same computer (`127.0.0.1`) or on different computers.

![Architecture of SK-RAFT. Your script and the skraft client send gRPC requests over TCP/IP to the SK-RAFT server. The server returns the results. The server connects over JTAG (USB) to the FPGA board, which has configuration memory, application memory, and a BSCAN interface to the user design.](docs/images/sk-raft-architecture.svg)

The `skraft` Python client in this repository sends the gRPC requests for you. A typical script does these steps:

1. Connect to the server: `SkraftFpga.connect(ip, port)`.
2. Reserve the board with its serial number: `client.attach(serial_number)`. To find the serial numbers of the connected boards, use `client.get_devices()`.
3. Upload the design files (bitstream, EBD, LL and XDC files) to the server: `dev.uploadDesignToServer(design)`.
4. Program the FPGA with an uploaded design: `dev.programFPGA(design)`. The server keeps each uploaded design. Thus, you can upload several designs, and then program the one to use.
5. Inject faults, for example: `dev.inject_random(TargetMemory.ESSENTIAL_CRAM)`.
6. Read the effect of the faults, for example through BSCAN: `dev.read_bscan(...)`.

Example:

```python
from skraft import Design, SkraftFpga, TargetMemory

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BFD452A") as dev:
        design = Design(bit="top.bit", ebd="top.ebd")
        dev.uploadDesignToServer(design)
        dev.programFPGA(design)
        report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
        print(f"far {report.far:#010x} word {report.word_index} bit {report.bit_index}")
```

Before you inject into the application memory (flip-flops, LUTRAM, BRAM), read the setup rules in [`docs/general_guidelines.md`](docs/general_guidelines.md). For the concepts, refer to [`docs/concepts.md`](docs/concepts.md). For code snippets of the common routines, refer to [`docs/cheatsheet.md`](docs/cheatsheet.md).

## Folder structure

```
sk-raft-client/
├── api/python/                           Python client (skraft package)
├── application_examples/                 Example designs and scripts for specific use cases
├── auxiliary_components/                 Reusable BSCAN registers, safe clock, BRAM hold pass
├── docs/                                 Concepts and reference documents
└── get_started/                          Example designs and scripts
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

## License

- The Python client (`api/python`), the examples (`get_started/` and `application_examples/`), the auxiliary components (`auxiliary_components/`) and the documents (`docs/`) are open source under the Apache License 2.0. Refer to [`LICENSE.md`](LICENSE.md) and [`NOTICE.md`](NOTICE.md).
- Exception: the NEORV32 files in `application_examples/test_neo_hardened` are under the BSD 3-Clause License. Refer to [`NOTICE.md`](NOTICE.md).
- The SK-RAFT server is not open source. The SK-RAFT Trial Licence Agreement or the SK-RAFT End User Licence Agreement applies to the server.
- SK-RAFT and SolidKosmos are trademarks of SOLIDKOSMOS S.A. The Apache License 2.0 does not give permission to use these trademarks.
