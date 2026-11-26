<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/sk-raft-logo-dark-bg.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/sk-raft-logo-light-bg.svg">
  <img alt="SK-RAFT by SolidKosmos" src="docs/images/sk-raft-logo-light-bg.svg">
</picture>

# SK-RAFT: FPGA fault injection for AMD-Xilinx devices

[![Latest release](https://img.shields.io/github/v/release/solidkosmos/sk-raft-client?label=release)](https://github.com/solidkosmos/sk-raft-client/releases/latest)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE.md)
[![Documentation](https://img.shields.io/badge/docs-solidkosmos.github.io-informational)](https://solidkosmos.github.io/)

SK-RAFT is an EDA software tool for fault injection in AMD-Xilinx FPGAs. It emulates single-event upsets (SEUs).

![SK-RAFT runs fault injection trials on a Basys 3. In each trial, it flips one essential bit of a simplex adder and one essential bit of a TMR adder. The simplex adder gives wrong results in approximately 45% of the trials. The TMR adder gives wrong results in approximately 2.6% of the trials.](docs/images/sk-raft-demo.gif)

The demo uses [example 2](get_started/example2/README.md). In each trial, SK-RAFT injects one fault into a random essential bit of a simplex adder and one fault into a random essential bit of a TMR adder. Then the script examines the results of the two adders. The vulnerability factor (VF) of an adder is the number of trials with wrong results, divided by the number of trials.

This repository contains open-source getting-started examples for the SK-RAFT server. The SK-RAFT server is proprietary SolidKosmos software and requires a valid trial or commercial licence.

**Request Free Trial:**  [https://solidkosmos.gr/#try](https://solidkosmos.gr/#try).

## Main functions

- **Injection into the configuration RAM (CRAM).** The CRAM contains the FPGA configuration: CLBs, DSPs, clock managers, IOBs, and all other configurable resources. SK-RAFT can inject faults into all of the CRAM. 
- **Injection into the application RAM (ARAM).** The ARAM contains the design data during operation: the contents of the BRAMs, the flip-flops, and the LUTRAM. 
- **Targeted fault injection.** SK-RAFT can limit the injection to:
  - The essential bits of the design.
  - The essential bits of a specific Pblock.
  - The application memories of selected components in your RTL hierarchy.
- **Essential-bit analysis.** SK-RAFT reads the Vivado-generated EBD file and finds the essential bits of the design or specific Pblocks.
- **Full BSCAN support.** Your script can write inputs to the design and read outputs from the design through the BSCAN user registers (USER1 to USER4). A register can have any number of bits. It does not have to be a whole number of bytes.
- **Readback scrubbing through JTAG.** Your script can scrub the CRAM from outside the FPGA: it reads back the frames and writes the frames that changed back, through JTAG (refer to [`readback_scrubbing`](application_examples/readback_scrubbing/README.md)). This function helps during radiation tests.
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
3. Upload the design files (bitstream, EBD, LL and XDC files) to the server: `dev.upload_design_to_server(design)`.
4. Program the FPGA with an uploaded design: `dev.program_fpga(design)`. The server keeps each uploaded design. Thus, you can upload several designs, and then program the one to use.
5. Inject faults, for example: `dev.inject_random(TargetMemory.ESSENTIAL_CRAM)`.
6. Read the effect of the faults, for example through BSCAN: `dev.read_bscan(...)`.

Example:

```python
from skraft import Design, SkraftFpga, TargetMemory

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BFD452A") as dev:
        design = Design(bit="top.bit", ebd="top.ebd")
        dev.upload_design_to_server(design)
        dev.program_fpga(design)
        report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
        print(f"far {report.far:#010x} word {report.word_index} bit {report.bit_index}")
```

Before you inject into the application memory (flip-flops, LUTRAM, BRAM), read the setup rules in [`docs/general_guidelines.md`](docs/general_guidelines.md). For the concepts, refer to [`docs/concepts.md`](docs/concepts.md). For code snippets of the common routines, refer to [`docs/cheatsheet.md`](docs/cheatsheet.md).

## Quick start

1. Install the SK-RAFT server and activate its licence. Connect the licence dongle, if you use one, and the FPGA board (its USB JTAG cable) to the server computer. Close the Vivado Hardware Manager (`hw_server`): only one program can use a JTAG cable at a time.
2. Start the server: type `sk-raft` in a terminal, on Windows or on Linux. If the server does not see the board, refer to the troubleshooting chapter of the SK-RAFT Server User Manual.

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

   `sk-raft -v` prints the version of the server. The server writes its log, `skraft.log`, and its cache in `%LOCALAPPDATA%\SolidKosmos\sk-raft` on Windows and in `~/.local/share/SolidKosmos/sk-raft` on Linux.
3. Open a terminal with the `skraft` Python client. The SK-RAFT setup installs the client in a virtual environment of your examples folder. On Windows, double-click `get_started\open_terminal.bat`. On Linux, run `sh get_started/open_terminal.sh`. Run the commands of the next steps in the terminal that opens. If you cloned this repository from GitHub, install the client first: refer to [Installation](#installation).
4. Make sure that the server finds your board:

   ```bash
   python get_started/list_devices.py
   ```

   The script prints the serial number and the part number of each board that is connected to the server. For a server on another computer, set `SK_RAFT_SERVER_IP` at the top of the script to the address of that computer. In your own scripts, `client.get_devices()` gives the same list.
5. Run an example. Start with [`get_started`](get_started/README.md). It has prebuilt design files for the Basys 3 and the ZedBoard. Set `BOARD` at the top of the `main.py` of the example. The examples attach to the first board that the server lists, so connect only the target board to the server.

## Folder structure

```
sk-raft-client/
├── api/python/                           Python client (skraft package) and offline bundle
├── application_examples/                 Example designs and scripts for specific use cases
├── auxiliary_components/                 Reusable BSCAN registers, safe clock, BRAM hold pass
├── docs/                                 Concepts, guidelines and cheat sheet
└── get_started/                          Example designs and scripts, client install scripts
```

## Installation

The `skraft` Python client is not on PyPI. The SK-RAFT setup installs it: your examples folder has a virtual environment, `.venv`, with the client from `api/python` in it.

### Open a terminal with the client

On Windows, double-click `get_started\open_terminal.bat`. It opens a Command Prompt in the root folder of the examples, with `.venv` active.

On Linux, in the root folder of the examples:

```bash
sh get_started/open_terminal.sh
```

The script opens a shell with `.venv` active. Type `exit` to leave it.

### Install the client in a clone from GitHub

A clone of this repository from GitHub has no `.venv`. Install the client one time with the scripts in `get_started`. They make `.venv` in the root folder of the repository and install the client from `api/python` into it. They need Python 3.9 or a later version and internet access.

- On Windows, double-click `get_started\install_client.bat`.
- On Linux, in the root folder of the repository, run `sh get_started/install_client.sh`. On Ubuntu and Debian, the script needs the `python3-venv` package (`sudo apt install python3-venv`).

Then open a terminal with the client, as above. If `.venv` does not exist, `open_terminal` installs the client first.

The examples in `get_started` and `application_examples` run in this terminal. Some application examples need more packages, for example `pyserial`. Their README gives the `pip install` command.

### Install with commands

The SK-RAFT installation comes with a virtual environment that has the client installed. You need the commands below only to make a new virtual environment with the client, for example for your own project. Use the commands of your shell.

Linux:

```bash
cd your-project
python3 -m venv .venv
source .venv/bin/activate
pip install /path/to/api/python
```

Windows, Command Prompt:

```bat
cd your-project
python -m venv .venv
.venv\Scripts\activate.bat
pip install C:\path\to\api\python
```

Windows, PowerShell:

```powershell
cd your-project
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install C:\path\to\api\python
```

If PowerShell stops at `Activate.ps1` with the error "running scripts is disabled on this system", the execution policy of Windows blocks PowerShell scripts. Run this command one time in PowerShell, then activate again. It changes the policy only for your Windows user, and it does not need administrator rights:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

If a group policy of your organization sets the execution policy, you cannot change it. Then use Command Prompt, or use the Python of the virtual environment without activation: `.venv\Scripts\python -m pip install C:\path\to\api\python`, then `.venv\Scripts\python main.py`.

To use local changes to the client without a new installation, use `pip install -e /path/to/api/python`.

### Installation without internet access

See [`./api/python/offline_bundle`](./api/python/offline_bundle)

## Compatibility

The client and the SK-RAFT server have separate versions, in the form MAJOR.MINOR.PATCH. A server works with each client of the same major version that is not newer than the server. For example, server 1.4.2 works with clients 1.0.0 to 1.4.2. It does not work with client 1.5.0 or with client 2.0.0.

- The version of the client: `pip show skraft`.
- The version of the server: `sk-raft -v`, or `client.version()` from a script.

When the client connects, it prints its version and the version of the server. It prints a warning when their major or minor versions (X.Y of X.Y.Z) differ.

The changes of each version are in [`CHANGELOG.md`](CHANGELOG.md).

## Documentation

To read all the documents on one website, go to [solidkosmos.github.io](https://solidkosmos.github.io/).

The documents are also Markdown files in this repository:

- [`docs/concepts.md`](docs/concepts.md): the concepts of SK-RAFT.
- [`docs/general_guidelines.md`](docs/general_guidelines.md): the setup rules for injection into the application memory.
- [`docs/cheatsheet.md`](docs/cheatsheet.md): code snippets of the common routines.
- The README of each folder in `get_started` and `application_examples`.

## Report a problem

To report a bug in the client, the examples or the documents, open an issue in the Issues tab of this repository. Use the "Bug report" template. For more information, refer to [`CONTRIBUTING.md`](CONTRIBUTING.md).

SolidKosmos does not accept pull requests from persons outside SolidKosmos.

## License

- The Python client (`api/python`), the examples (`get_started/` and `application_examples/`), the auxiliary components (`auxiliary_components/`) and the documents (`docs/`) are open source under the Apache License 2.0. Refer to [`LICENSE.md`](LICENSE.md) and [`NOTICE.md`](NOTICE.md).
- Exception: the NEORV32 files in `application_examples/test_neo_hardened` are under the BSD 3-Clause License. Refer to [`NOTICE.md`](NOTICE.md).
- The SK-RAFT server is not open source. The SK-RAFT Trial Licence Agreement or the SK-RAFT End User Licence Agreement applies to the server.
- SK-RAFT and SolidKosmos are trademarks of SOLIDKOSMOS S.A. The Apache License 2.0 does not give permission to use these trademarks.
