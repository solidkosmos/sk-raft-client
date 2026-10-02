# SK-RAFT Concepts

How SK-RAFT locates and describes a fault, independent of any one example. The get-started examples (`examples/get_started_examples_package/`) are the hands-on counterpart to this document.

## The two planes

Every fault SK-RAFT injects lands in one of two places.

The **configuration plane** is the bitstream itself — the configuration memory (CRAM) that defines what the fabric *is*: each LUT's truth table, the routing between them, and a BRAM's mode and width. A fault here changes the circuit's structure.

The **application plane** is the live, dynamic state the configured circuit is working with as it runs — a flip-flop's current value, a BRAM's stored data. A fault here changes a value, not the circuit itself.

SK-RAFT can manipulate both planes directly. `TargetMemory.FF` and `TargetMemory.BRAM` inject into the application plane itself — flipping a register's current value or a stored data word — exactly as `TargetMemory.CRAM`/`ESSENTIAL_CRAM` inject into the configuration plane. Neither plane is just observed; both are addressable injection targets.

![Where a fault lands: the application plane and configuration plane are two physically stacked layers; a fault can strike through both at the same point, and configuration drives application state](images/plane-diagram.svg)

*The application plane (live flip-flop and BRAM state) sits above the configuration plane (CRAM) that defines the circuit. A fault can land in either layer at the same physical location. The next two sections cover the two cases that complicate this picture: essential bits within the configuration plane, and LUTRAM, which sits in both.*

## Essential bits

Most of a device's configuration memory is unused by any one design — unused routing slack, logic for features the design doesn't instantiate. A random bit flip anywhere in CRAM (`TargetMemory.CRAM`) usually lands there and has no observable effect.

**Essential bits** are the subset of CRAM this specific design actually depends on, read from its `.ebd` file. Targeting `TargetMemory.ESSENTIAL_CRAM` guarantees every injected bit is one the design relies on, so every flip has a real chance of producing an observable effect. This is the difference the first get-started example walks through directly.

## Where LUTRAM sits

LUTRAM is the one case that blurs the two planes. A LUT configured as distributed RAM stores its contents in its own configuration bits (its INIT field) — so a LUTRAM word is, physically, a set of essential configuration bits, but the circuit uses it as application-plane data. `TargetMemory.LUTRAM` targets exactly those bits.

BRAM keeps the two cleanly separate instead: its configuration (mode, width) and its content live in different frame types entirely (block type 0 vs. block type 1 — see `examples/get_started_examples_package/example4`), so `TargetMemory.ESSENTIAL_CRAM` and `TargetMemory.BRAM` never overlap the way CRAM and LUTRAM do.

## Pblocks: confining the search

Any of the targets above can be confined to a named pblock from the design's XDC (`pblock=` on `bit_count`, `inject_random`, and `inject_exhaustive`). This narrows injection to one region of the design — one heartbeat generator, one adder, one BRAM — without changing which plane or which essential-bit population is being drawn from.

## Locating a bit: FAR, word, and bit index

However a target is selected, SK-RAFT reports and accepts the same three coordinates: a Frame Address (FAR), a word index within that frame, and a bit index within that word. `dev.decode_far()` turns a FAR into its block type, top/bottom half, row, column, and minor frame number — useful for telling a configuration hit (block type 0) from a content hit (block type 1), as in `example4`.

## `TargetMemory` at a glance

| `TargetMemory` | Plane | Selects | Used in |
| --- | --- | --- | --- |
| `CRAM` | Configuration | Every configuration bit, essential or not | example1 (step 1) |
| `ESSENTIAL_CRAM` | Configuration | Only the bits this design's `.ebd` marks essential | example1 (steps 2-3), example2, example4 (Part 1) |
| `FF` | Application | A flip-flop's current register value | example3 (Part 1) |
| `LUTRAM` | Configuration, acting as application data | A distributed-RAM word's essential config bits | example3 (Part 2) |
| `BRAM` | Application | A block RAM word (content frames, block type 1) | example4 (Part 2) |
