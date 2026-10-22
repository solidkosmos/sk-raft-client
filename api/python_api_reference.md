<a id="skraft.skraft_fpga"></a>

# skraft.skraft\_fpga

Client for the SK-RAFT server.

Connects to an SK-RAFT server over gRPC, reserves FPGA devices and runs
operations on them, such as programming, readback, fault injection and
scrubbing.

<a id="skraft.skraft_fpga.FpgaDevice"></a>

## FpgaDevice Objects

```python
class FpgaDevice()
```

A device on the SK-RAFT server.

A reserved device is normally obtained from SkraftFpga.attach. The class
can be used as a context manager, in which case the reservation is
released automatically when the block ends.

**Attributes**:

- `serial_number` _str_ - The serial number of the device.
- `part_number` _str_ - The part number of the device. Empty if it is
  not known.
- `design` _Design_ - The design that was last uploaded to the server,
  or programmed.

<a id="skraft.skraft_fpga.FpgaDevice.__init__"></a>

#### \_\_init\_\_

```python
def __init__(stub, serial_number: str, part_number: str = "")
```

Create a handle for a device on the server.

Creating the handle does not reserve the device. Use
SkraftFpga.attach to reserve a device.

**Arguments**:

- `stub` _skraft_client_pb2_grpc.SKRaftFpgaStub_ - The gRPC stub of
  the server connection.
- `serial_number` _str_ - The serial number of the device.
- `part_number` _str_ - The part number of the device. Empty if it
  is not known.

<a id="skraft.skraft_fpga.FpgaDevice.__enter__"></a>

#### \_\_enter\_\_

```python
def __enter__() -> "FpgaDevice"
```

Enter the context manager.

**Returns**:

- `FpgaDevice` - This device.

<a id="skraft.skraft_fpga.FpgaDevice.__exit__"></a>

#### \_\_exit\_\_

```python
def __exit__(*exc_info) -> None
```

Leave the context manager and release the device.

**Arguments**:

- `*exc_info` - Details of any exception raised inside the block.
  They are not used.
  

**Raises**:

- `ConnectionFailedError` - If the server could not release the
  device.

<a id="skraft.skraft_fpga.FpgaDevice.release"></a>

#### release

```python
def release() -> None
```

Release the device and the resources reserved for it on the server.

Uses the FpgaClose RPC.

**Raises**:

- `ConnectionFailedError` - If the server could not release the
  device.

<a id="skraft.skraft_fpga.FpgaDevice.uploadDesignToServer"></a>

#### uploadDesignToServer

```python
def uploadDesignToServer(design: Design) -> None
```

Upload the files of a design to the server.

Each file is sent in its own stream through the FpgaUploadDesignFile
RPC. The server keeps the files of each design in a folder of its
own. Thus, you can upload several designs, and then program one of
them with programFPGA. Once every file has been sent, the design is
also kept on the client so that later calls can check which files
are available.

**Arguments**:

- `design` _Design_ - The design whose files should be uploaded.
  Files that are not set are skipped.
  

**Raises**:

- `DesignFileError` - If a design file cannot be read or its upload
  fails.

<a id="skraft.skraft_fpga.FpgaDevice.design"></a>

#### design

```python
@property
def design() -> Design
```

The design that was last uploaded to the server, or programmed.

**Returns**:

- `Design` - The last uploaded or programmed design, or an empty
  design if nothing has been uploaded yet.

<a id="skraft.skraft_fpga.FpgaDevice.programFPGA"></a>

#### programFPGA

```python
def programFPGA(design: Optional[Design] = None) -> None
```

Program the device with an uploaded design.

Upload the design with uploadDesignToServer first. The server keeps
each uploaded design. Thus, you can upload several designs, and then
program the one to use. The client reads the local files of the
design again, and the server checks that its copies are the same.
After the programming, later calls check the files of this design.
Uses the FpgaProgram RPC.

**Arguments**:

- `design` _Optional[Design]_ - The design to program. If not given,
  the design that was last uploaded or programmed is used.
  

**Raises**:

- `TypeError` - If the design is not a Design.
- `DesignFileError` - If the design has no bitstream, or if a design
  file cannot be read.
- `ConnectionFailedError` - If the server could not program the
  device, for example because the design was not uploaded.
  

**Examples**:

  >>> dev.uploadDesignToServer(design_a)
  >>> dev.uploadDesignToServer(design_b)
  >>> dev.programFPGA(design_a)
  >>> dev.programFPGA(design_b)

<a id="skraft.skraft_fpga.FpgaDevice.readback_range"></a>

#### readback\_range

```python
def readback_range(start_far: int, end_far: int) -> list[FpgaFrame]
```

Read back a range of configuration frames from the device.

Uses the FpgaReadBackRange RPC.

**Arguments**:

- `start_far` _int_ - The frame address where the range starts.
- `end_far` _int_ - The frame address where the range ends. This
  frame is included in the result.
  

**Returns**:

- `list[FpgaFrame]` - The frames that were read back.
  

**Raises**:

- `FrameAddressError` - If the start address comes after the end
  address, or if the server could not read the frames.

<a id="skraft.skraft_fpga.FpgaDevice.shutdown"></a>

#### shutdown

```python
def shutdown()
```

Shut down the device.

Uses the FpgaShutdown RPC.

**Raises**:

- `ConnectionFailedError` - If the server could not shut down the
  device.

<a id="skraft.skraft_fpga.FpgaDevice.startup_sequence"></a>

#### startup\_sequence

```python
def startup_sequence()
```

Run the startup sequence on the device.

Uses the FpgaStartupSequence RPC.

**Raises**:

- `ConnectionFailedError` - If the startup sequence fails.

<a id="skraft.skraft_fpga.FpgaDevice.restore_application_layer"></a>

#### restore\_application\_layer

```python
def restore_application_layer()
```

Restore the application layer of the device.

Uses the FpgaRestoreApplication RPC.

**Raises**:

- `ConnectionFailedError` - If the application layer could not be
  restored.

<a id="skraft.skraft_fpga.FpgaDevice.readback"></a>

#### readback

```python
def readback(option: ReadbackOption) -> list[FpgaFrame]
```

Read back every configuration frame of the device.

Uses the FpgaReadBack RPC.

**Arguments**:

- `option` _ReadbackOption_ - How the readback is done. The capture
  option asks the server to capture the current state of all
  changeable elements of the device before reading it back.
  

**Returns**:

- `list[FpgaFrame]` - All frames that were read back.
  

**Raises**:

- `ConnectionFailedError` - If the server could not read back the
  device.

<a id="skraft.skraft_fpga.FpgaDevice.write_frame"></a>

#### write\_frame

```python
def write_frame(frame: FpgaFrame, restore: bool = False) -> None
```

Write one configuration frame to the device.

The server writes the words of the frame at the frame address of
the frame. The frame must have all the words of a frame of the
device, as a frame from readback has. Uses the FpgaWriteFrame RPC.

**Arguments**:

- `frame` _FpgaFrame_ - The frame to write.
- `restore` _bool_ - If True, the server also restores the
  flip-flops and RAMs of the whole device after the write.
  Keep it False to change only the configuration data.
  

**Raises**:

- `TypeError` - If the frame is not an FpgaFrame.
- `ConnectionFailedError` - If the server could not write the frame,
  for example because the frame address is not on the device
  or the number of words is not correct.
  

**Examples**:

  >>> frames = dev.readback(ReadbackOption.READBACK)
  >>> dev.write_frame(frames[1])

<a id="skraft.skraft_fpga.FpgaDevice.cram_bits"></a>

#### cram\_bits

```python
@property
def cram_bits() -> int
```

The total number of configuration memory (CRAM) bits in the device.

**Returns**:

- `int` - The number of CRAM bits.
  

**Raises**:

- `ConnectionFailedError` - If the server could not count the bits.

<a id="skraft.skraft_fpga.FpgaDevice.essential_cram_bits"></a>

#### essential\_cram\_bits

```python
@property
def essential_cram_bits() -> int
```

The number of essential CRAM bits in the loaded design.

Requires the essential bits (EBD) file.

**Returns**:

- `int` - The number of essential CRAM bits.
  

**Raises**:

- `DesignFileError` - If the essential bits (EBD) file has not
  been uploaded.
- `ConnectionFailedError` - If the server could not count the bits.

<a id="skraft.skraft_fpga.FpgaDevice.ff_bits"></a>

#### ff\_bits

```python
@property
def ff_bits() -> int
```

The number of flip-flop bits used by the loaded design.

Requires the logic location (LL) file.

**Returns**:

- `int` - The number of flip-flop bits.
  

**Raises**:

- `DesignFileError` - If the logic location (LL) file has not
  been uploaded.
- `ConnectionFailedError` - If the server could not count the bits.

<a id="skraft.skraft_fpga.FpgaDevice.bram_bits"></a>

#### bram\_bits

```python
@property
def bram_bits() -> int
```

The number of block RAM (BRAM) bits used by the loaded design.

Requires the logic location (LL) file.

**Returns**:

- `int` - The number of BRAM bits.
  

**Raises**:

- `DesignFileError` - If the logic location (LL) file has not
  been uploaded.
- `ConnectionFailedError` - If the server could not count the bits.

<a id="skraft.skraft_fpga.FpgaDevice.lutram_bits"></a>

#### lutram\_bits

```python
@property
def lutram_bits() -> int
```

The number of LUTRAM bits used by the loaded design.

Requires the logic location (LL) file.

**Returns**:

- `int` - The number of LUTRAM bits.
  

**Raises**:

- `DesignFileError` - If the logic location (LL) file has not
  been uploaded.
- `ConnectionFailedError` - If the server could not count the bits.

<a id="skraft.skraft_fpga.FpgaDevice.all_bit_counts"></a>

#### all\_bit\_counts

```python
def all_bit_counts(pblock: Optional[str] = None) -> dict[str, int]
```

Get every bit count for the loaded design in one call.

Without a pblock, the counts cover the whole device and come from
the FpgaGetAllBitCounts RPC. With a pblock, each count only includes
the bits that fall inside that pblock, and each memory type is
requested separately. A memory type whose design file has not been
uploaded gives a count of 0.

**Arguments**:

- `pblock` _Optional[str]_ - The name of a pblock from the
  constraints (XDC) file. If omitted, the whole device is
  counted. Using a pblock requires the constraints file.
  

**Returns**:

  dict[str, int]: The bit counts, under the keys cram_bits,
  essential_cram_bits, bram_bits, flip_flop_bits,
  lutram_bits, pblock_bits and pblock_essential_bits.
  

**Raises**:

- `DesignFileError` - If a pblock is given and the constraints
  (XDC) file has not been uploaded.
- `ConnectionFailedError` - If the server could not provide the
  counts.

<a id="skraft.skraft_fpga.FpgaDevice.bit_count"></a>

#### bit\_count

```python
def bit_count(target: TargetMemory, pblock: Optional[str] = None) -> int
```

Count the bits of one memory type in the loaded design.

