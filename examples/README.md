## SolidKosmos S.A.

# SK-RAFT

This is a repository of example designs and scripts utilizing SK-RAFT, SolidKosmos's EDA tool for emulating and analysing single-event effects (SEEs) on COTS FPGAs and SoCs.

## Layout

```
examples/
└── py/                        Python examples (skraft client)
    ├── example.py              Minimal end-to-end walkthrough: load design,
    │                           program, read bit stats, readback, random
    │                           injection, scrubbing, mixed campaign
    └── neorv_fi_example/       Fault-injection campaign against a NEORV32
        ├── README.md           RISC-V core, comparing UART/CRC output to a
        ├── run_injection.py    golden run to measure AVF
        └── bscan_helpers.py    BSCAN/JTAG helpers (reset, step, CRC read-back)
```

## Contents

- **`py/example.py`** — smallest possible tour of the API: connect, attach a device, push design files, program, pull CRAM/flip-flop bit stats, do a full readback, inject a random fault, run scrubbing, and (commented) launch a mixed fault-injection campaign.
- **`py/neorv_fi_example/`** — a fuller campaign example targeting a NEORV32 core, including design loading, frame exclusion, BSCAN-based DUT control, fault injection/reversal, and golden-run comparison. See its own `README.md` for details and run instructions.

New examples should be added under `py/` (or a new language folder, mirroring `api/`) with their own subfolder and `README.md` when non-trivial.
