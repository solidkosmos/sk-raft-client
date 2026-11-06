# SK-RAFT application examples

Examples of SK-RAFT for specific use cases. Each folder has a README with the requirements and the steps to run the example.

| Example | Description |
| --- | --- |
| [`mmcm_drp_interface/`](mmcm_drp_interface/README.md) | Changes the MMCM output clocks over BSCAN through the DRP (Basys 3) |
| [`readback_scrubbing/`](readback_scrubbing/README.md) | A CRAM readback scrubber that runs in the client script |
| [`sem_arbitration/`](sem_arbitration/README.md) | SK-RAFT injects into the CRAM, the SEM IP detects and corrects (Basys 3, TE0841) |
| [`test_neo_hardened/`](test_neo_hardened/README.md) | A NEORV32 RISC-V SoC with SECDED/parity hardening, and its fault-injection campaign |
| [`tls_program/`](tls_program/README.md) | Programs the FPGA through a TLS connection to the SK-RAFT server |
| [`xadc_alarm/`](xadc_alarm/README.md) | Sets off and clears the XADC temperature alarm through JTAG |
| [`xadc_monitor/`](xadc_monitor/README.md) | Reads the XADC temperature and voltage sensors through JTAG |
