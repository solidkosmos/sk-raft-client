## SolidKosmos S.A.

# SK-RAFT

This is a repository of example designs and scripts utilizing SK-RAFT, SolidKosmos's EDA tool for emulating and analysing single-event effects (SEEs) on COTS FPGAs and SoCs.

## Layout

```
examples/
├── get_started_examples_package/         Vivado + Python getting-started suite
│   ├── example1/ .. example4/             Python API walkthroughs (src/main.py)
│   └── hw/getting_started_examples_hw/    Vivado project (create_project.tcl)
│       ├── sources_1/new/                  VHDL sources
│       └── xdc/                            basys3/, zedboard/, custom_template/
└── test_neo_hardened/                     NEORV32 SoC hardened with SECDED/parity/ECC
    ├── README.md                           (DMEM, regfile, CPU control FSM, PC) plus a
    ├── LICENSE                             JTAG fault-injection test harness, targeting
    ├── THIRD_PARTY_NOTICES.md              a Digilent Basys-3 (Xilinx Artix-7)
    ├── create_project.tcl                  Vivado project generator (source of truth)
    ├── neorv_fi_example/                   Python fault-injection campaign (BSCAN-driven,
    │                                        golden-run comparison, AVF measurement)
    ├── sw/hardening_coremark/               Firmware: hardening handlers + CoreMark
    └── test_neo.srcs/                       Tracked HDL sources/constraints only
        ├── sources_1/imports/rtl/            Vendored NEORV32 core + top-level test setup
        ├── sources_1/imports/new/            SolidKosmos JTAG/BSCAN bridge, step controller
        ├── sources_1/imports/UTILITIES/       Parity/SECDED building blocks
        ├── sources_1/new/                    secded_enc8b.vhd / secded_dec8b.vhd (DMEM codec)
        └── constrs_1/imports/                Basys-3 pin/timing constraints (.xdc)
```

New examples should be added under a new top-level folder (mirroring `get_started_examples_package/` and `test_neo_hardened/`, or `api/` at the repo root) with its own `README.md` when non-trivial.
