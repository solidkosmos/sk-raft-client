# Example 2: JTAG/BSCAN-driven adder, simplex vs. TMR, single-bit upsets

Programs a bitstream, then compares a plain (simplex) adder to a triplicated (TMR) one, each in its own pblock. Both adders share one operand register (USER1) and each has its own result register (USER2 simplex, USER3 TMR). Each trial injects one random essential bit into each pblock, drives 100 random operand pairs through both adders, marks an adder as failed if any of its results was wrong, then reverts both bits. Trials run until you press Enter.

```bash
python main.py
```

| Constant | Default | Meaning |
| --- | --- | --- |
| `design` | `tester.{bit,ebd}` + XDC | Design files, uploaded to the server by the script. |
| `PBLOCK_SIMPLEX` / `PBLOCK_TMR` | `"pblock_sngl_add"` / `"pblock_tmr_add"` | The two pblocks under test, as named in the XDC. |
| `OP_LEN` | `4` | Operand width; must match the design's `op_len` generic. |

The script first prints each pblock's essential-bit count, then keeps one status line updated with the trial count and each adder's result for that trial (green Correct / red Wrong) and its VF (vulnerability factor: the fraction of trials in which it failed). When you stop it, it prints the final error counts and VFs. Every trial reverts its bits right after checking, so the device should be left clean; interrupting with Ctrl-C mid-trial can still leave a bit flipped - reprogram before anything else in that case.

Set `SK_RAFT_SERVER_IP`, `DEVICE` and `design` at the top of `main.py` before running.
