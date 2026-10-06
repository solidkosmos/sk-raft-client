## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## ZedBoard (xc7z020clg484-1) constraints for xadc_top: XADC temperature and
## supply monitor, read over BSCAN.

## The design does not instantiate the Zynq PS. clk_i is the dedicated
## 100 MHz PL oscillator of the board (bank 13, Y9). It is also the XADC DRP
## clock (DCLK). The XADC also measures the PS supplies (VCCPINT, VCCPAUX,
## VCCO_DDR). The PS does not have to operate for these measurements.
set_property -dict { PACKAGE_PIN Y9 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5.00} [get_ports clk_i]

## LEDs: LD0 = OT, LD1 = any alarm (ALM7), LD2 = heartbeat, LD3 = not used
set_property -dict {PACKAGE_PIN T22 IOSTANDARD LVCMOS33} [get_ports {data_o[0]}]
set_property -dict {PACKAGE_PIN T21 IOSTANDARD LVCMOS33} [get_ports {data_o[1]}]
set_property -dict {PACKAGE_PIN U22 IOSTANDARD LVCMOS33} [get_ports {data_o[2]}]
set_property -dict {PACKAGE_PIN U21 IOSTANDARD LVCMOS33} [get_ports {data_o[3]}]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of about 15 MHz)
create_clock -add -name bscan_clk_u1 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u1*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]
create_clock -add -name bscan_clk_u2 -period 66.667 -waveform {0 33.333} \
  [get_pins -of_objects [get_cells bscan_u2*/tck_BUFG_inst] -filter {REF_PIN_NAME==O}]

## The snapshot request goes through a two flip-flop synchronizer. The snapshot
## does not change during a JTAG read. Thus the two clock groups are asynchronous.
set_clock_groups -asynchronous \
  -group [get_clocks sys_clk_pin] \
  -group [get_clocks {bscan_clk_u1 bscan_clk_u2}]

## Configuration options. The PL is configured through JTAG, so the SPI
## configuration options of the Basys 3 do not apply.
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Same bitstream options as the SK-RAFT getting-started examples. Thus you can
## also use this design for fault injection.
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
