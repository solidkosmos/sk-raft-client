# sk-raft
SK-RAFT is an advanced EDA tool by SolidKosmos for emulating and analysing single-event effects (SEEs) on commercial off-the-shelf (COTS) FPGAs and SoCs, enabling fault injection, recovery validation, and radiation-tolerance assessment.


sk-raft/
├── README.md
├── api/
│   ├── c/
│   │   ├── include/        # SK-RAFT C headers
│   │   ├── src/            # C wrapper / client
│   │   └── README.md
│   ├── go/
│   │   ├── src/            # Go client
│   │   ├── go.mod
│   │   └── README.md
│   ├── node/
│   │   ├── src/            # Node/TypeScript client
│   │   ├── package.json
│   │   └── README.md
│   └── python/
│       ├── src/            # Python package
│       ├── requirements.txt
│       └── README.md
├── examples/
│   ├── fault-injection/
│   │   └── flip-flops/
│   │       ├── README.md
│   │       ├── hw/
│   │       │   ├── create_project.tcl
│   │       │   ├── src/            # HDL / BD Tcl, etc.
│   │       │   └── constraints.xdc
│   │       └── sw/
│   │           ├── python/
│   │           │   ├── run_campaign.py
│   │           │   └── requirements.txt
│   │           ├── go/
│   │           │   └── main.go
│   │           ├── c/
│   │           │   └── main.c
│   │           └── node/
│   │               └── index.js
│   ├── program/
│   ├── readback/
│   └── scrubbing/
├── install/
│   ├── linux/
│   │   ├── arm/
│   │   │   └── scripts/
│   │   └── x86/
│   │       └── scripts/install.sh
│   ├── mac/
│   │   └── scripts/
│   └── windows/
│       └── installer/
└── docs/
    ├── index.md
    ├── getting-started/
    │   └── overview.md
    ├── api/
    │   ├── c.md
    │   ├── go.md
    │   ├── node.md
    │   └── python.md
    └── application-notes/
        ├── overview.md
        └── fault-injection-flip-flops.md

