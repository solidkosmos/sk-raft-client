# JTAG/BSCAN-driven signed multiply: clean DSP48 reference vs. fault-injection target

Two identical DSP48 signed-multiplier instances: `pblock_dsp_clean` (never injected into) and `pblock_dsp_target` (the one this script attacks). Each has its own operand-write channel - USER1 for clean, USER2 for target - so an upset can't corrupt both instances' inputs through a shared path, the same lesson example5's adder test found the hard way.

Every check recomputes the true signed product in Python from the operands just written and compares **both** instances against that, rather than against each other - two channels agreeing isn't proof either is right, and the known value sidesteps that entirely.

`REPEATS` single-bit trials run against `pblock_dsp_target`: inject one upset at a random essential bit, write a fresh random operand pair to both channels and check both instances, then inject that same bit again to flip it back before the next trial. Nothing accumulates across trials. A mismatch line (in signed decimal, both operands and all three results) prints whenever either instance disagrees with the true product; a warning means the clean reference also went wrong, which (with separate operand channels) can only mean routing shared between the two multipliers' own logic (`CONTAIN_ROUTING` is not set on either pblock).

## BSCAN register mapping

| Register | Width | Direction | Contents |
| --- | --- | --- | --- |
| USER1 | `a_len + b_len` bits | write | Clean instance's operand pair (`B<<a_len \| A`) |
| USER2 | `a_len + b_len` bits | write | Targeted instance's operand pair, same packing |
| USER3 | `a_len + b_len` bits | read | Clean instance's product |
| USER4 | `a_len + b_len` bits | read | Targeted instance's product |

## Requirements

- Python 3.9+, the `skraft` package installed, `reporting.py` alongside `main.py`.
- A running sk-raft server, target board connected over USB.
- A bitstream, EBD, and the XDC declaring both pblocks, all on the **server**.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `A_LEN` / `B_LEN` | `16` / `16` | Operand widths; must match the design's generics. |
| `REPEATS` | `80` | Single-bit trials to run against `PBLOCK_TARGET`. |
| `PBLOCK_CLEAN` / `PBLOCK_TARGET` | `"pblock_dsp_clean"` / `"pblock_dsp_target"` | Pblock names, as in the XDC. |

## Running it

```bash
python main.py
```

Reports how many of `REPEATS` trials left the target wrong. Interrupting with Ctrl-C mid-trial can leave one bit still flipped; reprogram before anything else.
