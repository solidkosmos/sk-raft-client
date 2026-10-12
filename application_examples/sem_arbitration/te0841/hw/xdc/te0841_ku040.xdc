################################################################################
# Company: SolidKosmos S.A.
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# Constraints of the UltraScale SEM arbitration example (top:
# sem_arbitration_us) for the Trenz TE0841-02 (xcku040-sfva784-1-i).
################################################################################

set_property CFGBVS GND [current_design]
set_property CONFIG_VOLTAGE 1.8 [current_design]

# Board clock: 200 MHz oscillator U11, differential. No internal
# termination (see the TE0841 board file).
set_property PACKAGE_PIN R25 [get_ports clk_i_p]
set_property PACKAGE_PIN R26 [get_ports clk_i_n]
set_property IOSTANDARD LVDS [get_ports clk_i_p]
set_property IOSTANDARD LVDS [get_ports clk_i_n]
set_property DIFF_TERM_ADV TERM_NONE [get_ports clk_i_p]
set_property DIFF_TERM_ADV TERM_NONE [get_ports clk_i_n]
create_clock -period 5.000 -name sysclk_200 [get_ports clk_i_p]

# Enable of the oscillator (EN_OSC). The oscillator operates only when this
# pin is 1.
set_property PACKAGE_PIN AF24 [get_ports en_osc]
set_property IOSTANDARD LVCMOS33 [get_ports en_osc]

# UART 0 (SEM monitor, 9600 8-N-1)
set_property PACKAGE_PIN AG24 [get_ports tx_o]
set_property IOSTANDARD LVCMOS33 [get_ports tx_o]
set_property PACKAGE_PIN AH24 [get_ports rx_i]
set_property IOSTANDARD LVCMOS33 [get_ports rx_i]

# BSCAN TCK clocks (USER1 to USER3), 15 MHz. TCK goes through a BUFG in
# each bscan_interface instance.
create_clock -period 66.667 -name bscan_clk_u1 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u1_clk_en/tck_BUFG_inst]]
create_clock -period 66.667 -name bscan_clk_u2 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u2_cap/tck_BUFG_inst]]
create_clock -period 66.667 -name bscan_clk_u3 -waveform {0.000 33.333} \
    -add [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u3_sem_status/tck_BUFG_inst]]

# The TCK domains are asynchronous to the design clock. The design
# synchronizes each BSCAN bit with two flip-flops. The first group holds
# sysclk_200 and the clocks that come from it (safe_clk of the PLL and the
# gated sem_clk).
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks sysclk_200] \
    -group [get_clocks {bscan_clk_u1 bscan_clk_u2 bscan_clk_u3}]

# Bitstream settings for SK-RAFT and the SEM: readback is allowed, the EBD
# file (essential bits) is written, and each frame has a CRC.
set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
set_property BITSTREAM.READBACK.SECURITY None [current_design]
set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
set_property BITSTREAM.CONFIG.UNUSEDPIN PULLUP [current_design]

# The SEM controller (u_sem) in its own pblock. No other logic goes into
# this area. SK-RAFT can target the SEM with pblock="pblock_sem".
create_pblock pblock_sem
add_cells_to_pblock [get_pblocks pblock_sem] [get_cells -quiet [list u_sem]]
resize_pblock [get_pblocks pblock_sem] -add {SLICE_X81Y105:SLICE_X91Y119}
resize_pblock [get_pblocks pblock_sem] -add {DSP48E2_X15Y42:DSP48E2_X15Y47}
resize_pblock [get_pblocks pblock_sem] -add {RAMB18_X8Y42:RAMB18_X9Y47}
resize_pblock [get_pblocks pblock_sem] -add {RAMB36_X8Y21:RAMB36_X9Y23}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_sem]
