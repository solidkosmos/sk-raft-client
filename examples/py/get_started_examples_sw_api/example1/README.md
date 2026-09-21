# Example 1: Program the device, then inject CRAM upsets

Programs a bitstream, then injects CRAM upsets - random or exhaustive, accumulative or reverted. Any bitstream works; use your own or build the provided [`adder_top`](.../getting_started_examples_hw/sources_1/new/adder_top.vhd) design.

```bash
python main.py --program /path/on/server/tester.bit [--random [N] | --exhaustive] [--accumulative | --non-accumulative]
```

| Flag | Meaning |
| --- | --- |
| `--program PATH` | Required. Server-side `.bit` path. |
| `--random [N]` | Inject `N` random bits, one at a time (default 1000). Default mode. |
| `--exhaustive` | Sweep every CRAM bit once; `N` is ignored. Always leaves every bit flipped - one bulk call, not a loop, so accumulative/non-accumulative doesn't apply. |
| `--accumulative` / `--non-accumulative` | Random mode only: keep upsets in place, or revert them. Default: accumulative. |

Set `SK_RAFT_SERVER_IP` at the top of `main.py` before running.
