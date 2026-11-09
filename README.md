<img alt="SK-RAFT by SolidKosmos" src="docs/images/sk-raft-logo-light-bg.svg">

SK-RAFT is an EDA software tool for fault injection in AMD-Xilinx FPGAs. It emulates single-event upsets (SEUs).

This repository contains open-source getting-started examples for the SK-RAFT server. The SK-RAFT server is proprietary SolidKosmos software and requires a valid trial or commercial licence.

**Get a trial licence:** contact us at [info@solidkosmos.gr](mailto:info@solidkosmos.gr) or [www.solidkosmos.gr](https://solidkosmos.gr).

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

## Quick start

1. Install the SK-RAFT server with its licence. Connect the FPGA board to the server computer through its USB JTAG cable.
2. Start the server. On Windows, run the launcher in the `bin` folder of the server installation:

   ```bat
   bin\sk-raft.bat
   ```

   On Linux, run the server executable of the installation. It takes the same options as on Windows.

   The server is ready when it prints:

   ```
    ================================================================
    SK-RAFT - Reliability Assessment Fault-emulation Toolkit
    Server 1.x.x (build ef71872, 2026-11-06T13:03:58Z)
    Copyright (c) 2026 SolidKosmos. All rights reserved.
    Use is subject to the SK-RAFT End User License Agreement.
    ----------------------------------------------------------------
    SK-RAFT licence: FULL (Dinkey dongle XXXXXXXXXX)
      Features: application memory injections, pblock injections
    ----------------------------------------------------------------
    Host       windows/amd64, go1.27.3, PID XXXXX
    Log file   C:\path\to\skraft.log
    Designs    C:\path\to\designs
    Listening  [::]:50051, TLS false, client key false
    ================================================================
   ```

   Keep the server running while you use it. The server serves one client at a time. Another client that connects in the meantime gets the error `the server serves only one client and another client is connected`.

   | Option | Description |
   | --- | --- |
   | `-port <number>` | The TCP port of the server. The default is `50051`. |
   | `-tls-cert <file>`, `-tls-key <file>` | The TLS certificate and private key (PEM) of the server. With them, the server accepts only TLS connections. |
   | `-tls-public-key <file>` | The public key (or certificate) of the clients that the server accepts. Refer to [`application_examples/tls_program`](application_examples/tls_program/README.md). |

   `bin\sk-raft.bat -v` prints the version of the server. On Windows, the launcher runs the server in `%LOCALAPPDATA%\SolidKosmos\sk-raft`. The server writes its log, `skraft.log`, and its cache there.
3. Install the `skraft` Python client. Refer to [Installation](#installation).
4. Find the serial number of your board:

   ```bash
   python get_started/list_devices.py
   ```

   The script prints the serial number and the part number of each board that is connected to the server. For a server on another computer, set `SK_RAFT_SERVER_IP` at the top of the script to the address of that computer. In your own scripts, `client.get_devices()` gives the same list.
5. Run an example. Start with [`get_started`](get_started/README.md). It has prebuilt design files for the Basys 3 and the ZedBoard. Set `SERIAL_NUMBER` and `BOARD` at the top of the `main.py` of the example.

## Folder structure

```
sk-raft-client/
├── api/python/                           Python client (skraft package) and offline bundle
├── application_examples/                 Example designs and scripts for specific use cases
├── auxiliary_components/                 Reusable BSCAN registers, safe clock, BRAM hold pass
├── docs/                                 Concepts, reference documents and documentation builder
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

### Installation without internet access

See [`./api/python/offline_bundle`](./api/python/offline_bundle)

## Compatibility

The client and the SK-RAFT server have separate versions. The table gives the server versions that the current client supports:

| Client (`skraft`) | Supported SK-RAFT server versions |
| --- | --- |
| 1.0.0 | 1.0.0 |

- The version of the client: `pip show skraft`.
- The version of the server: `bin\sk-raft.bat -v`, or `client.version()` from a script.

The changes of each version are in [`CHANGELOG.md`](CHANGELOG.md).

## Documentation

To read all the documents of this repository, and the API reference of the client, in a web browser, build the documentation:

```bash
docs/html-gen/build_docs.sh      # docs\html-gen\build_docs.bat on Windows
```

The script writes one HTML file, `api/python/dist/skraft-docs-<version>.html`. The file contains all the pages, the images and a search. It needs no other file and no internet. Open it in a web browser, or send it to another person.

On the first run, the script creates a virtual environment in `docs/html-gen/.venv` and installs the packages of `docs/html-gen/requirements-docs.txt`. This needs internet access and Python 3.11 or later.

## Report a problem

To report a bug in the client, the examples or the documents, open an issue in the Issues tab of this repository. Use the "Bug report" template. For more information, refer to [`CONTRIBUTING.md`](CONTRIBUTING.md).

SolidKosmos does not accept pull requests from persons outside SolidKosmos.

## License

- The Python client (`api/python`), the examples (`get_started/` and `application_examples/`), the auxiliary components (`auxiliary_components/`) and the documents (`docs/`) are open source under the Apache License 2.0. Refer to [`LICENSE.md`](LICENSE.md) and [`NOTICE.md`](NOTICE.md).
- Exception: the NEORV32 files in `application_examples/test_neo_hardened` are under the BSD 3-Clause License. Refer to [`NOTICE.md`](NOTICE.md).
- The SK-RAFT server is not open source. The SK-RAFT Trial Licence Agreement or the SK-RAFT End User Licence Agreement applies to the server.
- SK-RAFT and SolidKosmos are trademarks of SOLIDKOSMOS S.A. The Apache License 2.0 does not give permission to use these trademarks.
