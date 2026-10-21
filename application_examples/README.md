# SK-RAFT application examples

Examples of SK-RAFT for specific use cases. Each folder has a README with the requirements and the steps to run the example.

```
application_examples/
├── readback_scrubbing/   A CRAM readback scrubber that runs in the client script
├── sem_arbitration/      SK-RAFT injects into the CRAM, the SEM IP detects and corrects (Basys 3, TE0841)
├── test_neo_hardened/    A NEORV32 RISC-V SoC with SECDED/parity hardening, and its fault-injection campaign
├── tls_program/          Programs the FPGA through a TLS connection to the SK-RAFT server
├── xadc_alarm/           Sets off and clears the XADC temperature alarm through JTAG
└── xadc_monitor/         Reads the XADC temperature and voltage sensors through JTAG
```