CRAM counts every configuration bit. ESSENTIAL_CRAM counts the
essential bits and needs the essential bits (EBD) file. FF, LUTRAM
and BRAM count storage element bits and need the logic location (LL)
file. Uses the FpgaGetBitCount RPC.

**Arguments**:

- `target` _TargetMemory_ - The memory type to count. Only one memory
  type can be given.
- `pblock` _Optional[str]_ - The name of a pblock from the
  constraints (XDC) file. If given, only the bits inside that
  pblock are counted.
  

**Returns**:

- `int` - The number of bits.
  

**Raises**:

- `DesignFileError` - If a design file needed for the target or
  the pblock has not been uploaded.
- `ValueError` - If the target is not a single memory type.
- `ConnectionFailedError` - If the server could not count the bits.

<a id="skraft.skraft_fpga.FpgaDevice.configure_seed"></a>

#### configure\_seed

```python
def configure_seed(seed: int) -> None
```

Set the seed of the random generator for random injections.

With the same seed, the same design and the same targets,
inject_random selects the same sequence of locations. Thus, you can
repeat a random campaign. Each SkraftFpga.attach sets a new seed
from the current time. Thus, set the seed after attach. Uses the
FpgaConfigureSeed RPC.

**Arguments**:

- `seed` _int_ - The seed, from 0 to 2**32 - 1.
  

**Raises**:

- `TypeError` - If the seed is not an integer.
- `ValueError` - If the seed is out of range.
- `ConnectionFailedError` - If the server could not set the seed.
  

**Examples**:

  >>> dev.configure_seed(42)
  >>> dev.inject_random(TargetMemory.ESSENTIAL_CRAM)

<a id="skraft.skraft_fpga.FpgaDevice.inject_random"></a>

#### inject\_random

```python
def inject_random(
    target: TargetMemory,
    pblock: Optional[str] = None,
    exclude_pblock: Optional[Iterable[str]] = None
) -> FpgaRandomInjectionReport
```

Inject a single upset at a random location.

To repeat the same locations, set the seed with configure_seed.
Uses the FpgaRandomBitFlip RPC. With exclude_pblock, it also uses
the FpgaExcludePblocks and FpgaIncludePblocks RPCs.

**Arguments**:

- `target` _TargetMemory_ - The memories where the upset may be
  injected. Several memories can be combined.
- `pblock` _Optional[str]_ - The name of a pblock from the
  constraints (XDC) file. If given, the upset is injected
  inside that pblock.
- `exclude_pblock` _Optional[Iterable[str]]_ - The names of pblocks
  from the constraints (XDC) file, for example a set. If
  given, the upset is not injected into the bits of these
  pblocks. The exclusion applies to this call only.
  

**Returns**:

- `FpgaRandomInjectionReport` - The location of the injected upset
  and, when known, the name of the affected net.
  

**Raises**:

- `TypeError` - If exclude_pblock is one string, or if it holds a
  name that is not a string.
- `ValueError` - If exclude_pblock holds the pblock given in pblock.
- `DesignFileError` - If a design file needed for the target or
  the pblocks has not been uploaded.
- `FrameAddressError` - If the server could not exclude the pblocks,
  or could not include them again.
- `ConnectionFailedError` - If the server could not inject the upset.
  

**Examples**:

  >>> dev.inject_random(TargetMemory.FF, exclude_pblock={"pb_sr"})
  >>> dev.inject_random(
  ...     TargetMemory.FF,
  ...     exclude_pblock={"pb_sr", "pb_sr2", "pb_sr3"},
  ... )

<a id="skraft.skraft_fpga.FpgaDevice.inject_exhaustive"></a>

#### inject\_exhaustive

```python
def inject_exhaustive(
        target: TargetMemory,
        pblock: Optional[str] = None) -> tuple[list[FpgaInjectionReport], int]
```

Inject an upset into every bit of the selected memories.

Uses the FpgaExhaustiveBitFlip RPC.

**Arguments**:

- `target` _TargetMemory_ - The memories to inject into. Several
  memories can be combined.
- `pblock` _Optional[str]_ - The name of a pblock from the
  constraints (XDC) file. If given, only the bits inside that
  pblock are injected.
  

**Returns**:

  tuple[list[FpgaInjectionReport], int]: A report for each
  injected location, and the number of injected bits as
  reported by the server.
  

**Raises**:

- `DesignFileError` - If a design file needed for the target or
  the pblock has not been uploaded.
- `ConnectionFailedError` - If the server could not run the
  injection.

<a id="skraft.skraft_fpga.FpgaDevice.inject_at"></a>

#### inject\_at

```python
def inject_at(far: int, word_index: int, bit_index: int,
              target: TargetMemory) -> FpgaInjectionReport
```

Inject an upset at one specific location.

Uses the FpgaBitFlip RPC.

**Arguments**:

- `far` _int_ - The frame address.
- `word_index` _int_ - The index of the word inside the frame.
- `bit_index` _int_ - The index of the bit inside the word.
- `target` _TargetMemory_ - The memory at that location. At most one
  storage element type can be given. If none is given, the
  location is treated as CRAM.
  

**Returns**:

- `FpgaInjectionReport` - The requested location. The server returns
  no details, so this simply repeats the input.
  

**Raises**:

- `DesignFileError` - If a design file needed for the target has
  not been uploaded.
- `ValueError` - If more than one storage element type is given.
- `ConnectionFailedError` - If the server could not inject the upset.

<a id="skraft.skraft_fpga.FpgaDevice.scrub"></a>

#### scrub

```python
def scrub(option: ScrubbingType,
          scrub_cycle: int,
          duration_ms: int,
          session_id: str = "") -> FpgaScrubReport
```

Run a scrubbing session on the device.

Uses the FpgaScrubbing RPC.

**Arguments**:

- `option` _ScrubbingType_ - The kind of scrubbing to run. Essential
  scrubbing needs the essential bits (EBD) file, which the
  server uses to tell essential upsets from non-essential
  ones.
- `scrub_cycle` _int_ - The scrub cycle setting for the session.
- `duration_ms` _int_ - How long the session runs, in milliseconds.
- `session_id` _str_ - An optional identifier for the session.
  

**Returns**:

- `FpgaScrubReport` - A summary of each scrub cycle, including its
  timings and the words that differed from the golden data.
  

**Raises**:

- `DesignFileError` - If essential scrubbing is requested and
  the essential bits (EBD) file has not been uploaded.
- `ConnectionFailedError` - If the server could not run the session.

<a id="skraft.skraft_fpga.FpgaDevice.run_campaign"></a>

#### run\_campaign

```python
def run_campaign(session: FpgaFiSession) -> FpgaFiSummary
```

Run a fault injection campaign defined by the user.

If the campaign targets essential bits, the essential bits (EBD)
file is needed. Uses the FpgaFaultInjection RPC.

**Arguments**:

- `session` _FpgaFiSession_ - The settings of the campaign.
  

**Returns**:

- `FpgaFiSummary` - The campaign settings, the number of injected and
  corrected faults, and the details of each affected word. The
  counts are worked out on the client from the returned words.
  

**Raises**:

- `DesignFileError` - If the campaign targets essential bits and
  the essential bits (EBD) file has not been uploaded.
- `ConnectionFailedError` - If the server could not run the campaign.

<a id="skraft.skraft_fpga.FpgaDevice.essential_frames"></a>

#### essential\_frames

```python
def essential_frames() -> list[FpgaFrame]
```

Get the essential bit masks from the essential bits (EBD) file.

Each returned frame is a mask, not configuration data. A set bit
marks an essential bit at that position. Requires the EBD file.
Uses the FpgaEssentialFrames RPC.

**Returns**:

- `list[FpgaFrame]` - The mask frames.
  

**Raises**:

- `DesignFileError` - If the essential bits (EBD) file has not
  been uploaded.
- `ConnectionFailedError` - If the server could not provide the
  frames.

<a id="skraft.skraft_fpga.FpgaDevice.mask_frames"></a>

#### mask\_frames

```python
def mask_frames() -> list[FpgaFrame]
```

Get the readback masks from the mask (MSD) file.

A set bit marks a position to ignore when a readback is compared
with the golden data. Requires the MSD file. Uses the
FpgaMaskFrames RPC.

**Returns**:

- `list[FpgaFrame]` - The mask frames.
  

**Raises**:

- `DesignFileError` - If the readback mask (MSD) file has not
  been uploaded.
- `ConnectionFailedError` - If the server could not provide the
  frames.

<a id="skraft.skraft_fpga.FpgaDevice.far_list"></a>

#### far\_list

```python
def far_list() -> list[int]
```

Get every frame address of the device.

Uses the FpgaFarList RPC.

**Returns**:

- `list[int]` - All frame addresses of the device.
  

**Raises**:

- `FrameAddressError` - If the server could not provide the list.

<a id="skraft.skraft_fpga.FpgaDevice.extract_fars_from_bitstream"></a>

#### extract\_fars\_from\_bitstream

```python
def extract_fars_from_bitstream(bitstream: str) -> list[int]
```

Extract every frame address from a bitstream.

The bitstream is sent to the server only for this operation, so the
bitstream uploaded with uploadDesignToServer is not changed. It must
be generated with per-frame CRC. Uses the
FpgaExtractFarsFromBitstream RPC.

**Arguments**:

- `bitstream` _str_ - The local path of the bitstream file.
  

**Returns**:

- `list[int]` - The frame addresses found in the bitstream.
  

**Raises**:

- `DesignFileError` - If the bitstream cannot be read.
- `FrameAddressError` - If the frame addresses could not be
  extracted.

<a id="skraft.skraft_fpga.FpgaDevice.exclude_frames"></a>

#### exclude\_frames

```python
def exclude_frames(fars: list[int]) -> None
```

Exclude frame addresses from feature operations.

Excluded frames are skipped by feature operations. Injection at a
single location with inject_at is not affected. Uses the
FpgaExcludeFars RPC.

**Arguments**:

- `fars` _list[int]_ - The frame addresses to exclude.
  

**Raises**:

- `FrameAddressError` - If the server could not exclude the frames.

<a id="skraft.skraft_fpga.FpgaDevice.pblocks"></a>

#### pblocks

```python
def pblocks() -> list[FpgaPblock]
```

List every pblock declared in the constraints.

Requires the constraints (XDC) file. Uses the FpgaGetPblocks RPC.

**Returns**:

- `list[FpgaPblock]` - Each pblock with its name and its range
  clauses. A clause can be passed to pblock_by_clause to find
  the frames it covers.
  

**Raises**:

- `DesignFileError` - If the constraints (XDC) file has not
  been uploaded.
- `FrameAddressError` - If the server could not provide the pblocks.

<a id="skraft.skraft_fpga.FpgaDevice.pblock_by_clause"></a>

#### pblock\_by\_clause

```python
def pblock_by_clause(clause: str) -> list[FpgaPblockFar]
```

Find the frames covered by a pblock range clause.

The result can be used with inject_at to limit injection to one
region of the device. Requires the constraints (XDC) file. Uses the
FpgaGetPblockFarsByClause RPC.

**Arguments**:

- `clause` _str_ - A pblock range clause, written as it appears in
  the constraints file.
  

**Returns**:

