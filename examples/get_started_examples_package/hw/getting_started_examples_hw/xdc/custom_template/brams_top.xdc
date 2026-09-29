## CUSTOM BOARD TEMPLATE -- brams_top: stock BRAM with byte-lane Hamming SEC, driven over BSCAN.
## Copy this whole folder to xdc/<your_board_name>/, fill in the PACKAGE_PIN /
## IOSTANDARD placeholders below for your board, then add an entry for
## <your_board_name> to device_info in create_project.tcl (part/family/clk_freq).

## Clock -- replace PIN/IOSTD, and PERIOD_NS = 1000 / clk_freq_MHz
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period <PERIOD_NS> -waveform {0 <PERIOD_NS/2>} [get_ports clk_i]

## LEDs: 3 byte ECC-correction flags (data_o[3] unused)
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[3]}]

## TCK, buffered through BUFG, treated as its own clock domain (~15 MHz JTAG rate)
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

## Optional: pblock isolating the stock BRAM for pblock-confined fault
## injection (instance label: stock_bram -- see brams_top.vhd). Fill in
## real RAMB18/RAMB36 ranges for your part.
# create_pblock pblock_stock_bram
# add_cells_to_pblock [get_pblocks pblock_stock_bram] [get_cells -quiet [list stock_bram]]
# resize_pblock [get_pblocks pblock_stock_bram] -add {RAMB18_X<x0>Y<y0>:RAMB18_X<x1>Y<y1> \
#                                                     RAMB36_X<x0>Y<y0>:RAMB36_X<x1>Y<y1> \
# }
# set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_stock_bram]
