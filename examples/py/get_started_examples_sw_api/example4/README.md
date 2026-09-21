# Example 4: JTAG/BSCAN-driven adder, simplex vs. TMR, single-bit upsets

Programs a bitstream, then compares a plain (simplex) adder to a triplicated (TMR) one, each in its own pblock with its own BSCAN operand channel, by running independent inject/check[/revert] trials against each and comparing failure rates.


```bash
python main.py --program /path/on/server/tester.bit --ebd /path/on/server/tester.ebd --xdc /path/on/server/tester.xdc [--all | --essential] [--random [N] | --exhaustive] [--accumulative | --non-accumulative]
```

| Flag | Meaning |
| --- | --- |
| `--program PATH` | Required. Server-side `.bit` path. |
| `--ebd PATH` | Required. Server-side `.ebd` path. |
| `--xdc PATH` | Required. Server-side `.xdc` path declaring both pblocks. |
| `--all` / `--essential` | Target the whole footprint of each pblock, or only its essential bits. Default: essential. |
| `--random [N]` | Run `N` single-bit trials against each pblock (default 50). Default mode. |
| `--exhaustive` | Sweep every targeted bit of each pblock once; `N` is ignored. |
| `--accumulative` / `--non-accumulative` | Leave upsets in place across trials, or revert each right after checking. Default: accumulative. |

Both campaigns share these settings but stay confined to their own pblock's bits. Reports how many trials broke each adder. A `!` warning means the *other* adder also broke on that trial - shared routing, not that adder's own fault. Interrupting with Ctrl-C can leave a bit flipped; reprogram before anything else.

Set `SK_RAFT_SERVER_IP` at the top of `main.py` before running.
