# NEORV32 Hardening Example

Vendor | Board | Design Name | Version | Vivado | License
------ | ----- | ----------- | ------- | ------ | -------
SolidKosmos S.A. | Digilent Basys-3 (Xilinx Artix-7 xc7a35tcpg236-1) | test_neo_hardened | 1.0 | 2019.1 | BSD-3-Clause

## Content

1. [Overview](#1-overview)
2. [Design Flow](#2-design-flow)
3. [Porting to a Different Board](#3-porting-to-a-different-board)
4. [Directory Layout](#4-directory-layout)
5. [The HARDEN_EN Generic](#5-the-harden_en-generic)
6. [Fault-Injection Test Harness](#6-fault-injection-test-harness)
7. [Firmware](#7-firmware)
8. [Known Limitations](#8-known-limitations)
9. [License and Third-Party Notices](#9-license-and-third-party-notices)
10. [Revision History](#10-revision-history)
11. [References](#11-references)

## 1. Overview

This design wraps a [NEORV32](https://github.com/stnolting/neorv32) RISC-V SoC
with a set of SECDED/parity/ECC hardening additions (DMEM, register file,
CPU control FSM state, program counter) and a JTAG-driven fault-injection
test harness, targeting a Digilent Basys-3 board. It exists to let a single
bitstream family be built two ways -- hardened and unhardened -- so the
effect of the hardening can be measured directly under fault injection
rather than argued about in the abstract.

The processor boots via NEORV32's UART bootloader (`BOOT_MODE_SELECT => 2`),
so this repository ships the hardware design only; application firmware is
uploaded separately over UART after configuration. See
[Firmware](#7-firmware) below.

## 2. Design Flow

1. Install Vivado 2019.1 (or compatible) and the board files for the Basys-3.
2. Clone/copy this repository to a local path with no spaces.
3. Open Vivado, switch to the **Tcl Console**, `cd` into the repository root,
   and run:
   ```tcl
   source create_project.tcl
   ```
   This regenerates the full project (`test_neo.xpr`) from source -- nothing
   binary is checked in.
4. To build the **unhardened baseline** instead of the default hardened
   build, set the top-level generic before running synthesis:
   ```tcl
   set_property generic HARDEN_EN=false [current_fileset]
   ```
   Hardened and unhardened builds need separate synthesis runs, since
   generics resolve at synthesis time.
5. Run synthesis and implementation, generate the bitstream, and program the
   Basys-3 as usual.
6. Connect a UART terminal (115200 8N1) to the board's USB-UART port for the
   NEORV32 bootloader console, and a JTAG cable for the fault-injection
   harness (see below).

## 3. Porting to a Different Board

This example is developed and validated against the Basys-3, but nothing in
the design is Basys-3-specific at the RTL level -- the JTAG bridge uses the
generic `BSCANE2` primitive available on any 7-series device, and the
NEORV32 core itself is board-agnostic. Moving to another board is left to
the user rather than exposed as a build-time choice, and in practice comes
down to two changes:

1. Update the target part/board in `create_project.tcl` (`set_property
   part ...` / `set_property board_part ...`) for the new device.
2. Swap in that board's own XDC file in place of `Basys-3-Master.xdc`,
   remapping the clock, UART, and GPIO pins used by
   `neorv32_test_setup_bootloader.vhd` and `tester.vhd`.

If the new board uses a different input clock frequency, also update
`CLOCK_FREQUENCY` on `neorv32_test_setup_bootloader`. One thing that won't
carry over automatically: the `clk_cycle_ctrlr` placement pblock in the XDC
is pinned to absolute slice coordinates on the `xc7a35tcpg236-1` die, so on
a different part it needs to be redrawn (or simply removed and left to the
placer) rather than copied as-is.

## 4. Directory Layout

Path | Contents
---- | --------
`test_neo.srcs/sources_1/imports/rtl/` | Vendored NEORV32 core (`core/`) and the top-level test setup (`test_setups/neorv32_test_setup_bootloader.vhd`). Most files are unmodified NEORV32; modified files are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
`test_neo.srcs/sources_1/imports/new/`, `.../sources_1/new/`, `.../UTILITIES/` | Original SolidKosmos S.A. sources: the JTAG/BSCAN bridge, the clock-cycle stepping controller, and the parity/SECDED building blocks.
`test_neo.srcs/sources_1/new/` | `secded_enc8b.vhd` / `secded_dec8b.vhd` -- the DMEM byte-lane Hamming codec.
`test_neo.srcs/constrs_1/imports/` | Basys-3 pin/timing constraints (`Basys-3-Master.xdc`).
`create_project.tcl` | Single source of truth for the Vivado project. Regenerates `test_neo.xpr` and the full fileset from scratch.
`LICENSE`, `THIRD_PARTY_NOTICES.md` | BSD-3-Clause license text and a full per-file breakdown of what's vendored, what's modified, and what's original.

## 5. The HARDEN_EN Generic

All hardening in this design is gated behind one generic,
`HARDEN_EN : boolean := true`, threaded from
`neorv32_test_setup_bootloader` down through `neorv32_top` / `neorv32_cpu` to
each modified file. With `HARDEN_EN => false` the design should behave like
stock NEORV32 for comparison purposes. Two implementation notes:

- In `neorv32_dmem.vhd` and `neorv32_prim.vhd` (register-file ECC), the
  protected and unprotected datapaths are separate `generate` branches, so
  the ECC hardware is genuinely absent from a disabled build.
- In `neorv32_cpu_control.vhd` and `neorv32_cpu_frontend.vhd`, the
  SECDED/parity hardware stays physically present in both configurations
  (it's fused into the FSM's combinational core); only its effect on
  execution and interrupt reporting is masked when disabled.

Full per-file detail is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 6. Fault-Injection Test Harness

The `tester` entity wires a two-channel JTAG/BSCAN bridge to a
single-step/burst clock-cycle controller (`clk_cycle_ctrlr`) that gates the
clock reaching the NEORV32 instance:

- **USER1** -- write: design reset (active low). Read: 32-bit status/CRC word.
- **USER2** -- write: 32-bit step-count command. Read: live step-count/status.

Commands written to USER2: any nonzero value loads a new cycle countdown,
`CMD_START_C` (0x1) releases it, `CMD_CANCEL_C` (0x2) aborts back to idle.
A `check_tx`/`DRAIN_TX` safety keeps the clock alive past the countdown if
the UART still has data in flight, so a print is never cut off mid-byte.

## 7. Firmware

This repository ships `sw/hardening_coremark/main.c` -- the part of the
firmware that's actually specific to this design. It installs the custom
fast-interrupt handlers for the hardening IRQs added here (DMEM correction,
register-file ECC, CPU-control/frontend FSM-state and PC/RA parity) before
handing off to CoreMark, and doubles as a worked example of wiring up those
interrupts. It's uploaded separately over UART via the NEORV32 bootloader,
per [Overview](#1-overview).

Everything else needed to build it is NEORV32's own stock
[`sw/example/coremark/`](https://github.com/stnolting/neorv32/tree/main/sw/example/coremark)
(benchmark source, port layer, makefile, and CoreMark's own license) --
clone NEORV32 and drop `main.c` in, replacing `core_main.c`'s ownership of
the entry point. `core_portme.c`/`core_portme.h` need a few changes from
stock to reproduce this build:

- Interrupts are left enabled during the timed run (stock CoreMark disables
  them for timing accuracy) -- needed so the hardening IRQs can actually
  fire and be observed while the benchmark runs.
- `ITERATIONS` reduced to 3, for a short, fast, repeatable run rather than
  an accurate/official CoreMark score.
- Floating-point result printing removed, to keep the build lightweight.
- UART baud rate set to 500000.
- A CRC over the printed output characters was added, so the console
  output itself carries an integrity check.

This isn't meant to document a full experimental methodology -- just enough
for someone to reproduce the same firmware build.

## 8. Known Limitations

- The DMEM decoder (`secded_dec8b`) corrects based on the Hamming syndrome
  only; it does not check overall parity, so it cannot distinguish a
  single-bit error from a double-bit one. Double-bit corruption may be
  silently mis-corrected rather than flagged.
- Register-file hardware ECC (`neorv32_prim_sdpram` on `RAMB36E1`) only
  covers the FPGA-style register file. The ASIC-style (`CPU_RF_HW_RST_EN`)
  register file has no ECC path.
- CPU-control and frontend hardening cannot be fully removed by
  `HARDEN_EN => false` at the hardware level (see [Section 5](#5-the-harden_en-generic));
  only its effect on program behavior is disabled.

## 9. License and Third-Party Notices

This project is licensed under BSD-3-Clause -- see [LICENSE](LICENSE).
NEORV32 is Copyright (c) NEORV32 contributors / Stephan Nolting, also
BSD-3-Clause. A full file-by-file breakdown of vendored, modified, and
original sources -- including every hardening change and why it was made --
is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 10. Revision History

Date | Design Version | Description
---- | --------------- | -----------
2026-07 | 1.0 | Initial public example: DMEM/regfile/CPU-control/frontend hardening, `HARDEN_EN` generic, JTAG fault-injection harness.

## 11. References

- [NEORV32 RISC-V Processor](https://github.com/stnolting/neorv32)
- [NEORV32 Data Sheet](https://stnolting.github.io/neorv32)
- [Digilent Basys-3 Reference Manual](https://digilent.com/reference/programmable-logic/basys-3/reference-manual)
- [Xilinx UG473 -- 7 Series FPGAs Memory Resources](https://www.xilinx.com/support/documentation/user_guides/ug473_7Series_Memory_Resources.pdf)
