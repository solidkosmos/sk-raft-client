## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## CUSTOM BOARD TEMPLATE for xadc_top: XADC temperature and supply monitor,
## read over BSCAN. Use it for a 7-series FPGA or Zynq-7000 board.
## 1. Copy this file to xdc/<your_board_name>.xdc.
## 2. Fill the PACKAGE_PIN / IOSTANDARD placeholders below for your board.
## 3. Add an entry for <your_board_name> to board_info in build.tcl.
## clk_i is also the XADC DRP clock (DCLK). INIT_42 in xadc_top.vhd divides
## it by 4: ADCCLK = DCLK / 4. The maximum ADCCLK is 26 MHz. If your clock is
## more than 104 MHz, set a larger divider in INIT_42.

## Clock: replace PIN/IOSTD. Set PERIOD_NS to 1000 / clk_freq_MHz.
set_property -dict { PACKAGE_PIN <PIN> IOSTANDARD <IOSTD> } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period <PERIOD_NS> -waveform {0 <PERIOD_NS/2>} [get_ports clk_i]

## LEDs: data_o[0] = OT, data_o[1] = any alarm (ALM7), data_o[2] = heartbeat,
## data_o[3] = not used
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN <PIN> IOSTANDARD <IOSTD>} [get_ports {data_o[3]}]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of about 15 MHz)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

set_clock_groups -asynchronous \
  -group [get_clocks sys_clk_pin] \
  -group [get_clocks {bscan_clk_u1 bscan_clk_u2}]

## Configuration options: set CONFIG_VOLTAGE, CFGBVS, CONFIGRATE and
## CONFIG_MODE for your board. On a Zynq-7000 board, remove CONFIGRATE and
## CONFIG_MODE.
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
