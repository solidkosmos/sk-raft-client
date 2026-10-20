################################################################################
# Company: SolidKosmos S.A.
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Constraints of the 7-series SEM arbitration example (top:
# sem_arbitration_7series) for the Digilent Basys 3 (xc7a35tcpg236-1).
################################################################################

# Clock: 100 MHz oscillator
set_property -dict {PACKAGE_PIN W5 IOSTANDARD LVCMOS33} [get_ports clk_i]
create_clock -period 10.000 -name sys_clk_pin -waveform {0.000 5.000} \
    -add [get_ports clk_i]

# BSCAN TCK clocks (USER1 to USER3), 15 MHz. The JTAG domain is
# asynchronous to the design clock.
create_clock -period 66.667 -name bscan_clk_u1 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u1_clk_en/tck_BUFG_inst]]
create_clock -period 66.667 -name bscan_clk_u2 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u2_icap_grant/tck_BUFG_inst]]
create_clock -period 66.667 -name bscan_clk_u3 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u3_sem_status/tck_BUFG_inst]]
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks sys_clk_pin] \
    -group [get_clocks {bscan_clk_u1 bscan_clk_u2 bscan_clk_u3}]

# LEDs LD0, LD1, LD2 and LD15
set_property -dict {PACKAGE_PIN U16 IOSTANDARD LVCMOS33} \
    [get_ports icap_request_o]
set_property -dict {PACKAGE_PIN E19 IOSTANDARD LVCMOS33} \
    [get_ports status_heartbeat_o]
set_property -dict {PACKAGE_PIN U19 IOSTANDARD LVCMOS33} \
    [get_ports status_initialization_o]
set_property -dict {PACKAGE_PIN L1 IOSTANDARD LVCMOS33} [get_ports sem_idle_o]

# USB-UART (SEM monitor, 9600 8-N-1)
set_property -dict {PACKAGE_PIN B18 IOSTANDARD LVCMOS33} [get_ports rx_i]
set_property -dict {PACKAGE_PIN A18 IOSTANDARD LVCMOS33} [get_ports tx_o]

# Configuration
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property CONFIG_MODE SPIx4 [current_design]

# Bitstream settings for SK-RAFT and the SEM: readback is allowed, the EBD
# file (essential bits) is written, and each frame has a CRC.
set_property BITSTREAM.READBACK.SECURITY NONE [current_design]
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]

# The SEM controller (u_sem) in its own pblock. No other logic goes into
# this area. SK-RAFT can target the SEM with pblock="pblock_sem".
create_pblock pblock_sem
add_cells_to_pblock [get_pblocks pblock_sem] [get_cells -quiet [list u_sem]]
resize_pblock [get_pblocks pblock_sem] -add {SLICE_X8Y15:SLICE_X15Y34 \
                                             DSP48_X0Y6:DSP48_X0Y13 \
                                             RAMB18_X0Y6:RAMB18_X0Y13 \
                                             RAMB36_X0Y3:RAMB36_X0Y6}
set_property IS_SOFT FALSE [get_pblocks pblock_sem]
set_property EXCLUDE_PLACEMENT true [get_pblocks pblock_sem]
