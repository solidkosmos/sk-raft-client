# Example 1: Three widening steps of CRAM injection

Walks through sk-raft's targeting mechanics in order, against one design:

1. **Whole-device CRAM** - every CRAM frame is read back, then random bits anywhere in it are upset.
2. **Essential bits** - the server picks each bit from the design's essential bits, read from the EBD.
3. **A pblock's essential bits** - the same, confined to one pblock at a time: `pblock_slow_heartbeat`, then `pblock_fast_heartbeat`.

Every upset is held for 100 ms, then flipped back. Each step (and each pblock in step 3) runs until you press Enter, and the device is re-programmed before steps 2 and 3. Watch the toggling LEDs on the board to see the effect of each upset.

[`targeted_top`](../hw/sources_1/new/targeted_top.vhd)
(fast/slow heartbeat generators, each in its own pblock) is the design this
is written against. Its XDC declares both pblocks, e.g.:

```tcl
create_pblock pblock_fast_heartbeat
add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells fast_hb_inst]
resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X54Y91:SLICE_X57Y99}
```

A pblock constrains placement by using :
`set_property EXCLUDE_PLACEMENT true [get_pblocks ...] `, and routing by 
`set_property CONTAIN_ROUTING true [get_pblocks ...]`
the latter not being used in the examples for simplicity's sake.

```bash
python main.py
```

| Constant | Default | Meaning |
| --- | --- | --- |
| `design` | `targeted_top.{bit,ebd}` + XDC | Design files, uploaded to the server by the script. |
| `DEVICE` | `"210183BFD452A"` | Target board's serial; `device_list()` lists the connected ones. |
| `pblocks` (in `main()`) | slow, fast heartbeat | Pblocks step 3 confines to, as named in the XDC. |

Every upset is reverted, so the device should be left clean. Interrupting
with Ctrl-C while an upset is held can leave it in place; reprogram before
anything else in that case.

Set `SK_RAFT_SERVER_IP`, `DEVICE` and `design` at the top of `main.py`.
