# Example 5: BRAM readback and writeback, a BRAM with built-in ECC under SK-RAFT injection

This example shows two effects of an SK-RAFT injection into the content of a block RAM that uses the built-in ECC of the BRAM and has no output register (`DO_REG = 0`):

1. The configuration access overwrites the output latch of the BRAM. While the clock is stopped, the BRAM outputs a wrong word.
2. When the clock starts, the BRAM reads the word again. The word has the injected bit flipped, and the ECC does not detect it (`SBITERR = 0`).

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
| 2 | Stop the clock. | The word is still correct. The output latch holds the last read. |
| 3 | Inject into word 0, bit 0 (`Ram=B:BIT0` in the LL file). The clock is still stopped. | A wrong word. |
| 4 | Start the clock. | Bit 0 is flipped, `SBITERR = 0`. |

**Stage 3.** To flip one bit, SK-RAFT reads the content frame, changes the bit and writes the frame back. This access to a content frame overwrites the output latch of the BRAM port. The BRAM has no output register, so its outputs show the latch directly: data, parity and `SBITERR` are not the values of word 0. The same occurs for each readback and each revert of a content frame.

**Stage 4.** The BRAM reads word 0 again, and the outputs are correct for the stored word. But the frame write went through the ECC encoder of the BRAM, which made new ECC bits for the flipped data. Thus the stored word is a valid ECC word, and the decoder finds no error. The flipped bit is silent data corruption, not an error that the ECC corrects.

Two consequences for SK-RAFT campaigns:

- A design that reads a BRAM with `DO_REG = 0` can take the wrong word of stage 3 after a freeze. The BRAM hold register pass ([`auxiliary_components/bram_hold_pass`](../../auxiliary_components/bram_hold_pass/README.md)) protects against this. This example builds without the pass to show the effect.
- `TargetMemory.BRAM` injection into a BRAM with `EN_ECC_WRITE = TRUE` does not test the built-in ECC. It gives a valid word with wrong data.

## Requirements

- Python 3.9 or a later version, with the `skraft` package installed.
- An SK-RAFT server in operation, with the target board connected through USB.
- The bitstream and the LL file of `bram_readback_writeback_top` in `hw/design_examples/<board>/bram_readback_writeback_top/`. Extract them from `design_examples.zip` (refer to [Prebuilt design files](../README.md#prebuilt-design-files)), or build them:

```bash
cd ../hw
vivado -mode batch -source create_project.tcl -tclargs basys3 bram_readback_writeback_top
```

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`, `SERIAL_NUMBER` and `BOARD`.
2. Run the script:

```bash
cd src
python main.py
```

The script prints a table with one row for each stage: the data, the ECC parity, `SBITERR` and the data bits that differ from the written word 0. At the end, it programs the FPGA again to clear the upset.

## Result

Sample output of a run on a Basys 3 (shortened). The frame addresses, the bit counts and the error counts depend on the board, the build and the seed.

```
Programmed 210183BFD452A
Word 0 is written as 0x0000000000000000.

Stage                              Data                Parity  SBITERR  Data bits that differ from word 0
1  clock on, BRAM filled           0x0000000000000000  0x00    0        none
2  clock stopped                   0x0000000000000000  0x00    0        none
3  bit 0 injected, clock stopped   0x0000000000000003  0x06    0        0, 1
4  clock on                        0x0000000000000001  0x83    0        0
```
