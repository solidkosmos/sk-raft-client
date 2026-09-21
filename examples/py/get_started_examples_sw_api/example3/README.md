# Example 3: Fault injection confined to a pblock

Programs a bitstream, then injects upsets confined to one pblock from the XDC - its whole footprint, or just its essential bits.

The XDC must declare the pblock as used for implementation:

```tcl
create_pblock pblock_fast_heartbeat
add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells fast_hb_inst]
resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X54Y91:SLICE_X57Y99}
```

A pblock constrains placement, not routing, by default - `set_property CONTAIN_ROUTING true [get_pblocks ...]` closes that gap.

```bash
python main.py --program /path/on/server/tester.bit --ebd /path/on/server/tester.ebd --xdc /path/on/server/tester.xdc --target pblock_fast_heartbeat [--all | --essential] [--random [N] | --exhaustive] [--accumulative | --non-accumulative]
```

| Flag | Meaning |
| --- | --- |
| `--program PATH` | Required. Server-side `.bit` path. |
| `--ebd PATH` | Required. Server-side `.ebd` path. |
| `--xdc PATH` | Required. Server-side `.xdc` path declaring `--target`. |
| `--target NAME` | Required. Pblock to attack, named exactly as in the XDC. |
| `--all` / `--essential` | Target the whole footprint of `--target`, or only its essential bits. Default: essential. |
| `--random [N]` | Inject `N` random bits inside `--target` (default 300). Default mode. |
| `--exhaustive` | Sweep every targeted bit of `--target` once; `N` is ignored. |
| `--accumulative` / `--non-accumulative` | Keep upsets in place, or revert each as it goes - applies to both modes here. Default: accumulative. |

If left accumulative, the device is re-programmed at the end to clear the upsets (skipped on Ctrl-C - reprogram manually then).

Set `SK_RAFT_SERVER_IP` at the top of `main.py` before running.
