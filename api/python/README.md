# skraft

The Python client of SK-RAFT, the FPGA fault-injection toolkit of SolidKosmos for AMD FPGAs. The client connects to the SK-RAFT server over gRPC. With it, a Python script can:

- reserve an FPGA board and program it with a bitstream;
- inject faults into the configuration memory (CRAM), into its essential bits, into one pblock, or into the application memory (flip-flops, LUTRAM, BRAM);
- read back and write configuration frames;
- write inputs to the design and read outputs from it through the BSCAN user registers;
- read the XADC and System Monitor sensors.

The SK-RAFT server is proprietary SolidKosmos software and needs a trial or commercial licence. To request a free trial, go to [solidkosmos.gr/#try](https://solidkosmos.gr/#try).

## Install

```bash
pip install skraft
```

The client needs Python 3.9 or a later version.

## Example

Inject one upset into a random essential bit of the design, then flip the bit back:

```python
import time

from skraft import Design, SkraftFpga, TargetMemory

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    serial_number = client.get_devices()[0].serial_number
    with client.attach(serial_number) as dev:
        design = Design(bit="top.bit", ebd="top.ebd")
        dev.upload_design_to_server(design)
        dev.program_fpga(design)

        report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
        print(f"far {report.far:#010x} word {report.word_index} bit {report.bit_index}")
        time.sleep(0.1)
        dev.inject_at(report.far, report.word_index, report.bit_index,
                      TargetMemory.CRAM)
```

## Versions

The client and the SK-RAFT server have separate versions, in the form MAJOR.MINOR.PATCH. A server works with each client of the same MAJOR version whose MAJOR.MINOR is not newer than the MAJOR.MINOR of the server. The PATCH numbers do not matter. For example, server 1.4.2 works with clients 1.0.x to 1.4.x. It does not work with client 1.5.0 or with client 2.0.0. When the client connects, it prints its version and the version of the server, and a warning when their major or minor versions differ.

## Documentation

- The documentation: concepts, guidelines, examples, cheat sheet and the API reference: [solidkosmos.github.io](https://solidkosmos.github.io).
- The examples and the source code: [github.com/solidkosmos/sk-raft-client](https://github.com/solidkosmos/sk-raft-client).
- The changes of each version: [CHANGELOG.md](https://github.com/solidkosmos/sk-raft-client/blob/main/CHANGELOG.md).

## License

Apache License 2.0.