- `list[FpgaPblockFar]` - Each frame address covered by the clause,
  together with the word and bit ranges it covers inside that
  frame.
  

**Raises**:

- `DesignFileError` - If the constraints (XDC) file has not
  been uploaded.
- `FrameAddressError` - If the server could not resolve the clause.

<a id="skraft.skraft_fpga.FpgaDevice.write_bscan"></a>

#### write\_bscan

```python
def write_bscan(bscan: BscanPrimitive, value: int) -> bytes
```

Write a value into a USER register through a BSCAN primitive.

The value is sent most significant byte first and padded to a whole
number of bytes. Uses the FpgaWriteBscan RPC.

**Arguments**:

- `bscan` _BscanPrimitive_ - The BSCAN primitive that gives access to
  the register.
- `value` _int_ - The value to write. It must not be negative and
  must fit in the register.
  

**Returns**:

- `bytes` - The data returned by the register during the write.
  

**Raises**:

- `OverflowError` - If the value is negative or too large for the
  register.
- `BscanError` - If the register could not be written.

<a id="skraft.skraft_fpga.FpgaDevice.read_bscan"></a>

#### read\_bscan

```python
def read_bscan(bscan: BscanPrimitive) -> bytes
```

Read the current value of a USER register through a BSCAN primitive.

Uses the FpgaReadBscan RPC.

**Arguments**:

- `bscan` _BscanPrimitive_ - The BSCAN primitive that gives access to
  the register.
  

**Returns**:

- `bytes` - The current value of the register.
  

**Raises**:

- `BscanError` - If the register could not be read.

<a id="skraft.skraft_fpga.FpgaDevice.read_register"></a>

#### read\_register

```python
def read_register(reg_addr: int) -> int
```

Read a register of the device.

Uses the FpgaReadRegister RPC.

**Arguments**:

- `reg_addr` _int_ - The address of the register, for example
  RegisterAddress.STATUS.
  

**Returns**:

- `int` - The value of the register.
  

**Raises**:

- `FrameAddressError` - If the register could not be read.

<a id="skraft.skraft_fpga.FpgaDevice.write_register"></a>

#### write\_register

```python
def write_register(reg_addr: int, value: int)
```

Write a value into a register of the device.

Uses the FpgaWriteRegister RPC.

**Arguments**:

- `reg_addr` _int_ - The address of the register, for example
  RegisterAddress.CTRL0.
- `value` _int_ - The value to write.
  

**Raises**:

- `FrameAddressError` - If the register could not be written.

<a id="skraft.skraft_fpga.FpgaDevice.decode_far"></a>

#### decode\_far

```python
def decode_far(far: int) -> FpgaFar7series | FpgaFarUltraScale
```

Split a frame address into its individual fields.

The server decides which device family layout applies. Uses the
FpgaDecodeFrameAddress RPC.

**Arguments**:

- `far` _int_ - The frame address to decode.
  

**Returns**:

  FpgaFar7series | FpgaFarUltraScale: The decoded fields, in the
  layout of the device family.
  

**Raises**:

- `FrameAddressError` - If the server could not decode the address.

<a id="skraft.skraft_fpga.FpgaDevice.xadc"></a>

#### xadc

```python
def xadc(sensor: XadcSensorSelector | int) -> XadcSensor
```

Read an XADC sensor of the device.

The sensor is given either by a selector of the library, for example
VCCINT or TEMPERATURE, or by the DRP address of its status register.
The value is in units of the International System of Units (SI):
volts (V) for voltages and degrees Celsius (degC) for temperatures.

Only the on-chip sensors, and their recorded maximum and minimum
values, can be read. Uses the FpgaXadcSensor RPC.

**Arguments**:

- `sensor` _XadcSensorSelector | int_ - The selector of the sensor,
  or the DRP address of its status register.
  

**Returns**:

- `XadcSensor` - The value of the sensor, in V or degC.
  

**Raises**:

- `TypeError` - If the sensor is neither a selector nor a DRP
  address.
- `XadcError` - If the server could not read the sensor, for example
  because the DRP address is not a sensor, or the device does
  not have the sensor.
  

**Examples**:

  >>> dev.xadc(VCCINT).value       # V
  >>> dev.xadc(TEMPERATURE).value  # degC
  >>> dev.xadc(0x01).value         # V, VCCINT by DRP address

<a id="skraft.skraft_fpga.FpgaDevice.xadc_alarm"></a>

#### xadc\_alarm

```python
def xadc_alarm(alarm: XadcAlarmSelector | int) -> XadcAlarm
```

Read an XADC alarm threshold of the device.

The threshold is given either by a selector of the library, for
example TEMPERATURE_UPPER or VCCINT_LOWER, or by the DRP address of
its alarm register. The server converts the raw value of the
register. The value is in units of the International System of
Units (SI): volts (V) for voltages and degrees Celsius (degC) for
temperatures. Uses the FpgaXadcAlarm RPC.

**Arguments**:

- `alarm` _XadcAlarmSelector | int_ - The selector of the threshold,
  or the DRP address of its alarm register.
  

**Returns**:

- `XadcAlarm` - The threshold, in V or degC.
  

**Raises**:

- `TypeError` - If the alarm is neither a selector nor a DRP
  address.
- `XadcError` - If the server could not read the threshold, for
  example because the DRP address is not an alarm register,
  or the device does not have the alarm.
  

**Examples**:

  >>> dev.xadc_alarm(TEMPERATURE_UPPER).value  # degC
  >>> dev.xadc_alarm(VCCINT_LOWER).value       # V

<a id="skraft.skraft_fpga.FpgaDevice.set_xadc_alarm"></a>

#### set\_xadc\_alarm

```python
def set_xadc_alarm(alarm: XadcAlarmSelector | int, value: float) -> None
```

Set an XADC alarm threshold of the device.

The value is in units of the International System of Units (SI):
volts (V) for voltages and degrees Celsius (degC) for temperatures.
The server converts it into the raw value of the alarm register, and
reads the register back to verify the write. The server keeps the
bits of the register that are not part of the threshold, for example
the automatic shutdown enable of OT_LIMIT, or the hysteresis or
window mode of TEMPERATURE_LOWER in UltraScale+ devices. Uses the
FpgaXadcSetAlarm RPC.

Caution: if the automatic shutdown is enabled, the device shuts down
when the temperature is above OT_LIMIT.

**Arguments**:

- `alarm` _XadcAlarmSelector | int_ - The selector of the threshold,
  or the DRP address of its alarm register.
- `value` _float_ - The threshold, in V or degC.
  

**Raises**:

- `TypeError` - If the alarm is neither a selector nor a DRP
  address, or if the value is not a number.
- `XadcError` - If the server could not set the threshold, for
  example because the value is outside the range of the ADC,
  or the design does not allow writes through JTAG.
  

**Examples**:

  >>> dev.set_xadc_alarm(TEMPERATURE_UPPER, 85.0)  # degC
  >>> dev.set_xadc_alarm(VCCINT_LOWER, 0.97)       # V

<a id="skraft.skraft_fpga.FpgaDevice.xadc_flags"></a>

#### xadc\_flags

```python
def xadc_flags() -> XadcFlags
```

Read the state of the XADC alarms of the device.

The server reads the flag register and decodes it. Uses the
FpgaXadcFlags RPC.

**Returns**:

- `XadcFlags` - The state of each alarm and of the JTAG access.
  

**Raises**:

- `XadcError` - If the server could not read the flag register.
  

**Examples**:

  >>> dev.xadc_flags().temperature  # True while ALM0 is on

<a id="skraft.skraft_fpga.FpgaDevice.read_xadc_register"></a>

#### read\_xadc\_register

```python
def read_xadc_register(register: XadcRegister | int) -> int
```

Read an XADC register of the device.

Only the flag register, the configuration registers and the alarm
registers can be read, see XadcRegister. Uses the
FpgaXadcReadRegister RPC.

**Arguments**:

- `register` _XadcRegister | int_ - The register, or its DRP
  address.
  

**Returns**:

- `int` - The raw 16-bit value of the register.
  

**Raises**:

- `TypeError` - If the register is not an XadcRegister or an int.
- `XadcError` - If the server could not read the register, for
  example because the DRP address is not the flag register, or
  a configuration or alarm register.
  

**Examples**:

  >>> dev.read_xadc_register(XadcRegister.CONFIG1)
  >>> dev.read_xadc_register(XadcRegister.FLAG) & 0x0001  # ALM0

<a id="skraft.skraft_fpga.FpgaDevice.write_xadc_register"></a>

#### write\_xadc\_register

```python
def write_xadc_register(register: XadcRegister | int, value: int) -> None
```

Write a raw value into an XADC control register of the device.

Only the configuration registers and the alarm registers can be
written, see XadcRegister. The flag register is read only. UG480
gives the meaning of each bit. Uses the FpgaXadcWriteRegister RPC.

**Arguments**:

- `register` _XadcRegister | int_ - The register, or its DRP
  address.
- `value` _int_ - The raw 16-bit value to write.
  

**Raises**:

- `TypeError` - If the register is not an XadcRegister or an int, or
  if the value is not an int.
- `ValueError` - If the value does not fit in 16 bits.
- `XadcError` - If the server could not write the register, for
  example because the DRP address is not a configuration or
  alarm register.
  

**Examples**:

  >>> dev.write_xadc_register(XadcRegister.ALARM8, 0x5800)

<a id="skraft.skraft_fpga.SkraftFpga"></a>

## SkraftFpga Objects

```python
class SkraftFpga()
```

A client for a single connection to an SK-RAFT server.

Use connect to create a client and open the connection. The class can
be used as a context manager, in which case the connection is closed
automatically when the block ends.

**Attributes**:

- `ip` _str_ - The address of the server.
- `port` _int_ - The port of the server.

<a id="skraft.skraft_fpga.SkraftFpga.__init__"></a>

#### \_\_init\_\_

```python
def __init__(ip: str, port: int)
```

Create a client without opening a connection.

Use connect instead to get a client that is ready to use.

**Arguments**:

- `ip` _str_ - The address of the server.
- `port` _int_ - The port of the server.

<a id="skraft.skraft_fpga.SkraftFpga.connect"></a>

#### connect

```python
@classmethod
def connect(cls,
            ip: str,
            port: int,
            tls_server_cert: Optional[str] = None,
            tls_cert: Optional[str] = None,
            tls_key: Optional[str] = None) -> "SkraftFpga"
```

Create a client and open a connection to the server.

After connecting, the server version is checked and a warning is
printed if it does not match the version this client expects.

The connection uses TLS when any of the TLS files is given. This is
needed when the server is started with -tls-cert and -tls-key.

**Arguments**:

- `ip` _str_ - The address of the server.
- `port` _int_ - The port of the server.
- `tls_server_cert` _Optional[str]_ - The path of the PEM certificate
  of the server (the -tls-cert of the server), used to verify
  the server. Its names must include the ip given here. If it
  is not given, the server is verified against the trusted
  certificates of the system.
- `tls_cert` _Optional[str]_ - The path of the PEM certificate of
  this client. It is needed when the server is started with
  -tls-public-key, and must hold that public key. Give it
  together with tls_key.
