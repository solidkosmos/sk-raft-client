# Fault injection confined to a pblock

Adds a spatial constraint on top of TEST 3's essential-bit targeting: it reads a pblock's definition from the design's XDC, works out exactly which configuration bits belong to that region, and injects only into those. The example design is a Basys3 board with two heartbeat generators, each in its own pblock (`pblock_fast_heartbeat`, `pblock_slow_heartbeat`) - injecting into the fast one and watching both LEDs shows the fast heartbeat degrade while the slow one keeps going, confinement you can see from across the bench.

This is the pattern to reach for when you need to know whether a fault in one region of a design can reach another - partition isolation, one lane of a redundant design, or reproducing a suspected field failure by concentrating injection where you suspect it.

## Requirements

- Python 3.9+, the `skraft` package installed, `reporting.py` alongside `main.py`.
- A running sk-raft server, target board connected over USB.
- A bitstream, matching EBD, and the XDC declaring the pblocks, all on the **server**.

The XDC must be the one actually used for implementation:

```tcl
create_pblock pblock_fast_heartbeat
add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells fast_hb_inst]
resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X54Y91:SLICE_X57Y99}
```

A pblock constrains placement, not routing by default, so a bit inside the footprint can still belong to routing shared with logic outside it. `set_property CONTAIN_ROUTING true [get_pblocks ...]` closes that gap at the cost of timing/area flexibility.

## Configuration

| Constant | Default | Meaning |
| --- | --- | --- |
| `PBLOCK` | `"pblock_fast_heartbeat"` | Pblock to attack, named exactly as in the XDC. |
| `INJECTIONS` | `300` | Upsets to inject inside it. |
| `PAUSE_S` | `0.1` | Delay after each upset, so a human can watch. `0` for full speed. |
| `ESSENTIAL_ONLY` | `True` | Restrict to the pblock's essential bits rather than its whole footprint. |
| `LOG_PATH` / `VERBOSE` | `"pblock_injection.log"` / `False` | Transcript and per-clause detail. |

## Running it

```bash
python main.py
```

Injections are cumulative within the run; the script reprograms at the end to clear them (skipped on Ctrl-C - reprogram manually then). To characterise individual bits rather than watching a region degrade, see the single-bit-upset inject/check/revert style used in example5.
