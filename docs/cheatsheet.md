# SK-RAFT cheat sheet

Short code snippets for the routines that you use most with the `skraft` Python client. For the rules of the injection setup, refer to [`general_guidelines.md`](general_guidelines.md). For each method and its parameters, refer to the [Python API reference](../api/python/python_api_reference.md).

All snippets after the first one use `dev`, the device that `client.attach()` gives.

## Connect and reserve a device

```python
from skraft import SkraftFpga, SkraftError

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    print(client.version())                      # server version
    for d in client.get_devices():               # connected boards
        print(d.serial_number, d.part_number)

    with client.attach("210183BFD452A") as dev:  # reserve one board
        dev.configure_seed(42)                   # repeatable random injections (set after attach)
        ...
```

With TLS (the server runs with `-tls-cert` and `-tls-key`):

```python
client = SkraftFpga.connect(ip="10.0.0.5", port=50051,
                            tls_server_cert="server.crt",          # verify the server
                            tls_cert="client.crt", tls_key="client.key")  # only if the server checks the client
```

## Upload and program a design

```python
from skraft import Design

design = Design(bit="top.bit", ebd="top.ebd", ll="top.ll", xdc="top.xdc")
dev.uploadDesignToServer(design)   # the server keeps each uploaded design
dev.programFPGA(design)            # program again at any time to clear all upsets
```

| Target | Files that the design must have |
| --- | --- |
| `TargetMemory.CRAM` | `bit` |
| `TargetMemory.ESSENTIAL_CRAM` | `bit`, `ebd` |
| `TargetMemory.FF`, `LUTRAM`, `BRAM` | `bit`, `ll` |
| `pblock=` or `exclude_pblock=` | also `xdc` |
| `component=` | also `ll` |

## Count the bits

```python
from skraft import TargetMemory

dev.bit_count(TargetMemory.ESSENTIAL_CRAM)                  # whole design
dev.bit_count(TargetMemory.ESSENTIAL_CRAM, pblock="pb_tmr")  # one pblock
dev.all_bit_counts()                                         # dict with all counts
```

## Inject into the CRAM and correct the upset

```python
import time

report = dev.inject_random(TargetMemory.ESSENTIAL_CRAM)
print(f"far {report.far:#010x} word {report.word_index} bit {report.bit_index}")
time.sleep(0.1)                                              # keep the upset
dev.inject_at(report.far, report.word_index, report.bit_index,
              TargetMemory.CRAM)                             # flip the bit back
```

## Inject into a pblock, or exclude pblocks

```python
dev.inject_random(TargetMemory.ESSENTIAL_CRAM, pblock="pb_tmr")          # only inside pb_tmr
dev.inject_random(TargetMemory.ESSENTIAL_CRAM,
                  exclude_pblock={"harness_pblock"})                    # never inside the test harness
```

The exclusion applies to that call only. To list the pblocks of the XDC file, use `dev.pblocks()`.

## Inject into the flip-flops of a component

```python
for component in dev.components():   # hierarchy from the LL file
    print(component)                 # tree with the flip-flop count of each component

dev.inject_random(TargetMemory.FF, component="top_component/sub_component")
```

`component=` works with `TargetMemory.FF` only. Stop the clock first (next section).

## Inject into the application memory (FF, LUTRAM, BRAM)

