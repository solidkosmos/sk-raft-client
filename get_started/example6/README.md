# Example 6: the BRAM port that SK-RAFT shares with your design

The designs of the other examples read their BRAMs through a hold register, and example 4 protects its BRAM data with an ECC in the fabric, not with the built-in ECC of the BRAM. This example shows why. It injects one bit into a BRAM that has no hold register and uses the built-in ECC, and it shows the two effects of the injection on the BRAM outputs.

## One BRAM, shared ports

A BRAM has shared ports between **the application layer** and **the configuration layer**:

- **The application layer:** your design. It writes and reads the BRAM through the BRAM ports: the address, the data input, the write enable and the data output `DO`.
- **The configuration layer:** the configuration logic of the FPGA. It writes and reads the BRAM content through the BRAM content frames (block type 1 in the frame address). SK-RAFT uses the configuration layer for each readback, injection and revert of a BRAM content frame.

The two layers use the **same write path** and the **same read path** of the BRAM. Thus, an access of the configuration layer also changes what the application layer sees.

![Block diagram of a BRAM with two users. The application layer and the configuration layer both write through the write path of the BRAM, which contains the ECC encoder. Both read through the read path, which contains the ECC decoder and the output latch. The output latch drives DO, which goes through a hold register to the design. The read path also gives the readback data to the configuration layer.](images/example6_bram_shared_port.svg)

## Effect 1: a configuration read changes the BRAM output