- `tls_key` _Optional[str]_ - The path of the PEM private key of this
  client, the private key of tls_cert.
  

**Returns**:

- `SkraftFpga` - The connected client.
  

**Raises**:

- `ValueError` - If only one of tls_cert and tls_key is given.
- `OSError` - If a TLS file cannot be read.
- `ConnectionFailedError` - If the server cannot be reached.

<a id="skraft.skraft_fpga.SkraftFpga.version"></a>

#### version

```python
def version() -> str
```

Get the version of the server.

Uses the Version RPC.

**Returns**:

- `str` - The version reported by the server.
  

**Raises**:

- `ConnectionFailedError` - If the server could not be reached.

<a id="skraft.skraft_fpga.SkraftFpga.__enter__"></a>

#### \_\_enter\_\_

```python
def __enter__() -> "SkraftFpga"
```

Enter the context manager.

**Returns**:

- `SkraftFpga` - This client.

<a id="skraft.skraft_fpga.SkraftFpga.__exit__"></a>

#### \_\_exit\_\_

```python
def __exit__(*exc_info) -> None
```

Leave the context manager and close the connection.

**Arguments**:

- `*exc_info` - Details of any exception raised inside the block.
  They are not used.

<a id="skraft.skraft_fpga.SkraftFpga.disconnect"></a>

#### disconnect

```python
def disconnect() -> None
```

Close the connection to the server.

Calling it again after the connection is closed has no effect.

<a id="skraft.skraft_fpga.SkraftFpga.get_devices"></a>

#### get\_devices

```python
def get_devices() -> list[FpgaDevice]
```

List the devices connected to the server.

Listing the devices does not reserve them. Use attach to reserve a
device. Uses the FpgaGetDevices RPC.

**Returns**:

- `list[FpgaDevice]` - One entry for each connected device, with its
  serial number and part number.
  

**Raises**:

- `DeviceReservationError` - If the server could not list the
  devices.

<a id="skraft.skraft_fpga.SkraftFpga.attach"></a>

#### attach

```python
def attach(serial_number: str) -> FpgaDevice
```

Reserve a device by its serial number.

The serial number is the one Vivado shows for the device. If the
reservation fails, any programmers opened during the attempt are
closed again. Uses the FpgaConnect and FpgaSelectDevice RPCs.

**Arguments**:

- `serial_number` _str_ - The serial number of the device to reserve.
  

**Returns**:

- `FpgaDevice` - The reserved device, with its serial number and
  part number. It can be used as a context manager so that
  the reservation is released automatically.
  

**Raises**:

- `DeviceReservationError` - If the device could not be reserved.
  When no device matches, the error message lists the serial
  numbers of the connected devices.

<a id="skraft.datatypes"></a>

# skraft.datatypes

Data types used by the SK-RAFT client.

Holds the options, design file settings and result types that the client
sends to and receives from the SK-RAFT server.

<a id="skraft.datatypes.TargetMemory"></a>

## TargetMemory Objects

```python
class TargetMemory(IntFlag)
```

The memories that can be selected for fault injection.

The members are flags and can be combined. Random and exhaustive
injection accept combined memories. An injection at one specific
location accepts at most one storage element type (FF, LUTRAM or BRAM).

**Attributes**:

- `CRAM` _TargetMemory_ - The whole configuration memory, with no
  further limit.
- `ESSENTIAL_CRAM` _TargetMemory_ - Only the essential configuration
  bits. Needs the essential bits (EBD) file.
- `FF` _TargetMemory_ - Flip-flop bits. Needs the logic location (LL)
  file.
- `LUTRAM` _TargetMemory_ - LUTRAM bits. Needs the logic location (LL)
  file.
- `BRAM` _TargetMemory_ - Block RAM bits. Needs the logic location (LL)
  file.

<a id="skraft.datatypes.TargetMemory.required_design_files"></a>

#### required\_design\_files

```python
@property
def required_design_files() -> tuple[str, ...]
```

The design files that this selection depends on.

**Returns**:

  tuple[str, ...]: The names of the Design fields that must be
  set. Empty if no design file is needed.

<a id="skraft.datatypes.ReadbackOption"></a>

## ReadbackOption Objects

```python
class ReadbackOption(int, Enum)
```

The ways a full readback can be done.

**Attributes**:

- `READBACK` _ReadbackOption_ - A plain readback of the configuration
  memory.
- `READBACK_CAPTURE` _ReadbackOption_ - A readback that first captures
  the current state of all changeable elements of the device.

<a id="skraft.datatypes.ScrubbingType"></a>

## ScrubbingType Objects

```python
class ScrubbingType(int, Enum)
```

The scrubbing mode.

**Attributes**:

- `READBACK` _ScrubbingType_ - Standard scrubbing, without the essential
  bits information.
- `ESSENTIAL` _ScrubbingType_ - Scrubbing that also uses the essential
  bits (EBD) file to tell essential upsets from non-essential
  ones.

<a id="skraft.datatypes.FaultType"></a>

## FaultType Objects

```python
class FaultType(int, Enum)
```

The fault model of a fault injection campaign.

The values match the fault types that the server understands.

**Attributes**:

- `RANDOM` _FaultType_ - Faults are injected at random locations.
- `EXHAUSTIVE` _FaultType_ - Faults are injected at every location in
  turn.

<a id="skraft.datatypes.RegisterAddress"></a>

## RegisterAddress Objects

```python
class RegisterAddress(int, Enum)
```

The addresses of the configuration registers of the device, for
FpgaDevice.read_register and FpgaDevice.write_register.

They are copies of the register addresses of the SK-RAFT server: the
ID of each register, shifted into the register address field (bit 13)
of a type 1 packet header.

**Attributes**:

- `FAR` _RegisterAddress_ - The frame address register.
- `CRC` _RegisterAddress_ - The cyclic redundancy check register.
- `STATUS` _RegisterAddress_ - The status register.
- `CTRL0` _RegisterAddress_ - The control register 0.
- `MASK` _RegisterAddress_ - The masking register for CTRL0 and CTRL1.
- `CMD` _RegisterAddress_ - The command register.
- `IDCODE` _RegisterAddress_ - The device ID register.
- `FDRI` _RegisterAddress_ - The frame data register input, which
  takes the configuration data.
- `FDRO` _RegisterAddress_ - The frame data register output, which
  gives the readback data.
- `CTRL1` _RegisterAddress_ - The control register 1.
- `COR0` _RegisterAddress_ - The configuration option register 0.
- `COR1` _RegisterAddress_ - The configuration option register 1.

<a id="skraft.datatypes.Design"></a>

## Design Objects

```python
@dataclass(frozen=True)
class Design()
```

The files of a design, as paths on the client computer.

FpgaDevice.uploadDesignToServer uploads every file that is set. All
files are optional. An operation that needs a file that is not set
raises an error that names the missing file.

**Attributes**:

- `bit` _Optional[str]_ - The bitstream, used to program the device.
- `ebd` _Optional[str]_ - The essential bits file.
- `ll` _Optional[str]_ - The logic location file, which locates the
  flip-flop, LUTRAM and BRAM bits.
- `xdc` _Optional[str]_ - The constraints file, which declares the
  pblocks.
- `rbd` _Optional[str]_ - The readback data file, used for self-test.
- `msd` _Optional[str]_ - The readback mask file, used for self-test.

<a id="skraft.datatypes.Design.require"></a>

#### require

```python
def require(*fields: str) -> None
```

Check that the named design files are set.

**Arguments**:

- `*fields` _str_ - The names of the design files to check.
  

**Raises**:

- `DesignFileError` - If one or more of the named files are not set.
  The error message names the missing files.

<a id="skraft.datatypes.FpgaFar"></a>

## FpgaFar Objects

```python
class FpgaFar()
```

A frame address split into its individual fields.

This is the common base for the layouts of each device family.

**Attributes**:

- `raw` _int_ - The original frame address.
- `blocktype` _int_ - The block type field.
- `row_address` _int_ - The row address field.
- `column_address` _int_ - The column address field.
- `minor_address` _int_ - The minor address field.

<a id="skraft.datatypes.FpgaFar.__init__"></a>

#### \_\_init\_\_

```python
def __init__(raw: int, blocktype: int, row_address: int, column_address: int,
             minor_address: int) -> None
```

Create a decoded frame address.

**Arguments**:

- `raw` _int_ - The original frame address.
- `blocktype` _int_ - The block type field.
- `row_address` _int_ - The row address field.
- `column_address` _int_ - The column address field.
- `minor_address` _int_ - The minor address field.

<a id="skraft.datatypes.FpgaFar.raw"></a>

#### raw

```python
@property
def raw() -> int
```

The original frame address.

<a id="skraft.datatypes.FpgaFar.blocktype"></a>

#### blocktype

```python
@property
def blocktype() -> int
```

The block type field.

<a id="skraft.datatypes.FpgaFar.row_address"></a>

#### row\_address

```python
@property
def row_address() -> int
```

The row address field.

<a id="skraft.datatypes.FpgaFar.column_address"></a>

#### column\_address

```python
@property
def column_address() -> int
```

The column address field.

<a id="skraft.datatypes.FpgaFar.minor_address"></a>

#### minor\_address

```python
@property
def minor_address() -> int
```

The minor address field.

<a id="skraft.datatypes.FpgaFar7series"></a>

## FpgaFar7series Objects

```python
class FpgaFar7series(FpgaFar)
```

A frame address in the 7 series layout.

Has all the fields of FpgaFar, plus the top or bottom half field.

**Attributes**:

- `topbottom` _int_ - Whether the frame is in the top or the bottom half
  of the device.

<a id="skraft.datatypes.FpgaFar7series.__init__"></a>

#### \_\_init\_\_

```python
def __init__(raw: int, blocktype: int, topbottom: int, row_address: int,
             column_address: int, minor_address: int) -> None
```

Create a decoded 7 series frame address.

**Arguments**:

- `raw` _int_ - The original frame address.
- `blocktype` _int_ - The block type field.
- `topbottom` _int_ - The top or bottom half field.
- `row_address` _int_ - The row address field.
- `column_address` _int_ - The column address field.
- `minor_address` _int_ - The minor address field.

<a id="skraft.datatypes.FpgaFar7series.topbottom"></a>

#### topbottom

```python
@property
def topbottom() -> int
```

Whether the frame is in the top or the bottom half of the device.

<a id="skraft.datatypes.FpgaFarUltraScale"></a>

## FpgaFarUltraScale Objects

```python
class FpgaFarUltraScale(FpgaFar)
```

A frame address in the UltraScale layout.

Has the same fields as FpgaFar.

<a id="skraft.datatypes.FpgaFarUltraScale.__init__"></a>

#### \_\_init\_\_

```python
def __init__(raw: int, blocktype: int, row_address: int, column_address: int,
             minor_address: int) -> None
```

Create a decoded UltraScale frame address.

**Arguments**:

- `raw` _int_ - The original frame address.
- `blocktype` _int_ - The block type field.
- `row_address` _int_ - The row address field.
- `column_address` _int_ - The column address field.
- `minor_address` _int_ - The minor address field.

