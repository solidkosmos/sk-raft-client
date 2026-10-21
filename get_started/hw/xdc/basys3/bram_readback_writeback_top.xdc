## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## Basys 3 constraints for bram_readback_writeback_top: one BRAM with the built-in
## ECC, driven over BSCAN.

## Clock
set_property -dict { PACKAGE_PIN W5 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports clk_i]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of about 15 MHz)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u3 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u3*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

set_clock_groups -asynchronous \
  -group [get_clocks pll_clk_o] \
  -group [get_clocks {bscan_clk_u1 bscan_clk_u2 bscan_clk_u3}]

## Configuration options
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Write the EBD file
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
## Add a CRC to each configuration frame. The device then checks each
## frame when it loads it.
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Exclude the BRAM from power optimization. The VHDL ties the read enable
## to 1. Without this line, opt_design gates the read enable, and the BRAM
## does not read again after the clock starts.
set_power_opt -exclude_cells [get_cells -hier -filter {REF_NAME =~ RAMB*}]
