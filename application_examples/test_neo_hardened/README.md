# NEORV32 Hardening Example

Board | Part | License
----- | ---- | -------
Digilent Basys 3 | xc7a35tcpg236-1 (Artix-7) | Apache-2.0 (SolidKosmos code), BSD-3-Clause (NEORV32)

## 1. Overview

A [NEORV32](https://github.com/stnolting/neorv32) RISC-V SoC with
SECDED/parity hardening (DMEM, register file, CPU control FSM state, program
counter) and a JTAG test harness for fault injection with SK-RAFT. The same
design builds hardened or unhardened (`HARDEN_EN`), so the effect of the
hardening can be measured under fault injection.

![Block diagram of the example. The board clock goes through the safe clock generation PLL, a root clock gate (BSCAN USER3) and the cycle controller, which enables the clock for the number of cycles set over BSCAN USER2, then to the NEORV32. The tester (BSCAN USER1/USER2/USER3 and the cycle controller) sits in harness_pblock, which SK-RAFT does not inject into. Inside the NEORV32, the hardened modules (CPU control, CPU frontend, register file, DMEM) are grouped apart from the stock modules (IMEM, UART0, GPIO and the rest). USER1 resets the NEORV32 and reads the CRC word from its GPIO, the UART tx_busy keeps the clock running until the UART is idle, and ECC/parity events raise fast interrupts that print an [ALERT] on the UART.](images/neorv32_hardening_blocks.svg)

The NEORV32 boots the CoreMark firmware from the IMEM image
(`BOOT_MODE_SELECT => 2`). The image is in
`hw/neorv32/neorv32_application_image.vhd`, so the bitstream holds the
firmware and no upload is necessary.

## 2. Build and Run

1. From this folder, create the project:
   ```
   vivado -mode batch -source create_project.tcl
   ```
   The script creates `test_neo/test_neo.xpr` from `hw/` and opens it in the
   GUI. Optional arguments: `-tclargs [project_name] [project_dir]`.
2. Run **Generate Bitstream**. The `.bit`, `.ebd` and `.ll` files go to
   `test_neo/test_neo.runs/impl_1/`.
3. Run the campaign with `neorv_fi_example/run_injection.py` (see its
   [README](neorv_fi_example/README.md)). The script programs the FPGA and
   reads the UART at 500000 baud.

For the unhardened baseline, remove the `#` from this line near the end of
`create_project.tcl` and use a separate project name:
```tcl
# set_property generic HARDEN_EN=false [get_filesets sources_1]
```

## 3. The HARDEN_EN Generic

`HARDEN_EN : boolean := true` goes from `neorv32_test_setup_bootloader`
through `neorv32_top` / `neorv32_cpu` to each modified file. With
`HARDEN_EN => false` the design behaves like stock NEORV32:

- DMEM and register file (`neorv32_dmem.vhd`, `neorv32_prim.vhd`): the
  protected and the plain datapaths are separate `generate` branches, so a
  disabled build has no ECC hardware.
- CPU control and frontend (`neorv32_cpu_control.vhd`,
  `neorv32_cpu_frontend.vhd`): the SECDED/parity logic stays in the design;
  only its effect on execution and on the interrupts is masked.

## 4. Fault-Injection Test Harness

`tester` connects three BSCAN user registers to the cycle controller
(`clk_cycle_ctrlr`), which gates the NEORV32 clock:

Register | Write | Read
-------- | ----- | ----
USER1 | design reset (active low) | 32-bit status/CRC word
USER2 | 32-bit step-count command | live step count/status
USER3 | root clock enable (1 = on) | synchronized enable

USER2 commands: a nonzero value loads a cycle countdown, 0x1 starts it, 0x2
cancels it. If the UART still sends when the countdown ends, the controller
keeps the clock on until the UART is idle (`check_tx`). The root clock feeds
the NEORV32, the harness and the cycle controller. It is off after
programming, and `run_injection.py` turns it off during each injection.

## 5. Firmware

`sw/hardening_coremark/main.c` is the design-specific part of the firmware.
It installs the fast-interrupt handlers of the hardening (DMEM and register
file corrections, CPU control/frontend state and PC/RA parity) and then runs
CoreMark. The rest is NEORV32's
[`sw/example/coremark/`](https://github.com/stnolting/neorv32/tree/main/sw/example/coremark),
with these changes in `core_portme.c`/`.h`:

- interrupts stay enabled during the timed run, so the hardening interrupts
  can fire
- `ITERATIONS` is 3, for a short run
- no floating-point result output
- UART at 500000 baud
- a CRC over the printed characters

To change the firmware, build it in NEORV32 and replace
`hw/neorv32/neorv32_application_image.vhd` with the generated image.

## 6. Porting to a Different Board

1. Change `part_name` in `create_project.tcl`.
2. Replace `hw/xdc/basys3.xdc` with constraints for the board (clock, UART,
   GPIO/LED pins).
3. For a different input clock, set `CLK_IN_FREQUENCY` and the `clk_i`
   period in the XDC. `INTERNAL_CLOCK_FREQUENCY` (default 70 MHz) is the
   core clock that `clk_gen_wrapper` makes from `clk_i`.
4. Redraw `harness_pblock` in the XDC: its slice range is for the
   xc7a35t.

## 7. Directory Layout

Path | Contents
---- | --------
`hw/neorv32/` | NEORV32 files: `core/`, the top (`neorv32_test_setup_bootloader.vhd`) and the application image. Modified files are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
`hw/src/` | SolidKosmos sources: test harness, `clk_gen_wrapper`, parity/SECDED blocks.
`hw/xdc/` | Basys 3 constraints (`basys3.xdc`).
`create_project.tcl` | Creates the Vivado project.
`neorv_fi_example/` | The SK-RAFT fault-injection campaign.
`sw/hardening_coremark/` | The design-specific firmware source.
`images/` | The block diagram.

## 8. Known Limitations

- The DMEM decoder (`secded_dec8b`) corrects from the syndrome only and does
  not check the overall parity: a double-bit error can be miscorrected.
- The register-file SECDED covers the FPGA-style register file only, and a
  detected double-bit error is not reported yet. The ASIC-style register
  file (`CPU_RF_HW_RST_EN`) has no ECC.
- `HARDEN_EN => false` does not remove the CPU control/frontend hardening
  logic (see section 3).

## 9. License

SolidKosmos S.A. code (test harness, hardening blocks, Tcl, XDC, Python) is
licensed under Apache-2.0, see [LICENSE.md](../../LICENSE.md). The NEORV32
files and the firmware adapted from NEORV32 stay under the NEORV32
BSD-3-Clause license, see [LICENSE-NEORV32](LICENSE-NEORV32). The per-file
list is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## 10. References

- [NEORV32 RISC-V Processor](https://github.com/stnolting/neorv32) and its
  [data sheet](https://stnolting.github.io/neorv32)
- [Digilent Basys 3 Reference Manual](https://digilent.com/reference/programmable-logic/basys-3/reference-manual)
