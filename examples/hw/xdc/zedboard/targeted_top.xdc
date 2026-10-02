## zedboard constraints for targeted_top -- fast/slow heartbeat counters.

## Zynq PS is never instantiated -- clk_i is the board's dedicated
## 100MHz PL oscillator (bank 13, Y9), fully independent of the PS.

## Clock
set_property -dict { PACKAGE_PIN Y9 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5.00} [get_ports clk_i]

## Heartbeat LEDs (data_o[1]=fast, data_o[0]=slow)
set_property -dict { PACKAGE_PIN T22 IOSTANDARD LVCMOS33 } [get_ports {data_o[1]}]
set_property -dict { PACKAGE_PIN T21 IOSTANDARD LVCMOS33 } [get_ports {data_o[0]}]

## Configuration options
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Expose essential bits (needed for sk-raft's essential-bit-targeted examples)
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]


## Pblocks: isolate each heartbeat counter for pblock-confined fault injection
create_pblock pblock_fast_heartbeat
add_cells_to_pblock [get_pblocks pblock_fast_heartbeat] [get_cells -quiet [list fast_heartbeat]]
resize_pblock [get_pblocks pblock_fast_heartbeat] -add {SLICE_X32Y47:SLICE_X35Y52}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_fast_heartbeat]

create_pblock pblock_slow_heartbeat
add_cells_to_pblock [get_pblocks pblock_slow_heartbeat] [get_cells -quiet [list slow_heartbeat]]
resize_pblock [get_pblocks pblock_slow_heartbeat] -add {SLICE_X48Y46:SLICE_X51Y51}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_slow_heartbeat]