# Changelog

The changes of each release of the SK-RAFT client. For the SK-RAFT server versions that the client supports, refer to [Compatibility](README.md#compatibility) in the README.

## 1.0.0 (2026-11-09)

The first release.

### Python client (`api/python`, package `skraft`)

- Connect to the server, with or without TLS, list the boards and attach a board.
- Upload a design and program the FPGA.
- Read back the configuration frames, also with GCAPTURE, and write frames.
- Inject into the CRAM and into the application memory (flip-flops, LUTRAM, BRAM): random, exhaustive or at one location. Limit the injection to the essential bits, to a pblock or to RTL components.
- Count the bits of each memory, and list the frame addresses, the pblocks and the components of a design.
- Write and read the BSCAN user registers USER1 to USER4.
- Run external scrubbing sessions and fault-injection campaigns.
- Read and write the configuration registers.
- Read the XADC and System Monitor sensors, and set their alarms.
- Set the JTAG clock (TCK) frequency and the FTDI latency: `configure_jtag_frequency` and `configure_latency`.
- Typed exceptions, all derived from `SkraftError`.

### Protocol

- `api/skraft_client.proto`: the gRPC service of the server, for clients in other languages.

### Examples and components

- `get_started/`: examples 1 to 5, with prebuilt designs for the Basys 3 and the ZedBoard.
- `application_examples/`: MMCM DRP interface, readback scrubbing, SEM arbitration, hardened NEORV32 SoC, TLS, XADC alarm and XADC monitor.
- `auxiliary_components/`: BSCAN user registers, safe-startup clock and BRAM hold pass.

### Documents and tools

- `docs/`: concepts, general guidelines and cheat sheet.
- `docs/html-gen`: builds all the documents and the API reference into one HTML file.
- `api/python/offline_bundle`: an installation bundle for computers without internet access.
