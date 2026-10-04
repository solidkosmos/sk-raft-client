## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## CUSTOM BOARD TEMPLATE for bscan_adder_top: simplex adder and TMR adder, driven over
## BSCAN. This top has no clk_i. All clocked logic uses the JTAG/BSCAN clock domain.
## 1. Copy this full folder to xdc/<your_board_name>/.
## 2. Fill the PACKAGE_PIN / IOSTANDARD placeholders below for your board.
## 3. Add an entry for <your_board_name> to device_info in create_project.tcl
##    (part and clk_freq). The script gets the family from the part.

## Status LEDs: total_fail_o (data_o[3]), min_vote_o (data_o[2:0])
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[3]}]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of about 15 MHz)
## (This design has no clk_i or PLL clock for a clock group. These 3 clocks
## are the only clocks in the design.)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u3 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u3*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

## Configuration options for 7-series parts. On UltraScale/UltraScale+ parts,
## delete CONFIG_VOLTAGE/CFGBVS (not valid there). Keep the other options.
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Write the EBD file (the SK-RAFT examples that target essential bits use it)
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Optional: pblocks that isolate the simplex adder from the TMR adder for
## pblock-confined fault injection (instance labels: sngl_add / tmr_add, see
## bscan_adder_top.vhd). Set the real SLICE ranges for your part.
# create_pblock pblock_sngl_add
# add_cells_to_pblock [get_pblocks pblock_sngl_add] [get_cells -quiet [list sngl_add]]
# resize_pblock [get_pblocks pblock_sngl_add] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_sngl_add]
#
# create_pblock pblock_tmr_add
# add_cells_to_pblock [get_pblocks pblock_tmr_add] [get_cells -quiet [list tmr_add]]
# resize_pblock [get_pblocks pblock_tmr_add] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_tmr_add]