<a id="skraft.datatypes.FpgaPblockRange"></a>

## FpgaPblockRange Objects

```python
class FpgaPblockRange()
```

An inclusive range of indexes.

**Attributes**:

- `start` _int_ - The first index of the range.
- `end` _int_ - The last index of the range. This index is included.

<a id="skraft.datatypes.FpgaPblockRange.__init__"></a>

#### \_\_init\_\_

```python
def __init__(start: int, end: int) -> None
```

Create a range.

**Arguments**:

- `start` _int_ - The first index of the range.
- `end` _int_ - The last index of the range.

<a id="skraft.datatypes.FpgaPblockRange.start"></a>

#### start

```python
@property
def start() -> int
```

The first index of the range.

<a id="skraft.datatypes.FpgaPblockRange.end"></a>

#### end

```python
@property
def end() -> int
```

The last index of the range.

<a id="skraft.datatypes.FpgaPblockAreaRange"></a>

## FpgaPblockAreaRange Objects

```python
class FpgaPblockAreaRange()
```

An area of a frame that a pblock occupies.

**Attributes**:

- `bit_range` _FpgaPblockRange_ - The bit indexes that the area occupies
  in each of its words.
- `word_range` _FpgaPblockRange_ - The word indexes that the area
  occupies in the frame.

<a id="skraft.datatypes.FpgaPblockAreaRange.__init__"></a>

#### \_\_init\_\_

```python
def __init__(bit_range: FpgaPblockRange, word_range: FpgaPblockRange) -> None
```

Create an area.

**Arguments**:

- `bit_range` _FpgaPblockRange_ - The bit indexes inside each word.
- `word_range` _FpgaPblockRange_ - The word indexes inside the frame.

<a id="skraft.datatypes.FpgaPblockAreaRange.bit_range"></a>

#### bit\_range

```python
@property
def bit_range() -> FpgaPblockRange
```

The bit indexes that the area occupies in each of its words.

<a id="skraft.datatypes.FpgaPblockAreaRange.word_range"></a>

#### word\_range

```python
@property
def word_range() -> FpgaPblockRange
```

The word indexes that the area occupies in the frame.

<a id="skraft.datatypes.FpgaPblockFar"></a>

## FpgaPblockFar Objects

```python
class FpgaPblockFar()
```

One frame address that a pblock covers.

**Attributes**:

- `far` _int_ - The frame address.
- `occupied_area` _list[FpgaPblockAreaRange]_ - The areas of this frame
  that the pblock occupies.

<a id="skraft.datatypes.FpgaPblockFar.__init__"></a>

#### \_\_init\_\_

```python
def __init__(far: int, occupied_area: list[FpgaPblockAreaRange]) -> None
```

Create a covered frame entry.

**Arguments**:

- `far` _int_ - The frame address.
- `occupied_area` _list[FpgaPblockAreaRange]_ - The areas of the
  frame that the pblock occupies.

<a id="skraft.datatypes.FpgaPblockFar.far"></a>

#### far

```python
@property
def far() -> int
```

The frame address.

<a id="skraft.datatypes.FpgaPblockFar.occupied_area"></a>

#### occupied\_area

```python
@property
def occupied_area() -> list[FpgaPblockAreaRange]
```

The areas of this frame that the pblock occupies.

<a id="skraft.datatypes.FpgaPblock"></a>

## FpgaPblock Objects

```python
class FpgaPblock()
```

A pblock declared in the constraints (XDC) file.

Each clause is kept as a plain string, so it can be passed directly to
FpgaDevice.pblock_by_clause.

**Attributes**:

- `name` _str_ - The name of the pblock, as written in the constraints.
- `clauses` _list[str]_ - The range clauses of the pblock.

<a id="skraft.datatypes.FpgaPblock.__init__"></a>

#### \_\_init\_\_

```python
def __init__(name: str, clauses: list[str]) -> None
```

Create a pblock.

**Arguments**:

- `name` _str_ - The name of the pblock.
- `clauses` _list[str]_ - The range clauses of the pblock.

<a id="skraft.datatypes.FpgaPblock.name"></a>

#### name

```python
@property
def name() -> str
```

The name of the pblock, as written in the constraints.

<a id="skraft.datatypes.FpgaPblock.clauses"></a>

#### clauses

```python
@property
def clauses() -> list[str]
```

The range clauses of the pblock.

<a id="skraft.datatypes.FpgaWord"></a>

## FpgaWord Objects

```python
class FpgaWord()
```

A single 32-bit word of configuration data.

The server sends words as plain numbers. This class wraps them for
convenience.

**Attributes**:

- `value` _int_ - The value of the word.

<a id="skraft.datatypes.FpgaWord.__init__"></a>

#### \_\_init\_\_

```python
def __init__(value: int)
```

Create a word.

**Arguments**:

- `value` _int_ - The 32-bit value of the word.

<a id="skraft.datatypes.FpgaWord.value"></a>

#### value

```python
@property
def value() -> int
```

The value of the word.

<a id="skraft.datatypes.FpgaFrame"></a>

## FpgaFrame Objects

```python
class FpgaFrame()
```

A configuration frame.

**Attributes**:

- `far` _int_ - The frame address of the frame.
- `words` _list[FpgaWord]_ - The words of the frame. The number of words
  depends on the device family.

<a id="skraft.datatypes.FpgaFrame.__init__"></a>

#### \_\_init\_\_

```python
def __init__(far: int, words: list[FpgaWord])
```

Create a frame.

**Arguments**:

- `far` _int_ - The frame address of the frame.
- `words` _list[FpgaWord]_ - The words of the frame.

<a id="skraft.datatypes.FpgaFrame.far"></a>

#### far

```python
@property
def far() -> int
```

The frame address of the frame.

<a id="skraft.datatypes.FpgaFrame.words"></a>

#### words

```python
@property
def words() -> list[FpgaWord]
```

The words of the frame.

<a id="skraft.datatypes.BscanPrimitive"></a>

## BscanPrimitive Objects

```python
class BscanPrimitive()
```

A BSCAN USER register.

The register number is checked when the object is created, so an
invalid number is reported straight away rather than during a later
read or write.

**Attributes**:

- `MIN_REGISTER` _int_ - The lowest valid USER register number.
- `MAX_REGISTER` _int_ - The highest valid USER register number.
- `user_register_id` _int_ - The USER register number.
- `size_in_bits` _int_ - The width of the register, in bits.

<a id="skraft.datatypes.BscanPrimitive.__init__"></a>

#### \_\_init\_\_

```python
def __init__(user_register_id: int, size_in_bits: int)
```

Create a USER register.

**Arguments**:

- `user_register_id` _int_ - The USER register number. It must be
  between MIN_REGISTER and MAX_REGISTER.
- `size_in_bits` _int_ - The width of the register, in bits.
  

**Raises**:

- `ValueError` - If the register number is outside the valid range.

<a id="skraft.datatypes.BscanPrimitive.user_register_id"></a>

#### user\_register\_id

```python
@property
def user_register_id() -> int
```

The USER register number.

<a id="skraft.datatypes.BscanPrimitive.size_in_bits"></a>

#### size\_in\_bits

```python
@property
def size_in_bits() -> int
```

The width of the register, in bits.

<a id="skraft.datatypes.BscanPrimitive.shift_in"></a>

#### shift\_in

```python
def shift_in(grpc_client, value: bytes, readonly: bool = False) -> bytes
```

Shift a value through the register and return what comes out.

In read-only mode the register contents stay unchanged and the
FpgaReadBscan RPC is used. Otherwise the value is written into the
register through the FpgaWriteBscan RPC.

**Arguments**:

- `grpc_client` _skraft_client_pb2_grpc.SKRaftFpgaStub_ - The gRPC
  stub of the server connection.
- `value` _bytes_ - The data to shift into the register.
- `readonly` _bool_ - If True, read the register without changing
  it.
  

**Returns**:

- `bytes` - The data shifted out of the register.
  

**Raises**:

- `grpc.RpcError` - If the server call fails.

<a id="skraft.datatypes.Bscan"></a>

## Bscan Objects

```python
class Bscan()
```

A BSCAN USER register that is read and written as an integer.

**Attributes**:

- `primitive` _BscanPrimitive_ - The USER register that this object uses.

<a id="skraft.datatypes.Bscan.__init__"></a>

#### \_\_init\_\_

```python
def __init__(dev, user_register_id: int, size_in_bits: int)
```

Create a register handle for an attached device.

**Arguments**:

- `dev` _FpgaDevice_ - The attached device that holds the register.
- `user_register_id` _int_ - The USER register number.
- `size_in_bits` _int_ - The width of the register, in bits.
  

**Raises**:

- `ValueError` - If the register number is outside the valid range.

<a id="skraft.datatypes.Bscan.primitive"></a>

#### primitive

```python
@property
def primitive() -> BscanPrimitive
```

The USER register that this object uses.

<a id="skraft.datatypes.Bscan.write"></a>

#### write

```python
def write(value: int) -> None
```

Write a value into the register.

**Arguments**:

- `value` _int_ - The value to write. It must not be negative and
  must fit in the register.
  

**Raises**:

- `OverflowError` - If the value is negative or too large for the
  register.
- `BscanError` - If the register could not be written.

<a id="skraft.datatypes.Bscan.read"></a>

#### read

```python
def read() -> int
```

Read the current value of the register.

Any bits above the width of the register are cleared.

**Returns**:

- `int` - The value of the register.
  

**Raises**:

- `BscanError` - If the register could not be read.

<a id="skraft.datatypes.FpgaInjectionReport"></a>

## FpgaInjectionReport Objects

```python
class FpgaInjectionReport()
```

The result of an injection at one location.

FpgaDevice.inject_at returns one report, and
FpgaDevice.inject_exhaustive returns one for each location. For
inject_at the server returns no details, so the report repeats the
requested location and has no net name.

**Attributes**:

- `far` _int_ - The frame address of the injection.
- `word_index` _int_ - The index of the word inside the frame.
- `bit_index` _int_ - The index of the bit inside the word.
- `target` _TargetMemory_ - The memory that was targeted.
- `net_name` _Optional[str]_ - The name of the affected net, or None if
  it is not known.

<a id="skraft.datatypes.FpgaInjectionReport.__init__"></a>

#### \_\_init\_\_

```python
def __init__(far: int,
             word_index: int,
             bit_index: int,
             target: TargetMemory,
             net_name: Optional[str] = None)
```

Create an injection report.

**Arguments**:

- `far` _int_ - The frame address of the injection.
- `word_index` _int_ - The index of the word inside the frame.
- `bit_index` _int_ - The index of the bit inside the word.
- `target` _TargetMemory_ - The memory that was targeted.
- `net_name` _Optional[str]_ - The name of the affected net, if
  known.

<a id="skraft.datatypes.FpgaInjectionReport.far"></a>

#### far

```python
@property
def far() -> int
```

The frame address of the injection.

<a id="skraft.datatypes.FpgaInjectionReport.word_index"></a>

#### word\_index

```python
@property
def word_index() -> int
```

