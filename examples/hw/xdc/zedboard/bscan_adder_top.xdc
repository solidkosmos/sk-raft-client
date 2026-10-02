## zedboard constraints for bscan_adder_top -- simplex vs. TMR adder,
## driven over BSCAN (no clk_i -- runs off the JTAG/BSCAN clock domain).

## Status LEDs: total_fail_o (data_o[3]), min_vote_o (data_o[2:0])
set_property -dict {PACKAGE_PIN T22 IOSTANDARD LVCMOS33} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN T21 IOSTANDARD LVCMOS33} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN U22 IOSTANDARD LVCMOS33} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN U21 IOSTANDARD LVCMOS33} [get_ports {data_o[3]}]

## TCK, buffered through BUFG, treated as its own clock domain (~15 MHz JTAG rate)
## (no clk_i/PLL in this design to group against -- these 3 are the only
## clocks that exist here)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u3 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u3*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

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

## NOTE: pblocks from the Basys3 XDCs are placement-specific to that
## device and are NOT ported here. Fault-injection examples that need a
## pblock on this board must have one added manually.

create_pblock pblock_sngl_add
add_cells_to_pblock [get_pblocks pblock_sngl_add] [get_cells -quiet [list sngl_add]]
resize_pblock [get_pblocks pblock_sngl_add] -add {SLICE_X32Y47:SLICE_X35Y52}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_sngl_add]

create_pblock pblock_tmr_add
add_cells_to_pblock [get_pblocks pblock_tmr_add] [get_cells -quiet [list tmr_add]]
resize_pblock [get_pblocks pblock_tmr_add] -add {SLICE_X48Y46:SLICE_X51Y51}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_tmr_add]