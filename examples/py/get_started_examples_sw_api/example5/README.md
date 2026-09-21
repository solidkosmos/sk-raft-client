# Example 5: JTAG/BSCAN-driven signed multiply, clean DSP48 reference vs. fault-injection target

Two identical DSP48 signed multipliers - `pblock_dsp_clean` (untouched reference) and `pblock_dsp_target` (the one this script attacks) - each with its own BSCAN operand channel. Every check recomputes the true signed product in Python and compares both instances against it, rather than against each other.

```bash
python main.py --program /path/on/server/tester.bit --ebd /path/on/server/tester.ebd --xdc /path/on/server/tester.xdc [--all | --essential] [--random [N] | --exhaustive] [--accumulative | --non-accumulative]
```

| Flag | Meaning |
| --- | --- |
| `--program PATH` | Required. Server-side `.bit` path. |
| `--ebd PATH` | Required. Server-side `.ebd` path. |
| `--xdc PATH` | Required. Server-side `.xdc` path declaring both pblocks. |
| `--all` / `--essential` | Target the whole footprint of the target pblock, or only its essential bits. Default: essential. |
| `--random [N]` | Inject `N` random bits against the target pblock, one at a time (default 200). Default mode; whether each is reverted before the next depends on `--accumulative`/`--non-accumulative`. |
| `--exhaustive` | Sweep every targeted bit of the target pblock once; `N` is ignored. |
| `--accumulative` / `--non-accumulative` | Leave upsets in place across trials, or revert each right after checking. Default: accumulative. |

`pblock_dsp_clean` is never injected into; it's the untouched hardware reference. Reports how many trials left the target wrong. A `!` warning means the clean reference also went wrong on that trial - shared routing, not real cross-talk of operands. Interrupting with Ctrl-C can leave a bit flipped; reprogram before anything else.

Set `SK_RAFT_SERVER_IP` at the top of `main.py` before running.
