# JTAG/BSCAN-driven adder: simplex vs. TMR, single-bit upsets

Two adders on the same board, fed identical operands: a plain (simplex) adder and one built from three replicated adders and a majority voter (TMR), each in its own pblock (`pblock_sngl_add`, `pblock_tmr_add`). The point is to sample how often a single essential-bit upset actually breaks each one, and compare the failure rates.

Each adder has its **own** BSCAN write channel for its operand pair (USER1 for simplex, USER2 for TMR), even though the script always writes the same values to both. That's deliberate: an earlier version of this test shared one write path for both adders, and a single upset there could corrupt both adders' inputs identically - a single point of failure that had nothing to do with either adder's own logic. Separate channels rule that out structurally.

The run is two independent campaigns, one per pblock, each running `REPEATS` single-bit trials: inject one upset at a random essential bit, apply a fresh random operand pair and check both adders, then inject that exact same bit again to flip it back (`FpgaBitFlip` toggles, so hitting the same spot twice reverts it) before the next trial. Nothing accumulates - each trial is an independent sample. A trial's mismatch also flags if the *other* adder went wrong too, which would mean the bit hit logic or routing shared between the two adders rather than the one under test (neither pblock has `CONTAIN_ROUTING` set).

## BSCAN register mapping

| Register | Width | Direction | Contents |
| --- | --- | --- | --- |
| USER1 | `op_len * 2` bits | write | Simplex adder's operand pair (`B<<op_len \| A`) |
| USER2 | `op_len * 2` bits | write | TMR adder's operand pair, same packing |
| USER3 | `op_len + 1` bits | read | Simplex adder's sum + carry |
| USER4 | `op_len + 1` bits | read | TMR adder's sum + carry |

## Requirements

- Python 3.9+, the `skraft` package installed, `reporting.py` alongside `main.py`.
- A running sk-raft server, target board connected over USB.
- A bitstream, EBD, and the XDC declaring both pblocks, all on the **server**.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `OP_LEN` | `4` | Bits per operand; must match the design's `op_len` generic. |
| `REPEATS` | `80` | Single-bit trials to run against each pblock. |
| `PBLOCK_SIMPLEX` / `PBLOCK_TMR` | `"pblock_sngl_add"` / `"pblock_tmr_add"` | Pblock names, as in the XDC. |

## Running it

```bash
python main.py
```

Reports how many of `REPEATS` trials broke each adder. A `!` warning line means an injection in one pblock also broke the *other* adder - shared routing, not that adder's own fault tolerance. Interrupting with Ctrl-C mid-trial can leave one bit still flipped; reprogram before anything else.
