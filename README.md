## SolidKosmos S.A.

# SK-RAFT

SK-RAFT is an advanced EDA tool by SolidKosmos for emulating and analysing single-event effects (SEEs) on commercial off-the-shelf (COTS) FPGAs and SoCs, enabling fault injection, recovery validation, and radiation-tolerance assessment. This repository holds the examples testing and utilizing SK-RAFT, along with the python client API to communicate with the SK-RAFT gRPC server. 

## Layout

```
sk-raft-deliverables/
├── api/                                  Client libraries
│   ├── node/                              TypeScript/Node client
│   └── python/                            Python client (skraft package)
├── global/
│   └── proto/                            Shared gRPC/protobuf definitions
└── examples/                             Example designs and scripts (see their own README)
    ├── get_started_examples_package/      Vivado + Python getting-started suite
    │   ├── example1/ .. example4/          Python API walkthroughs (src/main.py)
    │   └── hw/getting_started_examples_hw/ Vivado project (create_project.tcl)
    │       ├── sources_1/new/               VHDL sources
    │       └── xdc/                         basys3/, zedboard/, custom_template/
    └── test_neo_hardened/                 NEORV32 SoC hardening + JTAG FI harness
        ├── neorv_fi_example/                Python fault-injection campaign
        ├── sw/hardening_coremark/           Firmware
        └── test_neo.srcs/                   Tracked HDL sources/constraints
```
