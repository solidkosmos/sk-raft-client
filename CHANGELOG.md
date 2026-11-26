# Changelog

The changes of each release of the SK-RAFT client. For the SK-RAFT server versions that the client supports, refer to [Compatibility](README.md#compatibility) in the README.

## 1.0.1 (2026-11-26)

### Python client (`api/python`, package `skraft`)

- The package has the metadata for PyPI (description, README, license, links), and the minimum versions of its dependencies: grpcio 1.76.0 and protobuf 6.31.1. The generated gRPC code needs these versions.
- `SkraftFpga.connect()` prints the versions of the client and of the server. It prints a warning only when their major or minor versions (X.Y of X.Y.Z) differ. Before, it printed a warning for each server version other than the version of the client.
- When the block of `with client.attach(...) as dev:` raises an error and the release of the device also fails, for example because the server stopped, the client reports the error of the block. Before, the error of the release replaced it.
- Removed `FpgaDevice.scrub` and its types `ScrubbingType`, `FpgaScrubReport`, `FpgaScrubSummary` and `FpgaScrubWordSummary`. To scrub the CRAM, read back the frames and write the frames that changed back from your script, as [`readback_scrubbing`](application_examples/readback_scrubbing/README.md) does.

### Examples

- Example 1: the design `targeted_top` has two 16-bit shift registers with a feedback loop, each in its own pblock (`pblock_sr_0`, `pblock_sr_1`), with their even parities on LD0 and LD1. Before, it had two heartbeat counters. The prebuilt designs for the Basys 3 and the ZedBoard are new. Step 1 stops after 200 upsets, or earlier when you press Enter, and each step is a function of `main.py`.
- Example 4: the script injects only into the BRAM content (block type 1). The README tells why the configuration frames (block type 0) also affect the BRAM. The BRAM of `brams_top` is now `soft_sec_bram` (pblock `pblock_soft_sec_bram`), and the prebuilt designs are new.
- Example 6: the readback and writeback part of example 4 (`example4/readback_writeback`) is now example 6. It explains why a BRAM needs a hold register: the BRAM shares its write and read paths with the configuration layer, so an SK-RAFT access changes the BRAM output, and the built-in ECC encoder makes new parity bits for an injected bit.

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