The index of the word inside the frame.

<a id="skraft.datatypes.FpgaInjectionReport.bit_index"></a>

#### bit\_index

```python
@property
def bit_index() -> int
```

The index of the bit inside the word.

<a id="skraft.datatypes.FpgaInjectionReport.target"></a>

#### target

```python
@property
def target() -> TargetMemory
```

The memory that was targeted.

<a id="skraft.datatypes.FpgaInjectionReport.net_name"></a>

#### net\_name

```python
@property
def net_name() -> Optional[str]
```

The name of the affected net, or None if it is not known.

<a id="skraft.datatypes.FpgaRandomInjectionReport"></a>

## FpgaRandomInjectionReport Objects

```python
class FpgaRandomInjectionReport()
```

The result of a single random injection.

Returned by FpgaDevice.inject_random.

**Attributes**:

- `far` _int_ - The frame address where the injection took place.
- `word_index` _int_ - The index of the word inside the frame.
- `bit_index` _int_ - The index of the bit inside the word.
- `target` _TargetMemory_ - The memory that received the injection.
- `net_name` _Optional[str]_ - The name of the net at the injection site
  when the upset hit a flip-flop, otherwise None.

<a id="skraft.datatypes.FpgaRandomInjectionReport.__init__"></a>

#### \_\_init\_\_

```python
def __init__(far: int,
             word_index: int,
             bit_index: int,
             target: TargetMemory,
             net_name: Optional[str] = None)
```

Create a random injection report.

**Arguments**:

- `far` _int_ - The frame address where the injection took place.
- `word_index` _int_ - The index of the word inside the frame.
- `bit_index` _int_ - The index of the bit inside the word.
- `target` _TargetMemory_ - The memory that received the injection.
- `net_name` _Optional[str]_ - The name of the net at the injection
  site, if known.

<a id="skraft.datatypes.FpgaRandomInjectionReport.far"></a>

#### far

```python
@property
def far() -> int
```

The frame address where the injection took place.

<a id="skraft.datatypes.FpgaRandomInjectionReport.word_index"></a>

#### word\_index

```python
@property
def word_index() -> int
```

The index of the word inside the frame.

<a id="skraft.datatypes.FpgaRandomInjectionReport.bit_index"></a>

#### bit\_index

```python
@property
def bit_index() -> int
```

The index of the bit inside the word.

<a id="skraft.datatypes.FpgaRandomInjectionReport.target"></a>

#### target

```python
@property
def target() -> TargetMemory
```

The memory that received the injection.

<a id="skraft.datatypes.FpgaRandomInjectionReport.net_name"></a>

#### net\_name

```python
@property
def net_name() -> Optional[str]
```

The name of the net at the injection site, or None.

<a id="skraft.datatypes.FpgaScrubWordSummary"></a>

## FpgaScrubWordSummary Objects

```python
class FpgaScrubWordSummary()
```

The details of one word that a scrubbing session affected.

**Attributes**:

- `far` _int_ - The frame address of the affected frame.
- `word_index` _int_ - The index of the affected word.
- `bit_index` _int_ - The index of the affected bit.
- `golden_word_value` _int_ - The expected value of the word.
- `erroneous_word_value` _int_ - The value of the word that was found
  before the correction.
- `ebd_word_value` _int_ - The word at the same location in the
  essential bits (EBD) file.
- `msd_word_value` _int_ - The word at the same location in the readback
  mask (MSD) file.
- `is_essential` _bool_ - True if the affected bit is essential.

<a id="skraft.datatypes.FpgaScrubWordSummary.__init__"></a>

#### \_\_init\_\_

```python
def __init__(far: int, word_index: int, bit_index: int, golden_word_value: int,
             erroneous_word_value: int, ebd_word_value: int,
             msd_word_value: int, is_essential: bool)
```

Create a word summary.

**Arguments**:

- `far` _int_ - The frame address of the affected frame.
- `word_index` _int_ - The index of the affected word.
- `bit_index` _int_ - The index of the affected bit.
- `golden_word_value` _int_ - The expected value of the word.
- `erroneous_word_value` _int_ - The value found before the
  correction.
- `ebd_word_value` _int_ - The matching word from the essential bits
  (EBD) file.
- `msd_word_value` _int_ - The matching word from the readback mask
  (MSD) file.
- `is_essential` _bool_ - True if the affected bit is essential.

<a id="skraft.datatypes.FpgaScrubWordSummary.far"></a>

#### far

```python
@property
def far() -> int
```

The frame address of the affected frame.

<a id="skraft.datatypes.FpgaScrubWordSummary.word_index"></a>

#### word\_index

```python
@property
def word_index() -> int
```

The index of the affected word.

<a id="skraft.datatypes.FpgaScrubWordSummary.bit_index"></a>

#### bit\_index

```python
@property
def bit_index() -> int
```

The index of the affected bit.

<a id="skraft.datatypes.FpgaScrubWordSummary.golden_word_value"></a>

#### golden\_word\_value

```python
@property
def golden_word_value() -> int
```

The expected value of the word.

<a id="skraft.datatypes.FpgaScrubWordSummary.erroneous_word_value"></a>

#### erroneous\_word\_value

```python
@property
def erroneous_word_value() -> int
```

The value of the word that was found before the correction.

<a id="skraft.datatypes.FpgaScrubWordSummary.ebd_word_value"></a>

#### ebd\_word\_value

```python
@property
def ebd_word_value() -> int
```

The word at the same location in the essential bits file.

<a id="skraft.datatypes.FpgaScrubWordSummary.msd_word_value"></a>

#### msd\_word\_value

```python
@property
def msd_word_value() -> int
```

The word at the same location in the readback mask file.

<a id="skraft.datatypes.FpgaScrubWordSummary.is_essential"></a>

#### is\_essential

```python
@property
def is_essential() -> bool
```

True if the affected bit is essential.

<a id="skraft.datatypes.FpgaScrubSummary"></a>

## FpgaScrubSummary Objects

```python
class FpgaScrubSummary()
```

The result of one scrub cycle in a scrubbing session.

**Attributes**:

- `scrub_cycle` _int_ - The scrub cycle that this summary describes.
- `correction_time_ms` _int_ - The time spent correcting upsets, in
  milliseconds.
- `idle_time_ms` _int_ - The idle time in the cycle, in milliseconds.
- `scrub_cycle_actual_duration_ms` _int_ - The measured duration of the
  cycle, in milliseconds.
- `word_summaries` _list[FpgaScrubWordSummary]_ - The details of each
  word that the cycle affected.

<a id="skraft.datatypes.FpgaScrubSummary.__init__"></a>

#### \_\_init\_\_

```python
def __init__(scrub_cycle: int, correction_time_ms: int, idle_time_ms: int,
             scrub_cycle_actual_duration_ms: int,
             word_summaries: list[FpgaScrubWordSummary])
```

Create a scrub cycle summary.

**Arguments**:

- `scrub_cycle` _int_ - The scrub cycle that this summary describes.
- `correction_time_ms` _int_ - The time spent correcting upsets, in
  milliseconds.
- `idle_time_ms` _int_ - The idle time in the cycle, in
  milliseconds.
- `scrub_cycle_actual_duration_ms` _int_ - The measured duration of
  the cycle, in milliseconds.
- `word_summaries` _list[FpgaScrubWordSummary]_ - The details of
  each affected word.

<a id="skraft.datatypes.FpgaScrubSummary.scrub_cycle"></a>

#### scrub\_cycle

```python
@property
def scrub_cycle() -> int
```

The scrub cycle that this summary describes.

<a id="skraft.datatypes.FpgaScrubSummary.correction_time_ms"></a>

#### correction\_time\_ms

```python
@property
def correction_time_ms() -> int
```

The time spent correcting upsets, in milliseconds.

<a id="skraft.datatypes.FpgaScrubSummary.idle_time_ms"></a>

#### idle\_time\_ms

```python
@property
def idle_time_ms() -> int
```

The idle time in the cycle, in milliseconds.

<a id="skraft.datatypes.FpgaScrubSummary.scrub_cycle_actual_duration_ms"></a>

#### scrub\_cycle\_actual\_duration\_ms

```python
@property
def scrub_cycle_actual_duration_ms() -> int
```

The measured duration of the cycle, in milliseconds.

<a id="skraft.datatypes.FpgaScrubSummary.word_summaries"></a>

#### word\_summaries

```python
@property
def word_summaries() -> list[FpgaScrubWordSummary]
```

The details of each word that the cycle affected.

<a id="skraft.datatypes.FpgaScrubReport"></a>

## FpgaScrubReport Objects

```python
class FpgaScrubReport()
```

The result of a completed scrubbing session.

Returned by FpgaDevice.scrub.

**Attributes**:

- `scrub_summaries` _list[FpgaScrubSummary]_ - One summary for each
  scrub cycle of the session.

<a id="skraft.datatypes.FpgaScrubReport.__init__"></a>

#### \_\_init\_\_

```python
def __init__(scrub_summaries: list[FpgaScrubSummary])
```

Create a scrubbing report.

**Arguments**:

- `scrub_summaries` _list[FpgaScrubSummary]_ - One summary for each
  scrub cycle.

<a id="skraft.datatypes.FpgaScrubReport.scrub_summaries"></a>

#### scrub\_summaries

```python
@property
def scrub_summaries() -> list[FpgaScrubSummary]
```

One summary for each scrub cycle of the session.

<a id="skraft.datatypes.FpgaFiSession"></a>

## FpgaFiSession Objects

```python
@dataclass
class FpgaFiSession()
```

The settings of a fault injection campaign defined by the user.

The shares of single bit, multiple bit and multiple cell upsets are
percentages and must add up to 100. A campaign can only target the
whole configuration memory or its essential bits, so storage element
targets are not accepted. Both rules are checked when the object is
created.

**Attributes**:

- `fault_type` _FaultType_ - The fault model of the campaign.
- `duration_ms` _int_ - How long the campaign runs, in milliseconds.
- `correction_time_ms` _int_ - The correction time, in milliseconds.
- `time_between_faults_ms` _int_ - The time between consecutive faults,
  in milliseconds.
- `sbu_percent` _float_ - The share of single bit upsets, in percent.
- `mbu_percent` _float_ - The share of multiple bit upsets, in percent.
- `mcu_percent` _float_ - The share of multiple cell upsets, in percent.
- `target` _TargetMemory_ - The memory to inject into. Either CRAM or
  ESSENTIAL_CRAM.
- `correct` _bool_ - If True, injected faults are corrected.
- `essential` _bool_ - True if the campaign targets only essential bits.
  Worked out from target.

