# Example 4: BRAM content injection and ECC recovery

This example injects upsets into the content of one BRAM. Then it shows which words read back wrong, and which of them an error-correcting code (ECC) in the design repairs:

- One flipped bit in a byte: the ECC corrects it.
- Two or more flipped bits in the same byte: the ECC cannot correct them, and it can also change a correct bit.

## Design

![Block diagram of brams_top. A BRAM in a pblock has an encoder on the write path. On the read path, a falling-edge hold register on the gated clock feeds a decoder and a multiplexer. USER1 controls the clock gate, USER2 selects the address, USER3 carries the data and USER4 enables the ECC correction.](images/example4_brams_top_abstract.svg)

The design [`brams_top`](../hw/sources_1/new/brams_top.vhd) has one BRAM (a RAMB36), `soft_sec_bram`, in the pblock `pblock_soft_sec_bram`. The BRAM has 1024 words of 36 bits:

| Bits of a word | Contents |
| --- | --- |
| 23:0 | 3 data bytes |
| 35:24 | 12 check bits: 4 for each data byte |

The ECC is a Hamming SEC (single error correction) code for each byte, in the fabric around the BRAM:

- **Write:** an encoder calculates the 4 check bits of each data byte. The BRAM stores the data bytes and their check bits.
- **Read:** a decoder checks each byte with its 4 check bits. If one of these 12 bits is flipped, the decoder corrects it.
- **USER4** selects what the script reads: the raw data (correction off) or the corrected data (correction on).

The ECC is in the fabric because the built-in ECC of the BRAM does not see an SK-RAFT injection. [Example 6](../example6/README.md) explains why.

The script controls the design through four BSCAN registers:

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | write | The clock enable of the BRAM. The script stops the clock during each injection. |
| USER2 | 16 bits | write | The address. Only the low 10 bits have an effect. |
| USER3 | 24 bits | write and read | The data at the address. A write of USER3 writes the word. A read of USER3 reads the word, and does not write it (refer to [`auxiliary_components/bscan`](../../auxiliary_components/bscan/README.md)). |
| USER4 | 1 bit | write | The ECC correction: 1 = on, 0 = off. It applies to the read path only. The reset value is 0. |

## What the script does

1. It programs the FPGA and starts the clock of the BRAM.
2. It writes a known word to each of the 1024 addresses: `0xA5A5A5` XOR the address. Then it reads all the words back with the correction off. If a word is wrong, the script stops and does not inject.
3. It injects one upset each 0.3 s into a random content bit of the BRAM (`TargetMemory.BRAM`), until you press Enter. It stops the clock of the BRAM before each injection, and starts it again after the injection. The upsets add up, and the script does not correct them.
4. It reads all the words with the correction off, then with the correction on. Each time, it prints the wrong words.
5. It programs the FPGA again, to clear the upsets.

Press Enter early to see the ECC correct each word. Let the injection continue for a longer time to see bytes with two or more flipped bits, which the ECC cannot correct.

## Run the example

You need:

- Python 3.9 or a later version, with the `skraft` package installed.
- An SK-RAFT server in operation, with the target board connected through USB.
- The bitstream, the LL file and the XDC file of `brams_top` in `hw/design_examples/<board>/brams_top/`. Use the prebuilt files in `design_examples.zip`, or build them with `hw/create_project.tcl`. Refer to [Prebuilt design files](../README.md#prebuilt-design-files) and [Build a design](../README.md#build-a-design).

Set these constants at the top of `src/main.py`:

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` | `127.0.0.1` | The address of the SK-RAFT server. |
| `BOARD` | `basys3` | Your board: `basys3` or `zedboard`. |
| `ADDRESS_BITS` | `10` | The address width that has an effect: 1024 words. |

The script attaches to the first board that the server lists. Connect only the target board to the server. Then run the script:

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

How to read the output:

- **The upset lines** give the location of each injected bit: the frame address (FAR), the word in the frame and the bit in the word. `BLK_TYPE` is the block type of the frame: always 1, a BRAM content frame. `BRAM Content bit count` is 36864: 1024 words x 36 bits.
- **The wrong words** give the address (`ADDR`), the written word (`EXPECTED`), the word that the script read (`READ`) and the positions of the bits that differ (`FAULTY BITS`, 0 = the least significant bit).
- **Compare the two reads** to see what the ECC did with each word:

| Correction off | Correction on | Meaning |
| --- | --- | --- |
| Wrong | Correct | Each byte of the word had at most one flipped bit. The ECC corrected it. |
| Wrong | Wrong | A byte had two or more flipped bits. The ECC cannot correct them. |
| Correct | Wrong | The flips were in the check bits. The ECC changed a correct data bit. |
| Correct | Correct | No data bit is flipped. One flipped check bit does not show with the correction off, and the ECC hides it with the correction on. |

In the sample, the 13 wrong words each had one flipped bit, and the ECC corrected all of them.

## Background

### The configuration frames of the BRAM also affect it

The block type field of the frame address (FAR) tells the kind of a frame. The BRAM column has frames of two block types:

| Block type | Frames | What they hold |
| --- | --- | --- |
| 0 | Configuration (CLB, I/O, CLK) | The configuration of the BRAM, for example its width and its output register, and the interconnect of the column. |
| 1 | BRAM content | The data bits and the parity bits of the BRAMs. |

The script injects only into the block type 1 frames. An upset in the block type 0 frames of the column can also change the BRAM: it can change how the BRAM operates, stop it, or break a route to or from it. Thus, to test a design that uses BRAMs, also inject into the essential bits of the BRAM column (`TargetMemory.ESSENTIAL_CRAM` with `pblock=`), as [example 1](../example1/README.md) does for its pblocks.

AMD defines the block types in the description of the frame address register (FAR):

- UG470, *7 Series FPGAs Configuration User Guide*, section "Frame Address Register (FAR)".
- UG570, *UltraScale Architecture Configuration User Guide*, section "Frame Address Register (FAR)".

### The hold register

The design reads the BRAM through a hold register. `hw/create_project.tcl` adds it with the BRAM hold register pass ([`auxiliary_components/bram_hold_pass`](../../auxiliary_components/bram_hold_pass/README.md)), and the build prints the report of the pass. Without the hold register, each injection into the BRAM content would also change the BRAM output, and the design could read a wrong word after the clock starts again. Thus a wrong word in the results comes from the injected content, not from the test setup. [Example 6](../example6/README.md) explains why, and shows the effect on a BRAM without a hold register.

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
