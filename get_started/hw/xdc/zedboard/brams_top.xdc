## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## ZedBoard constraints for brams_top: stock BRAM with byte-lane
## Hamming SEC, driven over BSCAN.

## The design does not instantiate the Zynq PS. clk_i is the dedicated
## 100 MHz PL oscillator of the board (bank 13, Y9), fully independent of the PS.

## Clock
set_property -dict { PACKAGE_PIN Y9 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5.00} [get_ports clk_i]

## LEDs: 3 byte ECC-correction flags (data_o[3] is not used)
set_property -dict {PACKAGE_PIN T22 IOSTANDARD LVCMOS33} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN T21 IOSTANDARD LVCMOS33} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN U22 IOSTANDARD LVCMOS33} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN U21 IOSTANDARD LVCMOS33} [get_ports {data_o[3]}]

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
## Add a CRC to each configuration frame. The device then checks each
## frame when it loads it.
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Note: This file does not use the Basys 3 pblocks, because their ranges
## are specific to that device. The pblocks below use ranges for the
## ZedBoard device.

## Pblock: isolate the stock BRAM for pblock-confined fault injection
create_pblock pblock_stock_bram
add_cells_to_pblock [get_pblocks pblock_stock_bram] [get_cells -quiet [list stock_bram]]
resize_pblock [get_pblocks pblock_stock_bram] -add {RAMB18_X4Y30:RAMB18_X4Y31 \
                                                    RAMB36_X4Y15:RAMB36_X4Y15 \
}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_stock_bram]

## Exclude the BRAMs from power optimization. Otherwise, Vivado adds
## gating logic to the BRAM enables.
set_power_opt -exclude_cells [get_cells -hier -filter {REF_NAME =~ RAMB*}]
