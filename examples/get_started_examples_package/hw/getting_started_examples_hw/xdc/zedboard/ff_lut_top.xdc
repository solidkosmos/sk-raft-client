## zedboard constraints for ff_lut_top -- FF shift register + LUTRAM,
## driven over BSCAN.

## Zynq PS is never instantiated -- clk_i is the board's dedicated
## 100MHz PL oscillator (bank 13, Y9), fully independent of the PS.

## Clock
set_property -dict { PACKAGE_PIN Y9 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5.00} [get_ports clk_i]

## LEDs: 4 of the 8 FF shift-register bits
set_property -dict {PACKAGE_PIN T22 IOSTANDARD LVCMOS33} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN T21 IOSTANDARD LVCMOS33} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN U22 IOSTANDARD LVCMOS33} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN U21 IOSTANDARD LVCMOS33} [get_ports {data_o[3]}]

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

## NOTE: pblocks from the Basys3 XDCs are placement-specific to that
## device and are NOT ported here. Fault-injection examples that need a
## pblock on this board must have one added manually.

## Pblocks: isolate the LUTRAM from the FF shift register for pblock-confined fault injection
create_pblock pblock_LUTRAM
add_cells_to_pblock [get_pblocks pblock_LUTRAM] [get_cells -quiet [list LUTRAM]]
resize_pblock [get_pblocks pblock_LUTRAM] -add {SLICE_X82Y79:SLICE_X87Y82}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_LUTRAM]

create_pblock pblock_ff_sr_inst
add_cells_to_pblock [get_pblocks pblock_ff_sr_inst] [get_cells -quiet [list ff_sr_inst]]
resize_pblock [get_pblocks pblock_ff_sr_inst] -add {SLICE_X82Y75:SLICE_X83Y78}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_ff_sr_inst]