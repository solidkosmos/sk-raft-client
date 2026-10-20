## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.
##
## Basys 3 constraints for neorv32_test_setup_bootloader: hardened NEORV32
## under test, driven by the SK-RAFT cycle-stepping harness over BSCAN.

## Clock
set_property -dict {PACKAGE_PIN W5 IOSTANDARD LVCMOS33} [get_ports clk_i]
create_clock -period 10.000 -name sys_clk_pin -waveform {0.000 5.000} \
    -add [get_ports clk_i]

## TCK goes through a BUFG and is a separate clock domain (JTAG rate of
## about 15 MHz). The BUFGs sit inside the bscan_interface instances:
## USER1/USER2 in harness_controller, USER3 (root clock enable) in tester.
create_clock -period 66.667 -name bscan_clk_u1 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells clk_reset_ctrl/bscan/bscan_u1_crc_rst/tck_BUFG_inst]]
create_clock -period 66.667 -name bscan_clk_u2 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells clk_reset_ctrl/bscan/bscan_u2_step/tck_BUFG_inst]]
create_clock -period 66.667 -name bscan_clk_u3 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells clk_reset_ctrl/bscan_u3_root_clk_en/tck_BUFG_inst]]

## The JTAG TCK domains are asynchronous to the design clock. The design
## clock is the PLL output, which also feeds the gated NEORV32 clock.
set_clock_groups -asynchronous -group [get_clocks pll_clk_o] \
    -group [get_clocks {bscan_clk_u1 bscan_clk_u2 bscan_clk_u3}]

## LEDs: upper 16 bits of the NEORV32 GPIO output word
set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS33} [get_ports {gpio_o[0]}]
set_property -dict {PACKAGE_PIN E19 IOSTANDARD LVCMOS33} [get_ports {gpio_o[1]}]
set_property -dict {PACKAGE_PIN U19 IOSTANDARD LVCMOS33} [get_ports {gpio_o[2]}]
set_property -dict {PACKAGE_PIN V19 IOSTANDARD LVCMOS33} [get_ports {gpio_o[3]}]
set_property -dict {PACKAGE_PIN W18 IOSTANDARD LVCMOS33} [get_ports {gpio_o[4]}]
set_property -dict {PACKAGE_PIN U15 IOSTANDARD LVCMOS33} [get_ports {gpio_o[5]}]
set_property -dict {PACKAGE_PIN U14 IOSTANDARD LVCMOS33} [get_ports {gpio_o[6]}]
set_property -dict {PACKAGE_PIN V14 IOSTANDARD LVCMOS33} [get_ports {gpio_o[7]}]
set_property -dict {PACKAGE_PIN V13 IOSTANDARD LVCMOS33} [get_ports {gpio_o[8]}]
set_property -dict {PACKAGE_PIN V3 IOSTANDARD LVCMOS33} [get_ports {gpio_o[9]}]
set_property -dict {PACKAGE_PIN W3 IOSTANDARD LVCMOS33} [get_ports {gpio_o[10]}]
set_property -dict {PACKAGE_PIN U3 IOSTANDARD LVCMOS33} [get_ports {gpio_o[11]}]
set_property -dict {PACKAGE_PIN P3 IOSTANDARD LVCMOS33} [get_ports {gpio_o[12]}]
set_property -dict {PACKAGE_PIN N3 IOSTANDARD LVCMOS33} [get_ports {gpio_o[13]}]
set_property -dict {PACKAGE_PIN P1 IOSTANDARD LVCMOS33} [get_ports {gpio_o[14]}]
set_property -dict {PACKAGE_PIN L1 IOSTANDARD LVCMOS33} [get_ports {gpio_o[15]}]

## Harness debug outputs (7-segment segments CA and CB)
set_property -dict {PACKAGE_PIN W7 IOSTANDARD LVCMOS33} [get_ports clk_en_led]
set_property -dict {PACKAGE_PIN W6 IOSTANDARD LVCMOS33} [get_ports rst_led]

## USB-RS232 interface
set_property -dict {PACKAGE_PIN B18 IOSTANDARD LVCMOS33} [get_ports uart0_rxd_i]
set_property -dict {PACKAGE_PIN A18 IOSTANDARD LVCMOS33} [get_ports uart0_txd_o]

## Configuration options
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]

## Write the EBD file and keep the per-frame CRC. SK-RAFT injections need both.
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

## Pblock: keep the harness (instance clk_reset_ctrl, the tester) in its own
## region. run_injection.py excludes harness_pblock, so SK-RAFT does not
## inject into the harness. EXCLUDE_PLACEMENT keeps all other logic out of
## the region. Do not rename clk_reset_ctrl, because this constraint uses
## that name (see neorv32_test_setup_bootloader.vhd).
create_pblock harness_pblock
add_cells_to_pblock [get_pblocks harness_pblock] \
    [get_cells -quiet [list clk_reset_ctrl]]
resize_pblock [get_pblocks harness_pblock] -add {SLICE_X28Y16:SLICE_X31Y28}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks harness_pblock]

## Keep BRAM enables ungated
set_power_opt -exclude_cells [get_cells -hier -filter {REF_NAME =~ RAMB*}]


