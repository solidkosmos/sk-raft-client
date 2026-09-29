## Basys-3 constraints for brams_top -- stock BRAM with byte-lane Hamming SEC,
## driven over BSCAN.

## Clock
set_property -dict { PACKAGE_PIN W5 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports clk_i]

## LEDs: 3 byte ECC-correction flags (data_o[3] unused)
set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS33} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN E19 IOSTANDARD LVCMOS33} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN U19 IOSTANDARD LVCMOS33} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN V19 IOSTANDARD LVCMOS33} [get_ports {data_o[3]}]

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

## Pblock: isolate the stock BRAM for pblock-confined fault injection
create_pblock pblock_stock_bram
add_cells_to_pblock [get_pblocks pblock_stock_bram] [get_cells -quiet [list stock_bram]]
resize_pblock [get_pblocks pblock_stock_bram] -add {RAMB18_X0Y12:RAMB18_X0Y13 \
                                                    RAMB36_X0Y6:RAMB36_X0Y6 \
}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_stock_bram]