<a id="skraft.datatypes.FpgaFiSession.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__() -> None
```

Check the campaign settings after the object is created.

**Raises**:

- `ValueError` - If the upset shares do not add up to 100, or if the
  target is not CRAM or ESSENTIAL_CRAM.

<a id="skraft.datatypes.FpgaFiSession.essential"></a>

#### essential

```python
@property
def essential() -> bool
```

True if the campaign targets only essential bits.

<a id="skraft.datatypes.FpgaFiWordSummary"></a>

## FpgaFiWordSummary Objects

```python
class FpgaFiWordSummary()
```

The details of one word that a campaign affected.

**Attributes**:

- `far` _int_ - The frame address of the injected frame.
- `word_index` _int_ - The index of the injected word.
- `bit_index` _int_ - The index of the injected bit.
- `golden_word_value` _int_ - The value of the word before the
  injection.
- `injected_word_value` _int_ - The value of the word after the
  injection.
- `is_essential` _bool_ - True if the injected bit is essential.

<a id="skraft.datatypes.FpgaFiWordSummary.__init__"></a>

#### \_\_init\_\_

```python
def __init__(far: int, word_index: int, bit_index: int, golden_word_value: int,
             injected_word_value: int, is_essential: bool)
```

Create a word summary.

**Arguments**:

- `far` _int_ - The frame address of the injected frame.
- `word_index` _int_ - The index of the injected word.
- `bit_index` _int_ - The index of the injected bit.
- `golden_word_value` _int_ - The value before the injection.
- `injected_word_value` _int_ - The value after the injection.
- `is_essential` _bool_ - True if the injected bit is essential.

<a id="skraft.datatypes.FpgaFiWordSummary.far"></a>

#### far

```python
@property
def far() -> int
```

The frame address of the injected frame.

<a id="skraft.datatypes.FpgaFiWordSummary.word_index"></a>

#### word\_index

```python
@property
def word_index() -> int
```

The index of the injected word.

<a id="skraft.datatypes.FpgaFiWordSummary.bit_index"></a>

#### bit\_index

```python
@property
def bit_index() -> int
```

The index of the injected bit.

<a id="skraft.datatypes.FpgaFiWordSummary.golden_word_value"></a>

#### golden\_word\_value

```python
@property
def golden_word_value() -> int
```

The value of the word before the injection.

<a id="skraft.datatypes.FpgaFiWordSummary.injected_word_value"></a>

#### injected\_word\_value

```python
@property
def injected_word_value() -> int
```

The value of the word after the injection.

<a id="skraft.datatypes.FpgaFiWordSummary.is_essential"></a>

#### is\_essential

```python
@property
def is_essential() -> bool
```

True if the injected bit is essential.

<a id="skraft.datatypes.FpgaFiSummary"></a>

## FpgaFiSummary Objects

```python
class FpgaFiSummary()
```

The result of a completed fault injection campaign.

The server only returns the list of affected words, so the number of
injected and corrected faults is worked out on the client. If the server
starts reporting these counts, they should be used instead.

**Attributes**:

- `session` _FpgaFiSession_ - The settings that the campaign used.
- `faults_injected` _int_ - The total number of injected faults.
- `corrected` _int_ - The number of injected faults that were corrected.
- `affected_words` _list[FpgaFiWordSummary]_ - The details of each
  affected word.

<a id="skraft.datatypes.FpgaFiSummary.__init__"></a>

#### \_\_init\_\_

```python
def __init__(session: FpgaFiSession, faults_injected: int, corrected: int,
             affected_words: list[FpgaFiWordSummary])
```

Create a campaign summary.

**Arguments**:

- `session` _FpgaFiSession_ - The settings that the campaign used.
- `faults_injected` _int_ - The total number of injected faults.
- `corrected` _int_ - The number of faults that were corrected.
- `affected_words` _list[FpgaFiWordSummary]_ - The details of each
  affected word.

<a id="skraft.datatypes.FpgaFiSummary.session"></a>

#### session

```python
@property
def session() -> FpgaFiSession
```

The settings that the campaign used.

<a id="skraft.datatypes.FpgaFiSummary.faults_injected"></a>

#### faults\_injected

```python
@property
def faults_injected() -> int
```

The total number of injected faults.

<a id="skraft.datatypes.FpgaFiSummary.corrected"></a>

#### corrected

```python
@property
def corrected() -> int
```

The number of injected faults that were corrected.

<a id="skraft.datatypes.FpgaFiSummary.affected_words"></a>

#### affected\_words

```python
@property
def affected_words() -> list[FpgaFiWordSummary]
```

The details of each affected word.

<a id="skraft.datatypes.XadcSensorSelector"></a>

## XadcSensorSelector Objects

```python
class XadcSensorSelector()
```

An XADC sensor of the device, for FpgaDevice.xadc.

The library defines a selector for each known sensor, for example VCCINT
or TEMPERATURE, so selectors are not normally created by hand.

**Attributes**:

- `addr` _int_ - The DRP address of the status register of the sensor.

<a id="skraft.datatypes.XadcSensorSelector.__init__"></a>

#### \_\_init\_\_

```python
def __init__(addr: int)
```

Create a sensor selector.

**Arguments**:

- `addr` _int_ - The DRP address of the status register of the
  sensor.

<a id="skraft.datatypes.XadcSensorSelector.addr"></a>

#### addr

```python
@property
def addr() -> int
```

The DRP address of the status register of the sensor.

<a id="skraft.datatypes.XadcSensor"></a>

## XadcSensor Objects

```python
class XadcSensor()
```

The value of an XADC sensor, as read by FpgaDevice.xadc.

The value is in units of the International System of Units (SI): volts
(V) for voltages and degrees Celsius (degC) for temperatures.

**Attributes**:

- `addr` _int_ - The DRP address of the status register that was read.
- `value` _float_ - The value of the sensor, in V or degC.

<a id="skraft.datatypes.XadcSensor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(addr: int, value: float)
```

Create a sensor value.

**Arguments**:

- `addr` _int_ - The DRP address of the status register that was
  read.
- `value` _float_ - The value of the sensor, in V or degC.

<a id="skraft.datatypes.XadcSensor.addr"></a>

#### addr

```python
@property
def addr() -> int
```

The DRP address of the status register that was read.

<a id="skraft.datatypes.XadcSensor.value"></a>

#### value

```python
@property
def value() -> float
```

The value of the sensor, in V or degC.

<a id="skraft.datatypes.TEMPERATURE"></a>

#### TEMPERATURE

degC

<a id="skraft.datatypes.VCCINT"></a>

#### VCCINT

V

<a id="skraft.datatypes.VCCAUX"></a>

#### VCCAUX

V

<a id="skraft.datatypes.VREFP"></a>

#### VREFP

V

<a id="skraft.datatypes.VREFN"></a>

#### VREFN

V

<a id="skraft.datatypes.VCCBRAM"></a>

#### VCCBRAM

V

<a id="skraft.datatypes.VCCPINT"></a>

#### VCCPINT

V

<a id="skraft.datatypes.VCCPAUX"></a>

#### VCCPAUX

V

<a id="skraft.datatypes.VCCO_DDR"></a>

#### VCCO\_DDR

V

<a id="skraft.datatypes.MAX_TEMPERATURE"></a>

#### MAX\_TEMPERATURE

degC

<a id="skraft.datatypes.MAX_VCCINT"></a>

#### MAX\_VCCINT

V

<a id="skraft.datatypes.MAX_VCCAUX"></a>

#### MAX\_VCCAUX

V

<a id="skraft.datatypes.MAX_VCCBRAM"></a>

#### MAX\_VCCBRAM

V

<a id="skraft.datatypes.MIN_TEMPERATURE"></a>

#### MIN\_TEMPERATURE

degC

<a id="skraft.datatypes.MIN_VCCINT"></a>

#### MIN\_VCCINT

V

<a id="skraft.datatypes.MIN_VCCAUX"></a>

#### MIN\_VCCAUX

V

<a id="skraft.datatypes.MIN_VCCBRAM"></a>

#### MIN\_VCCBRAM

V

<a id="skraft.datatypes.MAX_VCCPINT"></a>

#### MAX\_VCCPINT

V

<a id="skraft.datatypes.MAX_VCCPAUX"></a>

#### MAX\_VCCPAUX

V

<a id="skraft.datatypes.MAX_VCCO_DDR"></a>

#### MAX\_VCCO\_DDR

V

<a id="skraft.datatypes.MIN_VCCPINT"></a>

#### MIN\_VCCPINT

V

<a id="skraft.datatypes.MIN_VCCPAUX"></a>

#### MIN\_VCCPAUX

V

<a id="skraft.datatypes.MIN_VCCO_DDR"></a>

#### MIN\_VCCO\_DDR

V

<a id="skraft.datatypes.XadcAlarmSelector"></a>

## XadcAlarmSelector Objects

```python
class XadcAlarmSelector()
```

An XADC alarm threshold of the device, for FpgaDevice.xadc_alarm and
FpgaDevice.set_xadc_alarm.

The library defines a selector for each alarm register, for example
TEMPERATURE_UPPER or VCCINT_LOWER, so selectors are not normally created
by hand.

**Attributes**:

- `addr` _int_ - The DRP address of the alarm register.

<a id="skraft.datatypes.XadcAlarmSelector.__init__"></a>

#### \_\_init\_\_

```python
def __init__(addr: int)
```

Create an alarm selector.

**Arguments**:

- `addr` _int_ - The DRP address of the alarm register.

<a id="skraft.datatypes.XadcAlarmSelector.addr"></a>

#### addr

```python
@property
def addr() -> int
```

The DRP address of the alarm register.

<a id="skraft.datatypes.XadcAlarm"></a>

## XadcAlarm Objects

```python
class XadcAlarm()
```

The threshold of an XADC alarm, as read by FpgaDevice.xadc_alarm.

The value is in units of the International System of Units (SI): volts
(V) for voltages and degrees Celsius (degC) for temperatures.

**Attributes**:

- `addr` _int_ - The DRP address of the alarm register that was read.
- `value` _float_ - The threshold, in V or degC.

<a id="skraft.datatypes.XadcAlarm.__init__"></a>

#### \_\_init\_\_

```python
def __init__(addr: int, value: float)
```

Create an alarm threshold.

**Arguments**:

- `addr` _int_ - The DRP address of the alarm register that was
  read.
- `value` _float_ - The threshold, in V or degC.

<a id="skraft.datatypes.XadcAlarm.addr"></a>

#### addr

```python
@property
def addr() -> int
```

The DRP address of the alarm register that was read.

<a id="skraft.datatypes.XadcAlarm.value"></a>

#### value

```python
@property
def value() -> float
```

The threshold, in V or degC.

<a id="skraft.datatypes.TEMPERATURE_UPPER"></a>

#### TEMPERATURE\_UPPER

degC

<a id="skraft.datatypes.TEMPERATURE_LOWER"></a>

#### TEMPERATURE\_LOWER

degC

<a id="skraft.datatypes.OT_LIMIT"></a>

#### OT\_LIMIT

degC

<a id="skraft.datatypes.OT_RESET"></a>

#### OT\_RESET

degC

<a id="skraft.datatypes.VCCINT_UPPER"></a>

#### VCCINT\_UPPER

V

<a id="skraft.datatypes.VCCINT_LOWER"></a>

#### VCCINT\_LOWER

V

<a id="skraft.datatypes.VCCAUX_UPPER"></a>

#### VCCAUX\_UPPER

V

<a id="skraft.datatypes.VCCAUX_LOWER"></a>

#### VCCAUX\_LOWER

V

