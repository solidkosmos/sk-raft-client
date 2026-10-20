# Third-Party Notices

This project is built around the **NEORV32 RISC-V Processor**
(https://github.com/stnolting/neorv32).

```
The NEORV32 RISC-V Processor
Copyright (c) NEORV32 contributors.
Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.
Licensed under the BSD-3-Clause license, see LICENSE for details.
SPDX-License-Identifier: BSD-3-Clause
```

The full, unmodified NEORV32 license text is reproduced in `LICENSE-NEORV32`
at the project root. It applies to all NEORV32 files, vendored and modified.
The SolidKosmos S.A. files of this example are licensed under Apache-2.0 (see
the sections below). The majority of the files under
`hw/neorv32/core/` are vendored copies of NEORV32
used **unmodified**.

## Modified NEORV32 files

SolidKosmos S.A. modified the following NEORV32 files to add the hardening
features used by this example design (SECDED/parity fault detection and
correction, and test-harness hooks). Each file carries an inline
"Modified by SolidKosmos S.A. (2026)" note immediately below its original
NEORV32 header, describing the specific change. Everything outside of the
noted change is original NEORV32 code and remains under NEORV32's copyright.

| File | Modification |
|---|---|
| `hw/neorv32/core/neorv32_top.vhd` | Added a `check_tx` test-harness port; wired DMEM-ECC interrupt and regfile/frontend correction/parity flags into custom fast-interrupt lines. Added the top-level `HARDEN_EN` generic (default `true`), threaded to `neorv32_cpu` and `neorv32_dmem`. |
| `hw/neorv32/core/neorv32_cpu.vhd` | Added a `dmem_irq_i` signal; latches/merges ECC-correction and parity/FSM flags into a custom fast-interrupt-request line. Threads `HARDEN_EN` to `neorv32_cpu_frontend`, `neorv32_cpu_control`, and `neorv32_cpu_regfile`. |
| `hw/neorv32/core/neorv32_dmem.vhd` | Added per-byte-lane Hamming SEC encode/decode (`secded_enc8b`/`secded_dec8b`, one per byte, 12-bit codeword) and an `irq_ecc_dmem` output, gated behind `HARDEN_EN` (falls back to a plain unprotected byte-wide RAM when disabled). The decoder corrects based on syndrome only, without checking overall parity, so `par_i`/`uncorr` are unused -- it can't distinguish a single-bit from a double-bit error. |
| `hw/neorv32/core/neorv32_cpu_regfile.vhd` | Added `irq_ecc_o`, sourced from the soft SECDED (`secded_enc32b`/`secded_dec32b`) in `neorv32_prim_sdpram` (FPGA-style register file only), gated behind `HARDEN_EN`; tied to `'0'` in the ASIC-style (`RST_EN`) register file, which has no ECC path. |
| `hw/neorv32/core/neorv32_cpu_control.vhd` | Added SECDED (`secded_enc4b`/`secded_dec4b`) protection for the exe-engine FSM state, and parity generation/checking for PC/PC2/RA. Gated behind `HARDEN_EN`: when disabled, `exe_fctv_state` bypasses correction (direct passthrough of the raw state register) and the state-correction/PC-parity IRQ bits are masked out of `custom_fast_irq`. |
| `hw/neorv32/core/neorv32_cpu_frontend.vhd` | Added parity generation/checking for the fetch-stage PC, and a one-hot weight detector on the fetch engine's own state register. Gated behind `HARDEN_EN`: `check_o`/`ill_state_o` are masked to `'0'` when disabled. |
| `hw/neorv32/core/neorv32_uart.vhd` | Added a `check_tx` output used by the external clock controller to detect an in-flight/queued transmission. |
| `hw/neorv32/core/neorv32_prim.vhd` | The `neorv32_prim_sdpram` entity only: added soft SECDED in fabric logic (`secded_enc32b` on the write data, one `secded_dec32b` on each read port) around the inferred block RAM, and an `irq_ecc_o` output that flags a corrected read, gated behind `HARDEN_EN` (falls back to the original inferred-BRAM behavioral description when disabled). Other primitives in this file are unmodified. |
| `hw/neorv32/neorv32_test_setup_bootloader.vhd` | The top-level entity of this project. Instantiates the safe-startup PLL (`clk_gen_wrapper`) and the fault-injection test harness (`tester`), runs the NEORV32 on the gated clock of the harness, sends the GPIO output to the harness (CRC word) and the LEDs, and adds the `HARDEN_EN` and clock-frequency generics. |
| `sw/hardening_coremark/main.c` | Adapted from NEORV32's `sw/example/hello_world/main.c`. Installs the custom fast-interrupt handlers for the hardening IRQs (see [README.md](README.md#6-firmware)) before handing off to CoreMark. |

### The `HARDEN_EN` generic

All of the SECDED/parity/ECC hardening added above is gated behind a single
`HARDEN_EN : boolean := true` generic, exposed at every level from
`neorv32_test_setup_bootloader` (the actual top-level entity used by this
project) down through `neorv32_top` / `neorv32_cpu` to the individual modified
files. Building with `HARDEN_EN => false` produces an unhardened baseline that
should behave like stock NEORV32 for fault-injection comparisons: no SECDED/
parity/ECC hardware is left in a position to affect execution or report
errors. Two exceptions to note:

- In `neorv32_dmem.vhd` and `neorv32_prim.vhd` (regfile ECC), the protected
  and unprotected datapaths are separate `generate` branches, so the ECC
  hardware is genuinely absent from the disabled build.
- In `neorv32_cpu_control.vhd` and `neorv32_cpu_frontend.vhd`, the SECDED/
  parity component instances remain physically present in both
  configurations (this logic is fused too tightly into the FSM's
  combinational core to cleanly remove via `generate` without a larger
  restructuring); only their effect on execution and interrupt reporting is
  masked when `HARDEN_EN` is false.

## Original SolidKosmos S.A. files

The following files are original SolidKosmos S.A. work (fault-injection test
harness, hardening support logic and scripts), licensed under Apache-2.0 like
the rest of this repository (see `LICENSE.md` at the repository root):

- `create_project.tcl`
- `hw/xdc/basys3.xdc`
- `neorv_fi_example/run_injection.py`
- `neorv_fi_example/bscan_routine_helpers.py`
- `hw/src/tester.vhd`
- `hw/src/clk_cycle_ctrlr.vhd`
- `hw/src/harness_controller.vhd`
- `hw/src/secded_ecc_enc_4bit.vhd` (entity `secded_enc4b`)
- `hw/src/secded_ecc_dec_4bit.vhd` (entity `secded_dec4b`)
- `hw/src/secded_enc32b.vhd` (entity `secded_enc32b`) --
  32-bit extended Hamming (39,32) SECDED encoder used by `neorv32_prim_sdpram`
  (register file).
- `hw/src/secded_dec32b.vhd` (entity `secded_dec32b`) --
  its counterpart decoder; corrects single-bit errors and flags double-bit
  errors (`uncorr_o`).
- `hw/src/par_generator.vhd` (entity `parity_generator`)
- `hw/src/par_checker.vhd` (entity `parity_checker`)

## SK-RAFT getting-started blocks (Apache-2.0)

These files come from the SK-RAFT getting-started examples (`get_started/hw`)
and keep their Apache-2.0 licence headers:

- `hw/src/bscan_interface.vhd` (with
  `async_reg` attributes added on its synchronizer flops)
- `hw/src/bscan_primitive_wrapper.vhd`
- `hw/src/bscan_user_register_io.vhd`
- `hw/src/examples_utilities_pkg.vhd`
- `hw/src/clk_gen_wrapper.vhd` (extended here with a
  `g_clkout_freq_mhz` generic for the output frequency)
- `hw/src/secded_enc8b.vhd` (entity `secded_enc8b`) --
  8-bit Hamming (12,8) encoder used by `neorv32_dmem.vhd`. Also computes an
  overall/DED parity bit (`ded_par_o`), which is left unconnected since the
  decoder below doesn't check it.
- `hw/src/secded_dec8b.vhd` (entity `secded_dec8b`) --
  its counterpart decoder; corrects based on syndrome only (see the DMEM row
  above).

## CoreMark (referenced, not vendored)

`sw/hardening_coremark/main.c` runs the [CoreMark](https://github.com/eembc/coremark)
benchmark, © EEMBC, licensed under Apache License 2.0 plus EEMBC's CoreMark
Acceptable Use Agreement (governing use of the "CoreMark" trademark/name,
not redistribution of the code). CoreMark itself, and the NEORV32 platform
port layer it runs on (`core_portme.c`/`.h`), are **not** included in this
repository -- build against NEORV32's own
[`sw/example/coremark/`](https://github.com/stnolting/neorv32/tree/main/sw/example/coremark)
instead, per [README.md](README.md#6-firmware), which also lists the
specific `core_portme.c`/`.h` changes needed to reproduce this build.
