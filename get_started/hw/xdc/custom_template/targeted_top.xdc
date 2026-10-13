## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## CUSTOM BOARD TEMPLATE for targeted_top: fast and slow heartbeat counters.
## 1. Copy this full folder to xdc/<your_board_name>/.
## 2. Fill the PACKAGE_PIN / IOSTANDARD placeholders below for your board.
## 3. Add an entry for <your_board_name> to device_info in create_project.tcl
##    (part and clk_freq). The script gets the family from the part.

## Clock: replace PIN/IOSTD. Set PERIOD_NS to 1000 / clk_freq (MHz).
## Set <PERIOD_NS/2> to half of that value.
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period <PERIOD_NS> -waveform {0 <PERIOD_NS/2>} [get_ports clk_i]

## Heartbeat LEDs (data_o[1]=fast, data_o[0]=slow)
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports {data_o[1]}]
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports {data_o[0]}]

## Configuration options. Set CONFIG_VOLTAGE, CFGBVS, CONFIG_MODE and
## CONFIGRATE for your board. On UltraScale/UltraScale+ parts, delete
## CONFIG_VOLTAGE and CFGBVS (not valid there).
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Write the EBD file (the SK-RAFT examples that target essential bits use it)
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
## Add a CRC to each configuration frame. The device then checks each
## frame when it loads it.
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Optional: pblocks that isolate each heartbeat counter for pblock-confined
## fault injection (instance labels: fast_heartbeat / slow_heartbeat, see
## targeted_top.vhd). Set the real SLICE ranges for your part.
# create_pblock pblock_fast_heartbeat
# add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells -quiet [list fast_heartbeat]]
# resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_fast_heartbeat]
#
# create_pblock pblock_slow_heartbeat
# add_cells_to_pblock [get_pblocks pblock_slow_heartbeat] [get_cells -quiet [list slow_heartbeat]]
# resize_pblock [get_pblocks pblock_slow_heartbeat] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_slow_heartbeat]
