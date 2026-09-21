# Example 2: Targeted injection into essential or CRAM bits

Programs a bitstream, then injects upsets into either the design's essential bits (from the EBD) or all of CRAM.

Vivado only emits the EBD file when this is set before writing the bitstream:

```tcl
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
write_bitstream -force tester.bit
```

```bash
python main.py --program /path/on/server/tester.bit --ebd /path/on/server/tester.ebd [--all | --essential] [--random [N] | --exhaustive] [--accumulative | --non-accumulative]
```

| Flag | Meaning |
| --- | --- |
| `--program PATH` | Required. Server-side `.bit` path. |
| `--ebd PATH` | Server-side `.ebd` path. Required unless `--all` is set. |
| `--all` / `--essential` | Target all of CRAM, or only essential bits. Default: essential. |
| `--random [N]` | Inject `N` random bits, one at a time (default 1000). Default mode. |
| `--exhaustive` | Sweep every targeted bit once; `N` is ignored. Always leaves every bit flipped. |
| `--accumulative` / `--non-accumulative` | Random mode only: keep upsets in place, or revert them. Default: accumulative. |

Set `SK_RAFT_SERVER_IP` at the top of `main.py` before running.
