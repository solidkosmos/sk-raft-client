## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## Basys 3 constraints for ff_lut_top: FF shift register and LUTRAM, driven over BSCAN.

## Clock
set_property -dict { PACKAGE_PIN W5 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports clk_i]

## LEDs: bits 3:0 of the FF shift register (sr_len is 8 by default)
set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS33} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN E19 IOSTANDARD LVCMOS33} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN U19 IOSTANDARD LVCMOS33} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN V19 IOSTANDARD LVCMOS33} [get_ports {data_o[3]}]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of about 15 MHz)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u3 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u3*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u4 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u4*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

set_clock_groups -asynchronous \
  -group [get_clocks pll_clk_o] \
  -group [get_clocks {bscan_clk_u1 bscan_clk_u2 bscan_clk_u3 bscan_clk_u4}]

## Configuration options
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Write the EBD file (the SK-RAFT examples that target essential bits use it)
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Pblocks: isolate the LUTRAM from the FF shift register for pblock-confined fault injection
create_pblock pblock_LUTRAM
add_cells_to_pblock [get_pblocks pblock_LUTRAM] [get_cells -quiet [list LUTRAM]]
resize_pblock [get_pblocks pblock_LUTRAM] -add {SLICE_X30Y44:SLICE_X33Y52}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_LUTRAM]

create_pblock pblock_ff_sr_inst
add_cells_to_pblock [get_pblocks pblock_ff_sr_inst] [get_cells -quiet [list ff_sr_inst]]
resize_pblock [get_pblocks pblock_ff_sr_inst] -add {SLICE_X48Y48:SLICE_X51Y51}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_ff_sr_inst]
