## SolidKosmos S.A.

# SK-RAFT

This is a repository of example designs and scripts utilizing SK-RAFT, SolidKosmos's EDA tool for emulating and analysing single-event effects (SEEs) on COTS FPGAs and SoCs.

## Layout

```
examples/
├── py/                          Python examples (skraft client)
│   ├── example.py                Minimal end-to-end walkthrough: load design,
│   │                             program, read bit stats, readback, random
│   │                             injection, scrubbing, mixed campaign
│   └── neorv_fi_example/         Fault-injection campaign against a NEORV32
│       ├── README.md              core, comparing UART/CRC output to a golden
│       ├── run_injection.py       run to measure AVF
│       ├── bscan_helpers.py       BSCAN/JTAG helpers (reset, step, CRC read-back)
│       └── firmware/
│           └── main.c             Hardening-demo firmware run on the DUT during
│                                   the campaign (same as hw/.../hardening_coremark)
└── hw/                          FPGA/HDL design examples
    └── test_neo_hardened/         NEORV32 SoC hardened with SECDED/parity/ECC
        ├── README.md               (DMEM, regfile, CPU control FSM, PC) plus a
        ├── LICENSE                 JTAG fault-injection test harness, targeting
        ├── THIRD_PARTY_NOTICES.md  a Digilent Basys-3 (Xilinx Artix-7)
        ├── create_project.tcl      Vivado 2019.1 project generator (source of
        │                           truth — regenerates the .xpr from scratch)
        ├── sw/hardening_coremark/
        │   └── main.c              Firmware: installs hardening fast-interrupt
        │                           handlers, then runs CoreMark
        └── test_neo.srcs/          Tracked HDL sources only (build products
            ├── sources_1/imports/  such as .cache/.hw/.runs/.xpr are gitignored)
            │   ├── rtl/             Vendored NEORV32 core + top-level test setup
            │   ├── new/             Original SolidKosmos sources: JTAG/BSCAN
            │   │                    bridge, clock-cycle stepping controller
            │   └── UTILITIES/       Parity/SECDED building blocks
            ├── sources_1/new/       secded_enc8b.vhd / secded_dec8b.vhd (DMEM
            │                        byte-lane Hamming codec)
            └── constrs_1/imports/   Basys-3 pin/timing constraints (.xdc)
```

## Contents

- **`py/example.py`** — smallest possible tour of the API: connect, attach a device, push design files, program, pull CRAM/flip-flop bit stats, do a full readback, inject a random fault, run scrubbing, and (commented) launch a mixed fault-injection campaign.
- **`py/neorv_fi_example/`** — a fuller campaign example targeting a NEORV32 core, including design loading, frame exclusion, BSCAN-based DUT control, fault injection/reversal, and golden-run comparison. `firmware/main.c` is the hardening-demo firmware loaded onto the DUT for the run. See its own `README.md` for details and run instructions.
- **`hw/test_neo_hardened/`** — a full Vivado FPGA design example: a NEORV32 RISC-V SoC with SECDED/parity/ECC hardening (gated behind a `HARDEN_EN` generic) and a JTAG-driven fault-injection test harness, targeting a Digilent Basys-3 board. Includes its own `README.md` (design flow, directory layout, hardening details, known limitations), `LICENSE`, `THIRD_PARTY_NOTICES.md` for vendored/modified NEORV32 sources, and `create_project.tcl` to regenerate the Vivado project from source. Only sources, constraints, the project script, and docs are tracked — Vivado-generated project directories are gitignored.

New examples should be added under `py/` or `hw/` (or a new top-level folder, mirroring `api/`) with their own subfolder and `README.md` when non-trivial.