Stop the clock of the design through BSCAN, inject, then start the clock again. The design must have the clock gate on USER1 (refer to [`auxiliary_components/bscan`](../auxiliary_components/bscan/README.md#example-clock-gate-on-user1)).

```python
from skraft import BscanPrimitive

USER_CLK_EN = BscanPrimitive(1, 1)   # USER1, 1 bit: 1 = clock runs

def inject_frozen(dev, target, **options):
    dev.write_bscan(USER_CLK_EN, 0)          # stop the clock
    try:
        return dev.inject_random(target, **options)
    finally:
        dev.write_bscan(USER_CLK_EN, 1)      # start the clock, also if the injection fails

report = inject_frozen(dev, TargetMemory.FF, pblock="pb_sr")
report = inject_frozen(dev, TargetMemory.BRAM)
```

To revert the upset, flip the same bit with the clock stopped:

```python
dev.write_bscan(USER_CLK_EN, 0)
dev.inject_at(report.far, report.word_index, report.bit_index, TargetMemory.BRAM)
dev.write_bscan(USER_CLK_EN, 1)
```

A BRAM port without an output register (`DO_REG = 0`) needs the BRAM hold register pass. Refer to [`general_guidelines.md`](general_guidelines.md#3-bram-injection-changes-the-bram-output).

## Inject into one bit from the LL file

```python
def ll_bit(ll_file, name):
    """FAR, word and bit of a BRAM bit, for example name="BIT0" (Ram=B:BIT0)."""
    with open(ll_file, encoding="ascii") as f:
        for line in f:
            fields = line.split()
            if fields[:1] == ["Bit"] and f"Ram=B:{name}" in fields:
                offset = int(fields[3])
                return int(fields[2], 16), offset // 32, offset % 32
    raise ValueError(f"Ram=B:{name} is not in {ll_file}")

far, word, bit = ll_bit("top.ll", "BIT0")
dev.inject_at(far, word, bit, TargetMemory.BRAM)    # with the clock stopped
```

## Inject into every bit

```python
reports, count = dev.inject_exhaustive(TargetMemory.ESSENTIAL_CRAM, pblock="pb_tmr")
```

## Read and write BSCAN registers

```python
from skraft import Bscan

USER_DATA = BscanPrimitive(3, 32)                         # USER3, 32 bits
dev.write_bscan(USER_DATA, 0x1234)
value = int.from_bytes(dev.read_bscan(USER_DATA), "big")  # bytes, MSB first

data = Bscan(dev, 3, 32)                                  # the same register, as integers
data.write(0x1234)
value = data.read()
```

## Read back configuration frames

```python
from skraft import ReadbackOption

frames = dev.readback(ReadbackOption.READBACK)            # all frames
frames = dev.readback(ReadbackOption.READBACK_CAPTURE)    # also the flip-flop values (stop the clock)
frames = dev.readback_range(0x00C00000, 0x00C0007F)       # a range, end included

frame = frames[0]
print(f"{frame.far:#010x}", [w.value for w in frame.words][:4])
print(dev.decode_far(frame.far).minor_address)            # block type, row, column, minor
```

The first and the last frame of a full readback are dummy frames, with the FAR of a real frame. Refer to [`readback_scrubbing`](../application_examples/readback_scrubbing/README.md).

## Write a frame back (correct one frame)

```python
golden = {}
for f in dev.readback(ReadbackOption.READBACK):
    golden.setdefault(f.far, f)  # keep the first frame of each FAR, not the dummy frame
...
dev.write_frame(golden[far])     # restore one frame from the golden copy
```

## Exclude frames from injection

```python
dev.exclude_frames([0x00400F9F, 0x00400FA0])   # the feature operations skip these frames; inject_at does not
```

## Scrubbing and campaigns on the server

```python
from skraft import ScrubbingType, FpgaFiSession, FaultType

report = dev.scrub(ScrubbingType.ESSENTIAL, scrub_cycle=1, duration_ms=10_000)
for cycle in report.scrub_summaries:
    print(cycle.scrub_cycle, len(cycle.word_summaries), "words differed from the golden data")

session = FpgaFiSession(fault_type=FaultType.RANDOM, duration_ms=10_000,
                        correction_time_ms=100, time_between_faults_ms=200,
                        sbu_percent=100.0, mbu_percent=0.0, mcu_percent=0.0,
                        target=TargetMemory.ESSENTIAL_CRAM, correct=True)
summary = dev.run_campaign(session)
print(summary.faults_injected, summary.corrected)
```

The parameter values are only examples. Refer to `scrub` and `run_campaign` in the API reference.

## Read the XADC sensors

```python
from skraft import TEMPERATURE, VCCINT, TEMPERATURE_UPPER

dev.xadc(TEMPERATURE).value        # degC
dev.xadc(VCCINT).value             # V
dev.set_xadc_alarm(TEMPERATURE_UPPER, 85.0)
dev.xadc_flags().temperature       # True while the temperature alarm is on
```

## Read a configuration register

```python
from skraft import RegisterAddress

status = dev.read_register(RegisterAddress.STATUS)
```

## Handle errors and leave a clean device

```python
try:
    ...
except SkraftError as e:          # base class of all client errors
    print(f"failed: {e}")
finally:
    dev.programFPGA(design)       # clear all upsets before other work
```
