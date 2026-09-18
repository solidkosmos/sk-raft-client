# BRAM injection: config bits, content, and ECC recovery

A single block RAM, reachable over JTAG. Its 24-bit data word is protected at byte level (the block's built-in ECC covers each of the three bytes on its own). The run has two phases against the same pblock (`pblock_stock_bram`), split by frame **block type**: block type 0 holds the primitive's own configuration (mode, width), block type 1 holds its stored content.

First, `CONFIG_INJECTIONS` upsets hit the block type 0 frames (`InjectionArea.CRAM`, not `BRAM` - these aren't content bits), followed by a quick round-trip sanity check and a reprogram, so this phase can't leave anything for the rest of the run to trip over. Then the memory is filled with a known pattern, `INJECTIONS` upsets hit the block type 1 content frames (`InjectionArea.BRAM`, cumulative, uncorrected), and the whole memory is read back twice - once with the ECC read path off, once on - so the difference between the two is exactly what the ECC corrected.

## BSCAN register mapping

| Register | Width | Access | Contents |
| --- | --- | --- | --- |
| USER1 | 16 bits | write | Address select (low 10 bits effective) |
| USER2 | 24 bits | read/write | Data at the selected address |
| USER3 | 1 bit | write | ECC read enable |

## Requirements

- Python 3.9+, the `skraft` package installed, `reporting.py` alongside `main.py`.
- A running sk-raft server, target board connected over USB.
- A bitstream, its LL file, and the XDC declaring `pblock_stock_bram`, all on the **server**.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `CONFIG_INJECTIONS` | `50` | Upsets into the pblock's own (block type 0) configuration. |
| `INJECTIONS` | `50` | Upsets into the pblock's content (block type 1), cumulative and uncorrected. |
| `ADDRESS_BITS` | `10` | Effective address width; 1024 words. |

## Running it

```bash
python main.py
```

If the initial write/verify pass finds the memory already wrong, the script stops without injecting anything. Headline result is the two wrong-address counts (ECC off vs. on) - a word that disappears between them had exactly one bit flipped, which byte-level ECC corrects; one that stays wrong had more than one. Faults are left in place; reprogram before anything else.
