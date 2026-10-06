# Example 4: BRAM injection, configuration bits, content and ECC recovery

The design uses one RAMB36 in the 1K x 36 configuration. Each 36-bit word contains 24 data bits and 12 check bits. Logic in the fabric around the BRAM protects each data byte with its own Hamming SEC code (4 check bits for each byte). This logic is not the built-in ECC of the BRAM.

![Block diagram of brams_top. A BRAM in a pblock has an encoder on the write path and a decoder with a multiplexer on the read path. USER1 controls the clock gate, USER2 selects the address, USER3 carries the data and USER4 enables the ECC correction.](images/example4_brams_top_abstract.svg)

## Sequence

1. The script fills the memory. Then it reads back each word to make sure that the data is correct.
2. **Part 1.** The script injects essential CRAM upsets (`TargetMemory.ESSENTIAL_CRAM`) into the block type 0 frames of the BRAM column. Then it reads back the memory.
3. The script programs the FPGA again. Thus the upsets of part 1 do not have an effect on part 2.
4. The script fills the memory again.
5. **Part 2.** The script injects content upsets (`TargetMemory.BRAM`) into the block type 1 frames. The upsets add up, and the script does not correct them.
6. The script reads back the full memory two times: first with ECC off, then with ECC on.
7. The script programs the FPGA again, to clear the upsets of part 2.

In the two parts, the script injects one upset each 0.3 s until you press Enter. When part 2 continues for a longer time, more bytes get two or more flips. The SEC code cannot correct these bytes.

## BSCAN register map

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | write | BRAM clock enable (the script stops the clock during each injection) |
| USER2 | 16 bits | write | Address select (only the low 10 bits have an effect) |
| USER3 | 24 bits | read/write (the TAP exit path selects the direction) | The data at the selected address |
| USER4 | 1 bit | write | ECC correction enable. It applies to the BRAM read path only. The reset value is 0. |

## Requirements

- Python 3.9 or a later version, with the `skraft` package installed.
- An SK-RAFT server in operation, with the target board connected through USB.
- The bitstream, the EBD file, the LL file and the XDC file that declares `pblock_stock_bram`. The script uploads these files to the server.

## Configuration

| Constant | Default | Description |
| --- | --- | --- |
| `ADDRESS_BITS` | `10` | The address width that has an effect: 1024 words. |

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/brams_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`, `DEVICE` and `design`.
3. Run the script:

```bash
cd src
python main.py
```

## Result

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
