# Example 1: CRAM injection in three steps

This example shows the CRAM injection functions of SK-RAFT in three steps on one design. Each step is more selective than the step before it:

1. **Full-device CRAM.** The script reads back all the CRAM frames. Then it upsets random bits in these frames.
2. **Essential bits.** The server selects each bit from the design's essential bits. The server reads the essential bits from the EBD file.
3. **The essential bits of one pblock.** This step is the same as step 2, but in one pblock at a time: first `pblock_slow_heartbeat`, then `pblock_fast_heartbeat`.

The script keeps each upset for 100 ms, then flips the same bit again to correct it. Each step, and each pblock in step 3, continues until you press Enter. The script reprograms the FPGA before steps 2 and 3. Monitor the LEDs on the board to see the effect of each upset.

## Design

The design for this example is [`targeted_top`](../hw/sources_1/new/targeted_top.vhd). It has a fast heartbeat counter and a slow heartbeat counter, each in its own pblock. The XDC file of the design declares the two pblocks, for example:

```tcl
create_pblock pblock_fast_heartbeat
add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells fast_hb_inst]
resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X54Y91:SLICE_X57Y99}
```

A pblock keeps the cells of its instance in the given area. Two more properties control the pblock:

- `set_property EXCLUDE_PLACEMENT true [get_pblocks ...]` prevents the placement of other cells in the pblock.
- `set_property CONTAIN_ROUTING true [get_pblocks ...]` keeps the routing of the pblock inside the pblock.

The examples do not use `CONTAIN_ROUTING`, to keep them simple.

## Run the example

1. Make sure that the design files are in `src/design_files/`. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`, `DEVICE` and `design`.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `design` | `targeted_top.{bit,ebd}` + XDC | The design files. The script uploads them to the server. |
| `DEVICE` | `"210183BFD452A"` | The serial number of the target board. `get_devices()` gives the connected boards. |
| `pblocks` (in `main()`) | slow and fast heartbeat | The pblocks for step 3, as the XDC file names them. |

## Result

The script corrects each upset. Thus, the device configuration is clean at the end. If you stop the script with Ctrl+C during an upset, the upset can remain in the device. In that case, reprogram the FPGA before you do any other work.
