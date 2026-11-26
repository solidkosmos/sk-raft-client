# Example 4: BRAM content injection and ECC recovery

The design uses one RAMB36 in the 1K x 36 configuration. Each 36-bit word contains 24 data bits and 12 check bits. Logic in the fabric around the BRAM protects each data byte with its own Hamming SEC code (4 check bits for each byte). This logic is not the built-in ECC of the BRAM.

![Block diagram of brams_top. A BRAM in a pblock has an encoder on the write path. On the read path, a falling-edge hold register on the gated clock feeds a decoder and a multiplexer. USER1 controls the clock gate, USER2 selects the address, USER3 carries the data and USER4 enables the ECC correction.](images/example4_brams_top_abstract.svg)

## Sequence

1. The script fills the memory. Then it reads back each word to make sure that the data is correct.
2. The script injects content upsets (`TargetMemory.BRAM`) into the block type 1 frames of the BRAM. The upsets add up, and the script does not correct them.
3. The script reads back the full memory two times: first with ECC off, then with ECC on.
4. The script programs the FPGA again, to clear the upsets.

The script injects one upset each 0.3 s until you press Enter. When the injection continues for a longer time, more bytes get two or more flips. The SEC code cannot correct these bytes.

## The configuration frames of the BRAM also affect it

The block type field of the frame address (FAR) tells the kind of a frame. The BRAM column has frames of two block types:

| Block type | Frames | What they hold |
| --- | --- | --- |
| 0 | Configuration (CLB, I/O, CLK) | The configuration of the BRAM, for example its width and its output register, and the interconnect of the column. |
| 1 | BRAM content | The data bits and the parity bits of the BRAMs. |

The script injects only into the block type 1 frames. An upset in the block type 0 frames of the column can also change the BRAM: it can change how the BRAM operates, stop it, or break a route to or from it. Thus, to test a design that uses BRAMs, also inject into the essential bits of the BRAM column (`TargetMemory.ESSENTIAL_CRAM` with `pblock=`), as [example 1](../example1/README.md) does for its pblocks.

AMD defines the block types in the description of the frame address register (FAR):

- UG470, *7 Series FPGAs Configuration User Guide*, section "Frame Address Register (FAR)".
- UG570, *UltraScale Architecture Configuration User Guide*, section "Frame Address Register (FAR)".

## BRAM output latch and the hold register

When SK-RAFT reads or writes BRAM content frames (the script injects into them), the output latch of `soft_sec_bram` takes a value from the configuration frame. The content of the BRAM does not change. The BRAM has no output register (`DO_REG = 0`), so without protection the design can take that wrong value instead of the word it read before the freeze.

`hw/create_project.tcl` builds `brams_top` with the BRAM hold register pass ([`auxiliary_components/bram_hold_pass`](../../auxiliary_components/bram_hold_pass/README.md)). The pass adds a falling-edge register behind the BRAM output, which keeps the word read before the freeze. Thus a wrong word in the results comes from the injected content, not from the latch. The build prints the report of the pass.

[`readback_writeback/`](readback_writeback/README.md) shows the effect without the pass, on a BRAM with the built-in ECC: the wrong word while the clock is stopped, and the flipped bit that the ECC does not detect.

## BSCAN register map

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | write | BRAM clock enable (the script stops the clock during each injection) |
| USER2 | 16 bits | write | Address select (only the low 10 bits have an effect) |
| USER3 | 24 bits | read/write (check auxiliary_components/bscan/bscan_user_register_io.vhd to see how reads are performed) | The data at the selected address |
| USER4 | 1 bit | write | ECC correction enable. It applies to the BRAM read path only. The reset value is 0. |

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.get_devices()`, `client.attach(serial_number)` | Connect to the SK-RAFT server, select the first board that the server lists and attach to it, in `with` statements that release the device and close the connection. |
| `Design(bit, ll, xdc)`, `dev.upload_design_to_server(design)`, `dev.program_fpga(design)` | Give the design files, upload them to the server and program the FPGA. |
| `dev.configure_seed(0)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `BscanPrimitive(user, length)`, `dev.write_bscan(primitive, value)`, `dev.read_bscan(primitive)` | Start and stop the clock (USER1), select the address (USER2), write and read the data (USER3), and enable the ECC correction (USER4). |
| `dev.bit_count(TargetMemory.BRAM, pblock=PBLOCK_BRAM)` | Get the number of content bits of the BRAM pblock. |
| `dev.inject_random(TargetMemory.BRAM, pblock=PBLOCK_BRAM)` | Inject one upset into a random content bit of the BRAM. |
| `dev.decode_far(far)` | Get the block type of the frame of each upset (1: BRAM content). |

## Requirements

- Python 3.9 or a later version, with the `skraft` package installed.
- An SK-RAFT server in operation, with the target board connected through USB.
- The bitstream, the LL file and the XDC file that declares `pblock_soft_sec_bram`. The script uploads these files to the server. Use the prebuilt files in `design_examples.zip`, or build them with `hw/create_project.tcl`. Both include the BRAM hold register pass.

## Configuration

| Constant | Default | Description |
| --- | --- | --- |
| `ADDRESS_BITS` | `10` | The address width that has an effect: 1024 words. |

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/brams_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`. The script attaches to the first board that the server lists. Connect only the target board to the server.
3. Run the script:

```bash
cd src
python main.py
```

## Result

Sample output of a run on a Basys 3 (shortened). The frame addresses, the bit counts and the error counts depend on the board, the build and the seed.

```
Example 4: BRAM content injection and ECC recovery
SK-RAFT client 1.0.0, server 1.0.3
Programmed 210183BA2524A.
Writing known words in the BRAM...
Wrote 1024 words into pblock_soft_sec_bram.
Checking if all words round-trip...
All 1024 addresses read back correctly.
BRAM Content bit count = 36864
Press enter to stop injecting
Injecting BRAM Content bit upsets into pblock_soft_sec_bram, none corrected.
     #  FAR       WORD  BIT  BLK_TYPE
     1  00c00055    63   26    1
     2  00c00020    61   18    1
...
Injected 20 BRAM Content faults.
Reading the whole memory with ECC read off.
ECC off: 13 of 1024 addresses wrong.
  ADDR  EXPECTED                  READ                      FAULTY BITS
   104  101001011010010111001101  101001011010010110001101  6
   129  101001011010010100100100  101001111010010100100100  17
...
13 words wrong, 13 faulty bits in total.
--------------------------------------------------------------------------------
Reading the whole memory again with ECC read on.
ECC on: 0 of 1024 addresses wrong.
ECC on: every word read back correctly. Single flips were corrected; flips in check bits were masked.
Re-programming to clear the device.
Example 4 done.
```

If the first write and read-back pass finds incorrect data, the script stops. It does not inject faults in that case.

After each read-back, the script prints each incorrect word with these data:

- The expected data bits.
- The data bits that it read.
- The positions of the incorrect bits.

The main result is the number of incorrect addresses with ECC off and with ECC on:

- A word that is incorrect only with ECC off had single flips. The SEC code corrected them.
- A word that is incorrect with ECC on had two or more flips in one byte. The SEC code cannot correct these flips, and it can also make an incorrect correction.
- A flip in a check bit does not show with ECC off. With ECC on, the SEC code hides a single flip in a check bit.

The script does not correct the faults. At the end, it programs the FPGA again to clear them.
