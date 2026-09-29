## CUSTOM BOARD TEMPLATE -- bscan_adder_top: simplex vs. TMR adder, driven over BSCAN (no clk_i --
## runs off the JTAG/BSCAN clock domain).
## Copy this whole folder to xdc/<your_board_name>/, fill in the PACKAGE_PIN /
## IOSTANDARD placeholders below for your board, then add an entry for
## <your_board_name> to device_info in create_project.tcl (part/family/clk_freq).

## Status LEDs: min_vote (data_o[2:0]), total_fail (data_o[3])
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[3]}]

## TCK, buffered through BUFG, treated as its own clock domain (~15 MHz JTAG rate)
## (no clk_i/PLL in this design to group against -- these 3 are the only
## clocks that exist here)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u3 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u3*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

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

## Optional: pblocks isolating the simplex adder from the TMR adder for
## pblock-confined fault injection (instance labels: sngl_add / tmr_add --
## see bscan_adder_top.vhd). Fill in real SLICE ranges for your part.
# create_pblock pblock_sngl_add
# add_cells_to_pblock [get_pblocks pblock_sngl_add] [get_cells -quiet [list sngl_add]]
# resize_pblock [get_pblocks pblock_sngl_add] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_sngl_add]
#
# create_pblock pblock_tmr_add
# add_cells_to_pblock [get_pblocks pblock_tmr_add] [get_cells -quiet [list tmr_add]]
# resize_pblock [get_pblocks pblock_tmr_add] -add {SLICE_X<x0>Y<y0>:SLICE_X<x1>Y<y1>}
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_tmr_add]
