# Example 4: BRAM injection, config bits, content, and ECC recovery

A single RAMB36 used as 1K x 36. Each 36-bit word holds 24 data bits and 12 check bits: fabric logic around the BRAM protects each data byte with its own Hamming SEC code (4 check bits per byte). This is not the BRAM's built-in ECC.

First, the memory is filled and checked to be sure every word round-trips. Essential CRAM upsets (`TargetMemory.ESSENTIAL_CRAM`) then hit the block-type-0 frames of the BRAM column, the memory is read back, and the device is reprogrammed, so nothing from this phase carries into the next. Then the memory is filled again, content upsets (`TargetMemory.BRAM`, accumulative, uncorrected) hit the block-type-1 frames, and the whole memory is read back twice: once with ECC off, once with it on.

Both phases inject until you press Enter, one upset every 0.3 s. The longer Part 2 runs, the more bytes collect two or more flips, which SEC can't correct.

## BSCAN register mapping

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 1 bit | write | BRAM clock enable (frozen around each injection) |
| USER2 | 16 bits | write | Address select (low 10 bits effective) |
| USER3 | 24 bits | read/write (TAP exit path selects which) | Data at the selected address |
| USER4 | 1 bit | write | ECC correction enable (BRAM read path only; resets to 0) |

## Requirements

- Python 3.9+, the `skraft` package installed.
- A running sk-raft server, target board connected over USB.
- A bitstream, its EBD and LL files, and the XDC declaring `pblock_stock_bram`; the script uploads them to the server.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `ADDRESS_BITS` | `10` | Effective address width; 1024 words. |

## Running it

```bash
python main.py
```

If the initial write/verify pass finds the memory already wrong, the script stops without injecting anything. Each read-back prints every wrong word with its expected and read data bits and the faulty bit positions. Headline result is the two wrong-address counts (ECC off vs. on). A word that is wrong only with ECC off had single flips, which SEC corrected. A word still wrong with ECC on had two or more flips in a byte, which SEC can't correct and may mis-correct. Flips in check bits never show with ECC off, and a single one is masked with ECC on. Faults are left in place; reprogram before anything else.