<a id="skraft.datatypes.VCCBRAM_UPPER"></a>

#### VCCBRAM\_UPPER

V

<a id="skraft.datatypes.VCCBRAM_LOWER"></a>

#### VCCBRAM\_LOWER

V

<a id="skraft.datatypes.VCCPINT_UPPER"></a>

#### VCCPINT\_UPPER

V

<a id="skraft.datatypes.VCCPINT_LOWER"></a>

#### VCCPINT\_LOWER

V

<a id="skraft.datatypes.VCCPAUX_UPPER"></a>

#### VCCPAUX\_UPPER

V

<a id="skraft.datatypes.VCCPAUX_LOWER"></a>

#### VCCPAUX\_LOWER

V

<a id="skraft.datatypes.VCCO_DDR_UPPER"></a>

#### VCCO\_DDR\_UPPER

V

<a id="skraft.datatypes.VCCO_DDR_LOWER"></a>

#### VCCO\_DDR\_LOWER

V

<a id="skraft.datatypes.XadcFlags"></a>

## XadcFlags Objects

```python
class XadcFlags()
```

The state of the XADC alarms and of the JTAG access, as read by
FpgaDevice.xadc_flags from the flag register (3Fh).

An alarm attribute is True while the alarm is on. In the default mode
of the sequencer, the XADC disables all the alarms, except the
over-temperature alarm (UG480 and UG580, Sequencer Modes). In Zynq
UltraScale+ MPSoCs, vccpint, vccpaux and vcco_ddr are the alarms of
VCC_PSINTLP, VCC_PSINTFP and VCC_PSAUX.

**Attributes**:

- `temperature` _bool_ - The temperature alarm (ALM0) is on.
- `vccint` _bool_ - The VCCINT alarm (ALM1) is on.
- `vccaux` _bool_ - The VCCAUX alarm (ALM2) is on.
- `over_temperature` _bool_ - The over-temperature alarm (OT) is on.
- `vccbram` _bool_ - The VCCBRAM alarm (ALM3) is on.
- `vccpint` _bool_ - The VCCPINT alarm (ALM4) is on, Zynq-7000 only.
- `vccpaux` _bool_ - The VCCPAUX alarm (ALM5) is on, Zynq-7000 only.
- `vcco_ddr` _bool_ - The VCCO_DDR alarm (ALM6) is on, Zynq-7000 only.
- `internal_reference` _bool_ - The ADC uses the on-chip reference
  (REF).
- `jtag_read_only` _bool_ - The design allows only reads of the XADC
  through JTAG (JTGR).
- `jtag_disabled` _bool_ - The design disables the JTAG access to the
  XADC (JTGD).

<a id="skraft.datatypes.XadcFlags.__init__"></a>

#### \_\_init\_\_

```python
def __init__(temperature: bool, vccint: bool, vccaux: bool,
             over_temperature: bool, vccbram: bool, vccpint: bool,
             vccpaux: bool, vcco_ddr: bool, internal_reference: bool,
             jtag_read_only: bool, jtag_disabled: bool)
```

Create the state of the XADC flags.

**Arguments**:

- `temperature` _bool_ - The temperature alarm (ALM0) is on.
- `vccint` _bool_ - The VCCINT alarm (ALM1) is on.
- `vccaux` _bool_ - The VCCAUX alarm (ALM2) is on.
- `over_temperature` _bool_ - The over-temperature alarm (OT) is on.
- `vccbram` _bool_ - The VCCBRAM alarm (ALM3) is on.
- `vccpint` _bool_ - The VCCPINT alarm (ALM4) is on.
- `vccpaux` _bool_ - The VCCPAUX alarm (ALM5) is on.
- `vcco_ddr` _bool_ - The VCCO_DDR alarm (ALM6) is on.
- `internal_reference` _bool_ - The ADC uses the on-chip reference.
- `jtag_read_only` _bool_ - The design allows only reads of the
  XADC through JTAG.
- `jtag_disabled` _bool_ - The design disables the JTAG access to
  the XADC.

<a id="skraft.datatypes.XadcFlags.temperature"></a>

#### temperature

```python
@property
def temperature() -> bool
```

The temperature alarm (ALM0) is on.

<a id="skraft.datatypes.XadcFlags.vccint"></a>

#### vccint

```python
@property
def vccint() -> bool
```

The VCCINT alarm (ALM1) is on.

<a id="skraft.datatypes.XadcFlags.vccaux"></a>

#### vccaux

```python
@property
def vccaux() -> bool
```

The VCCAUX alarm (ALM2) is on.

<a id="skraft.datatypes.XadcFlags.over_temperature"></a>

#### over\_temperature

```python
@property
def over_temperature() -> bool
```

The over-temperature alarm (OT) is on.

<a id="skraft.datatypes.XadcFlags.vccbram"></a>

#### vccbram

```python
@property
def vccbram() -> bool
```

The VCCBRAM alarm (ALM3) is on.

<a id="skraft.datatypes.XadcFlags.vccpint"></a>

#### vccpint

```python
@property
def vccpint() -> bool
```

The VCCPINT alarm (ALM4) is on, Zynq-7000 only.

<a id="skraft.datatypes.XadcFlags.vccpaux"></a>

#### vccpaux

```python
@property
def vccpaux() -> bool
```

The VCCPAUX alarm (ALM5) is on, Zynq-7000 only.

<a id="skraft.datatypes.XadcFlags.vcco_ddr"></a>

#### vcco\_ddr

```python
@property
def vcco_ddr() -> bool
```

The VCCO_DDR alarm (ALM6) is on, Zynq-7000 only.

<a id="skraft.datatypes.XadcFlags.internal_reference"></a>

#### internal\_reference

```python
@property
def internal_reference() -> bool
```

The ADC uses the on-chip reference (REF).

<a id="skraft.datatypes.XadcFlags.jtag_read_only"></a>

#### jtag\_read\_only

```python
@property
def jtag_read_only() -> bool
```

The design allows only reads of the XADC through JTAG (JTGR).

<a id="skraft.datatypes.XadcFlags.jtag_disabled"></a>

#### jtag\_disabled

```python
@property
def jtag_disabled() -> bool
```

The design disables the JTAG access to the XADC (JTGD).

<a id="skraft.datatypes.XadcRegister"></a>

## XadcRegister Objects

```python
class XadcRegister(int, Enum)
```

The XADC registers, at their DRP addresses, for
FpgaDevice.read_xadc_register and FpgaDevice.write_xadc_register.

Only the flag register, the configuration registers and the alarm
registers are accessible. The flag register is read only. The values are
raw 16-bit contents. UG480 (Status Registers, Control Registers) gives the
meaning of each bit, and the ADC transfer functions give the codes of the
alarm thresholds. The thresholds of the Processing System (PS) supplies
exist only in Zynq-7000 SoCs. FpgaDevice.xadc_alarm and
FpgaDevice.set_xadc_alarm give the thresholds in SI units, and
FpgaDevice.xadc_flags decodes the flag register.

The flag register shows the state of the alarms. Bit 0 is ALM0
(temperature), bit 1 is ALM1 (VCCINT), bit 2 is ALM2 (VCCAUX), bit 3 is
OT (over-temperature), bit 4 is ALM3 (VCCBRAM), and bits 5 to 7 are ALM4
to ALM6 (VCCPINT, VCCPAUX, VCCO_DDR). In the default sequencer mode
(CONFIG1), only OT operates. Bits 9 to 11 are REF, JTGR and JTGD.

Caution: the four least significant bits of ALARM3 select the automatic
shutdown at the over-temperature (OT) limit. The value 0011b enables it.

**Attributes**:

- `FLAG` _XadcRegister_ - Flag register (3Fh), read only.
- `CONFIG0` _XadcRegister_ - Configuration register 0 (40h).
- `CONFIG1` _XadcRegister_ - Configuration register 1 (41h).
- `CONFIG2` _XadcRegister_ - Configuration register 2 (42h).
- `ALARM0` _XadcRegister_ - Temperature upper threshold (50h).
- `ALARM1` _XadcRegister_ - VCCINT upper threshold (51h).
- `ALARM2` _XadcRegister_ - VCCAUX upper threshold (52h).
- `ALARM3` _XadcRegister_ - Over-temperature (OT) limit (53h).
- `ALARM4` _XadcRegister_ - Temperature lower threshold (54h).
- `ALARM5` _XadcRegister_ - VCCINT lower threshold (55h).
- `ALARM6` _XadcRegister_ - VCCAUX lower threshold (56h).
- `ALARM7` _XadcRegister_ - Over-temperature (OT) reset (57h).
- `ALARM8` _XadcRegister_ - VCCBRAM upper threshold (58h).
- `ALARM9` _XadcRegister_ - VCCPINT upper threshold (59h), Zynq-7000
  only.
- `ALARM10` _XadcRegister_ - VCCPAUX upper threshold (5Ah), Zynq-7000
  only.
- `ALARM11` _XadcRegister_ - VCCO_DDR upper threshold (5Bh), Zynq-7000
  only.
- `ALARM12` _XadcRegister_ - VCCBRAM lower threshold (5Ch).
- `ALARM13` _XadcRegister_ - VCCPINT lower threshold (5Dh), Zynq-7000
  only.
- `ALARM14` _XadcRegister_ - VCCPAUX lower threshold (5Eh), Zynq-7000
  only.
- `ALARM15` _XadcRegister_ - VCCO_DDR lower threshold (5Fh), Zynq-7000
  only.

<a id="skraft.exceptions"></a>

# skraft.exceptions

Typed exception hierarchy for the SK-RAFT client.

All errors that the client raises derive from :class:`SkraftError`. Thus,
callers can catch all of these errors with one ``except``, or handle specific
failures.

<a id="skraft.exceptions.SkraftError"></a>

## SkraftError Objects

```python
class SkraftError(Exception)
```

The base class for all errors that the SK-RAFT client raises.

<a id="skraft.exceptions.ConnectionFailedError"></a>

## ConnectionFailedError Objects

```python
class ConnectionFailedError(SkraftError)
```

The connection to the SK-RAFT server failed, or the communication with
the server stopped during an operation.

<a id="skraft.exceptions.DeviceReservationError"></a>

## DeviceReservationError Objects

```python
class DeviceReservationError(SkraftError)
```

The reservation of a target FPGA device failed. The device is not
available through the selected programmer, or another process (for
example, Vivado) uses the device.

<a id="skraft.exceptions.DesignFileError"></a>

## DesignFileError Objects

```python
class DesignFileError(SkraftError)
```

A design file that the requested operation must have is not loaded, or
the read or upload of a design file failed.

<a id="skraft.exceptions.FrameAddressError"></a>

## FrameAddressError Objects

```python
class FrameAddressError(SkraftError)
```

A frame address (FAR) is out of range or is not valid.

<a id="skraft.exceptions.BscanError"></a>

## BscanError Objects

```python
class BscanError(SkraftError)
```

A boundary-scan (BSCAN) operation failed.

<a id="skraft.exceptions.XadcError"></a>

## XadcError Objects

```python
class XadcError(SkraftError)
```

The read of an XADC sensor failed.

