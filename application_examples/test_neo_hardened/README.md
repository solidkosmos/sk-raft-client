# NEORV32 hardening: a hardened RISC-V core under SK-RAFT fault injection

| Board | Part | License |
| --- | --- | --- |
| Digilent Basys 3 | xc7a35tcpg236-1 (Artix-7) | Apache-2.0 (SolidKosmos code), BSD-3-Clause (NEORV32) |

This example has a [NEORV32](https://github.com/stnolting/neorv32) RISC-V SoC
with SECDED and parity hardening, and a JTAG test harness for fault injection
with SK-RAFT. The hardening protects the DMEM, the register file, the state of
the CPU control FSM and the program counter. The `HARDEN_EN` generic selects a
hardened or an unhardened build of the same design. Thus you can measure the
effect of the hardening under fault injection.

![Block diagram of the example. The board clock goes through the safe clock generation PLL, a root clock gate (BSCAN USER3) and the cycle controller, which enables the clock for the number of cycles set over BSCAN USER2, then to the NEORV32. The tester (BSCAN USER1/USER2/USER3 and the cycle controller) sits in harness_pblock, which SK-RAFT does not inject into. Inside the NEORV32, the hardened modules (CPU control, CPU frontend, register file, DMEM) are grouped apart from the stock modules (IMEM, UART0, GPIO and the rest). USER1 resets the NEORV32 and reads the CRC word from its GPIO, the UART tx_busy keeps the clock running until the UART is idle, and ECC/parity events raise fast interrupts that print an [ALERT] on the UART.](images/neorv32_hardening_blocks.svg)

The NEORV32 boots the CoreMark firmware from the IMEM image
(`BOOT_MODE_SELECT => 2`). The image is in
`hw/neorv32/neorv32_application_image.vhd`. Thus the bitstream holds the
firmware, and you do not upload it separately.

## Build and run the example

1. From this folder, in the Vivado Tcl shell (or after `settings64.bat` /
   `settings64.sh` of Vivado), build the design:
   ```
   vivado -mode batch -source create_project.tcl
   ```
   The script creates `test_neo/test_neo.xpr` from `hw/` and builds it, from
   synthesis to bitstream (about 11 min on a laptop). Vivado writes the
   `.bit`, `.ebd` and `.ll` files to `test_neo/test_neo.runs/impl_1/`. The
   implementation run also runs the BRAM hold register pass (refer to "BRAM
   output latch protection"). The script prints the report of the pass,
   `bram_hold_pass.rpt`, which is in the same folder. The optional arguments
   are `-tclargs [project_name] [project_dir] [-gui]`. With `-gui`, the
   project opens in the Vivado GUI after the build.
2. Run the campaign with `neorv_fi_example/run_injection.py`. Refer to its
   [README](neorv_fi_example/README.md). The script programs the FPGA and
   reads the UART at 500000 baud.

For the unhardened baseline, remove the `#` from this line near the end of
`create_project.tcl`, and use a different project name:

```tcl
# set_property generic HARDEN_EN=false [get_filesets sources_1]
```

## The HARDEN_EN generic

The generic `HARDEN_EN : boolean := true` goes from
`neorv32_test_setup_bootloader` through `neorv32_top` and `neorv32_cpu` to
each modified file. With `HARDEN_EN => false`, the design operates as the
stock NEORV32:

- DMEM and register file (`neorv32_dmem.vhd`, `neorv32_prim.vhd`): the
  protected datapath and the plain datapath are in different `generate`
  branches. Thus a build with `HARDEN_EN => false` has no ECC hardware.
- CPU control and frontend (`neorv32_cpu_control.vhd`,
  `neorv32_cpu_frontend.vhd`): the SECDED and parity logic stays in the
  design. The generic only masks its effect on the execution and on the
  interrupts.

## Fault-injection test harness

The `tester` module connects three BSCAN USER registers to the cycle
controller (`clk_cycle_ctrlr`). The cycle controller gates the NEORV32 clock.

| Register | Write | Read |
| --- | --- | --- |
| USER1 | Design reset (active low) | 32-bit status and CRC word |
| USER2 | 32-bit step-count command | Current step count and status |
| USER3 | Root clock enable (1 = on) | The synchronized enable |

The USER2 commands are:

- A value other than 0 loads a cycle countdown.
- 0x1 starts the countdown.
- 0x2 cancels the countdown.

If the UART still sends data when the countdown ends, the controller keeps
the clock on until the UART is idle (`check_tx`). The root clock goes to the
NEORV32, the harness and the cycle controller. The root clock is off after
programming. `run_injection.py` stops it during each injection.

## BRAM output latch protection

Vivado makes the NEORV32 IMEM and DMEM from block RAMs. An SK-RAFT access to
BRAM content frames (readback, inject, revert) overwrites the output latch of
each block RAM port without an output register. The stored content does not
change. Without protection, the core can use that wrong value instead of the
word that it read before the freeze.

`create_project.tcl` sets the BRAM hold register pass
([`auxiliary_components/bram_hold_pass`](../../auxiliary_components/bram_hold_pass/README.md))
as the hook before `opt_design`. The pass adds a register on the opposite
clock edge behind each BRAM output in use. This register keeps the word that
the core read before the freeze. After the build, examine
`bram_hold_pass.rpt`. The report lists each block RAM and the change that the
pass made. The clock gates of the harness are BUFGCEs. A BUFGCE stops low, as
the pass requires.

The paths from a hold register to the logic on the BRAM clock edge have half
a clock period. The paths from the register file BRAM through the ECC decoder
and the ALU do not meet 70 MHz with half a period. Thus the default core
clock is 40 MHz.

## Firmware

`sw/hardening_coremark/main.c` is the part of the firmware that is specific to
this design. It installs the fast-interrupt handlers of the hardening (DMEM
and register file corrections, CPU control and frontend state, PC and RA
parity). Then it runs CoreMark. The other files come from the NEORV32
[`sw/example/coremark/`](https://github.com/stnolting/neorv32/tree/main/sw/example/coremark),
with these changes in `core_portme.c` and `core_portme.h`:

- The interrupts stay enabled during the timed run, so that the hardening
  interrupts can occur.
- `ITERATIONS` is 3, for a short run.
- The firmware does not print the floating-point results.
- The UART runs at 500000 baud.
- The firmware calculates a CRC over the printed characters.

To change the firmware, build it in NEORV32. Then replace
`hw/neorv32/neorv32_application_image.vhd` with the image that NEORV32 makes.

## Use another board

1. Change `part_name` in `create_project.tcl`.
2. Replace `hw/xdc/basys3.xdc` with the constraints of your board (clock,
   UART, GPIO and LED pins).
3. For a different input clock, set `CLK_IN_FREQUENCY` and the `clk_i` period
   in the XDC. `INTERNAL_CLOCK_FREQUENCY` (default 40 MHz, refer to "BRAM
   output latch protection") is the core clock that `clk_gen_wrapper` makes
   from `clk_i`.
4. Change `harness_pblock` in the XDC. Its slice range is for the xc7a35t.

## Files

| Path | Contents |
| --- | --- |
| `hw/neorv32/` | NEORV32 files: `core/`, the top (`neorv32_test_setup_bootloader.vhd`) and the application image. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) lists the modified files. |
| `hw/src/` | SolidKosmos sources: test harness, parity and SECDED blocks. The build adds the BSCAN files and `clk_gen_wrapper` from `auxiliary_components/`. |
| `hw/xdc/` | Basys 3 constraints (`basys3.xdc`). |
| `create_project.tcl` | Creates the Vivado project, with the BRAM hold register pass from `../../auxiliary_components/bram_hold_pass/`. |
| `neorv_fi_example/` | The SK-RAFT fault-injection campaign. |
| `sw/hardening_coremark/` | The firmware source that is specific to this design. |
| `images/` | The block diagram. |

## Known limits

- The DMEM decoder (`secded_dec8b`) corrects from the syndrome only. It does
  not check the overall parity. Thus it can correct a double-bit error
  incorrectly.
- The register file SECDED covers only the FPGA-style register file. It does
  not report a detected double-bit error yet. The ASIC-style register file
  (`CPU_RF_HW_RST_EN`) has no ECC.
- `HARDEN_EN => false` does not remove the hardening logic of the CPU control
  and frontend (refer to "The HARDEN_EN generic").

## License

The Apache License 2.0 applies to the SolidKosmos S.A. code (test harness,
hardening blocks, Tcl, XDC, Python). Refer to [LICENSE.md](../../LICENSE.md).
The NEORV32 BSD 3-Clause License applies to the NEORV32 files and to the
firmware that comes from NEORV32. Refer to [LICENSE-NEORV32](LICENSE-NEORV32).
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) has the list of files.

## References

- [NEORV32 RISC-V Processor](https://github.com/stnolting/neorv32) and its
  [data sheet](https://stnolting.github.io/neorv32)
- [Digilent Basys 3 Reference Manual](https://digilent.com/reference/programmable-logic/basys-3/reference-manual)
