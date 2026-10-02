## SolidKosmos S.A.

# SK-RAFT

SK-RAFT is SolidKosmos's fault-injection platform for emulating and analysing single-event effects (SEEs) on commercial off-the-shelf (COTS) FPGAs and SoCs: fault injection, recovery validation, and radiation-tolerance assessment.

This repository contains the SK-RAFT client API and example designs/scripts. It does not include the SK-RAFT server.

The get-started examples (`examples/`) demonstrate SK-RAFT's core capabilities, each against a small purpose-built design: whole-device, essential-bit, and pblock-confined CRAM targeting; BSCAN-driven register access; flip-flop and LUTRAM injection; and BRAM content injection with ECC recovery.

## How SK-RAFT models a device

![Where a fault lands: the application plane and configuration plane are two physically stacked layers; a fault can strike through both at the same point, and SK-RAFT can inject into either plane directly](docs/images/plane-diagram.svg)

SK-RAFT addresses two physically stacked planes on the device: the **configuration plane** (CRAM — the bitstream itself: LUT truth tables, routing, BRAM mode) and the **application plane** (the live runtime state: flip-flop values, BRAM content). Both are direct injection targets. See [`docs/concepts.md`](docs/concepts.md) for the full model: essential bits, LUTRAM, pblocks, and how a fault is located.

**Try SK-RAFT:** `<trial link — TBD>`

## Layout

```
sk-raft-deliverables/
├── api/python/                           Python client (skraft package)
├── docs/                                 Concepts and reference docs
└── examples/                             Example designs and scripts (see examples/README.md)
    ├── example1/ .. example4/              Python API walkthroughs (src/main.py)
    └── hw/                                 Vivado project (create_project.tcl)
        ├── sources_1/new/                   VHDL sources
        └── xdc/                             basys3/, zedboard/, custom_template/
```

## Installation

Install the `skraft` Python client into your project's virtual environment directly from this repository; it is not published to PyPI.

```bash
cd your-project
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install /path/to/api/python
```

Use `pip install -e /path/to/api/python` instead to pick up local changes to the client without reinstalling.
