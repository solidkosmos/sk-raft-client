## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## Basys 3 constraints for mmcm_drp_interface_top: MMCM dynamic
## reconfiguration over BSCAN, two heartbeat LEDs on the MMCM outputs.
## Based on get_started/hw/xdc/basys3/targeted_top.xdc.

## Clock
set_property -dict { PACKAGE_PIN W5 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports clk_i]

## Heartbeat LEDs (led_o[0] = CLKOUT0, led_o[1] = CLKOUT1)
set_property -dict { PACKAGE_PIN U16 IOSTANDARD LVCMOS33 } [get_ports {led_o[0]}]
set_property -dict { PACKAGE_PIN E19 IOSTANDARD LVCMOS33 } [get_ports {led_o[1]}]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of about 15 MHz)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

## The board clock with the PLL and MMCM clocks made from it, and TCK, are
## asynchronous to each other.
set_clock_groups -asynchronous \
  -group [get_clocks -include_generated_clocks sys_clk_pin] \
  -group [get_clocks bscan_clk_u1]

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