When the configuration layer reads a BRAM content frame, each BRAM with bits in that frame does a read. The output latch of the BRAM then holds the data of that read, not the word that your design read before the clock stopped. (Stop the clock of the design during each injection into the application memory: refer to rule 2 of the [general guidelines](../../docs/general_guidelines.md#2-stop-the-clock-during-application-memory-injection).) The stored content does not change.

- **The operations that cause it:** each readback of a BRAM content frame (with or without capture), each injection into a BRAM (SK-RAFT reads the frame, flips the bit and writes the frame back) and each revert.
- **The BRAMs that it affects:** all the BRAMs that have bits in the frames that SK-RAFT reads. One content frame holds bits of more than one BRAM of the column. Thus an injection into one BRAM also changes the output of the other BRAMs in that frame.
- **What your design sees:** a BRAM without the output register (`DO_REG = 0`) drives `DO` directly from the output latch. While the clock is stopped, and after the clock starts until the BRAM reads again, `DO` shows the changed value. If your design uses `DO` in this time, it gets a word that it did not read. This is an error that the test setup makes, not an effect of the injected fault.

Stage 3 of this example shows effect 1.

## Effect 2: the built-in ECC does not see an injected bit

The ECC of a BRAM with `EN_ECC_WRITE = TRUE` and `EN_ECC_READ = TRUE` is part of the shared paths: the encoder is in the write path, and the decoder is in the read path.

When SK-RAFT writes the frame back with the flipped bit, the data goes through the ECC encoder of the BRAM. The encoder makes new parity bits for the changed data. Thus the stored word is a valid ECC word: its data and its parity bits agree. When the BRAM reads the word, the ECC decoder finds no error (`SBITERR = 0`) and does not correct the bit. The flipped bit is silent data corruption.

Stage 4 of this example shows effect 2. Two consequences:

- `TargetMemory.BRAM` injection does not test the built-in ECC of a BRAM.
- To test an ECC with SK-RAFT, put the ECC in the fabric, outside the BRAM, as [example 4](../example4/README.md) does. Its encoder is in the write path of your design only. The configuration layer writes the stored data and parity bits as they are, so the decoder in the fabric sees the injected bit.

## The fix for effect 1: a hold register

A hold register is a flip-flop behind `DO`, on the opposite clock edge of the BRAM: on the falling edge for a BRAM on the rising edge. It loads `DO` only in the half clock cycle directly after a read of your design. Your design uses the hold register, not `DO`.

1. The clock stops low (a BUFGCE). The last load of the hold register is the word that your design read before the clock stopped.
2. While the clock is stopped, SK-RAFT reads and writes the content frames, and the output latch changes. The hold register does not load, because it gets no clock edge.
3. When the clock starts, the BRAM reads first (rising edge). Then the hold register loads the new word (falling edge).

Thus your design never sees the changed output latch. The BRAM hold register pass adds the hold registers to your netlist. You do not change your source. Refer to [`auxiliary_components/bram_hold_pass`](../../auxiliary_components/bram_hold_pass/README.md) for the pass and its requirements, and to rule 3 of the [general guidelines](../../docs/general_guidelines.md). Example 4 builds its design with the pass.

A BRAM port with the output register (`DO_REG = 1`) needs no hold register: the output register keeps the word while the clock is stopped.

This example builds its design without the pass, to show effect 1.

## Design

`bram_readback_writeback_top` ([`hw/sources_1/new/bram_readback_writeback_top.vhd`](../hw/sources_1/new/bram_readback_writeback_top.vhd)) has one RAMB36 in simple dual-port mode, 512 x 72 (64 data bits and 8 ECC bits). The built-in ECC encoder makes the ECC bits on each write (`EN_ECC_WRITE = TRUE`). The built-in decoder checks each read (`EN_ECC_READ = TRUE`). The read port is always enabled, so the BRAM reads the word at the address on each clock edge. The BRAM outputs go directly to USER3, with no register in between.

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | write | Clock enable of the BRAM (a BUFGCE). 0 after programming. |
| USER2 | 16 bits | write | Address (only the low 9 bits have an effect). |
| USER3 | 80 bits | write | Bits 63:0 are written to the word at the address. |
| USER3 | 80 bits | read | Bits 63:0: data. Bits 71:64: ECC parity. Bit 72: `SBITERR`. |

The XDC excludes the BRAM from power optimization (`set_power_opt -exclude_cells`). Without it, `opt_design` gates the read enable, and the BRAM does not read again in stage 4.

## Stages

The script writes the address as the word: word 0 holds 0, word 1 holds 1, and so on. The script reads word 0 after each stage.

| Stage | Action | Result |
| --- | --- | --- |
| 1 | Start the clock, fill the BRAM, select word 0. | The word is correct, `SBITERR = 0`. |
| 2 | Stop the clock. | The word is still correct. The output latch holds the last read of the design. |
| 3 | Inject into word 0, bit 0 (`Ram=B:BIT0` in the LL file). The clock is still stopped. | A wrong word (effect 1). |
| 4 | Start the clock. | Bit 0 is flipped, `SBITERR = 0` (effect 2). |

**Stage 3.** To flip one bit, SK-RAFT reads the content frame, changes the bit and writes the frame back. The frame read goes through the read path of the BRAM and changes its output latch. The BRAM has no output register and no hold register, so USER3 shows the latch directly: the data, the parity and `SBITERR` are not the values of word 0.

**Stage 4.** The BRAM reads word 0 again, and the outputs are correct for the stored word. But the frame write went through the ECC encoder of the BRAM, which made new parity bits for the flipped data. Thus the decoder finds no error, and bit 0 stays flipped. In the sample output below, the parity of word 0 is `0x00` in stage 1 and `0x83` in stage 4: the parity bits changed together with the data bit.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.get_devices()`, `client.attach(serial_number)` | Connect to the SK-RAFT server, select the first board that the server lists and attach to it, in `with` statements that release the device and close the connection. |
| `Design(bit, ll)`, `dev.upload_design_to_server(design)`, `dev.program_fpga(design)` | Give the design files, upload them to the server and program the FPGA. |
| `BscanPrimitive(user, length)`, `dev.write_bscan(primitive, value)`, `dev.read_bscan(primitive)` | Start and stop the clock (USER1), select the address (USER2), write the words and read the BRAM outputs (USER3). |
| `dev.inject_at(far, word, bit, TargetMemory.BRAM)` | Stage 3: inject into word 0, bit 0. The script finds the location of the bit (`Ram=B:BIT0`) in the LL file. |

## Requirements

- Python 3.9 or a later version, with the `skraft` package installed.
- An SK-RAFT server in operation, with the target board connected through USB.
- The bitstream and the LL file of `bram_readback_writeback_top` in `hw/design_examples/<board>/bram_readback_writeback_top/`. Extract them from `design_examples.zip` (refer to [Prebuilt design files](../README.md#prebuilt-design-files)), or build them:

```bash
cd ../hw
vivado -mode batch -source create_project.tcl -tclargs basys3 bram_readback_writeback_top
```

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `BOARD`. The script attaches to the first board that the server lists. Connect only the target board to the server.
2. Run the script:

```bash
cd src
python main.py
```

The script prints a table with one row for each stage: the data, the ECC parity, `SBITERR` and the data bits that differ from the written word 0. At the end, it programs the FPGA again to clear the upset.

## Result

Sample output of a run on a Basys 3. The values of stage 3 depend on the board and the build.

```
SK-RAFT client 1.0.0, server 1.0.3
Programmed 210183BA2524A
Word 0 is written as 0x0000000000000000.

Stage                              Data                Parity  SBITERR  Data bits that differ from word 0
1  clock on, BRAM filled           0x0000000000000000  0x00    0        none
2  clock stopped                   0x0000000000000000  0x00    0        none
3  bit 0 injected, clock stopped   0x0000000000000003  0x06    0        0, 1
4  clock on                        0x0000000000000001  0x83    0        0
```
