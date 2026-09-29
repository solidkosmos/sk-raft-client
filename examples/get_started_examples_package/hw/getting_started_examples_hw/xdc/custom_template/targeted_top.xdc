## CUSTOM BOARD TEMPLATE -- targeted_top: fast/slow heartbeat counters.
## Copy this whole folder to xdc/<your_board_name>/, fill in the PACKAGE_PIN /
## IOSTANDARD placeholders below for your board, then add an entry for
## <your_board_name> to device_info in create_project.tcl (part/family/clk_freq).

## Clock -- replace PIN/IOSTD, and PERIOD_NS = 1000 / clk_freq_MHz
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period <PERIOD_NS> -waveform {0 <PERIOD_NS/2>} [get_ports clk_i]

## Heartbeat LEDs (data_o[1]=fast, data_o[0]=slow)
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports {data_o[1]}]
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports {data_o[0]}]

## Configuration options -- 7-series shown; on UltraScale/UltraScale+ parts,
## delete CONFIG_VOLTAGE/CFGBVS (not valid there), keep the rest as-is.
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Expose essential bits (needed for sk-raft's essential-bit-targeted examples)
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Optional: pblocks isolating each heartbeat counter for pblock-confined
## fault injection (instance labels: fast_heartbeat / slow_heartbeat -- see
## targeted_top.vhd). Fill in real SLICE ranges for your part.
# create_pblock pblock_fast_heartbeat
# add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells -quiet [list fast_heartbeat]]
# resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_fast_heartbeat]
#
# create_pblock pblock_slow_heartbeat
# add_cells_to_pblock [get_pblocks pblock_slow_heartbeat] [get_cells -quiet [list slow_heartbeat]]
# resize_pblock [get_pblocks pblock_slow_heartbeat] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_slow_heartbeat]
