## SPDX-License-Identifier: Apache-2.0
## Copyright (C) 2026 SOLIDKOSMOS S.A.

## Basys 3 constraints for targeted_top: feedback loop shift registers with parity generation.

## Clock
set_property -dict { PACKAGE_PIN W5 IOSTANDARD LVCMOS33 } [get_ports clk_i]
create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5} [get_ports clk_i]

## Parity LEDs (data_o[1]=sr_par_1 on LD1, data_o[0]=sr_par_0 on LD0)
set_property -dict { PACKAGE_PIN U16 IOSTANDARD LVCMOS33 } [get_ports {data_o[0]}]
set_property -dict { PACKAGE_PIN E19 IOSTANDARD LVCMOS33 } [get_ports {data_o[1]}]

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

## Pblocks: isolate each shift register for pblock-confined fault injection
create_pblock pblock_sr_0
add_cells_to_pblock [get_pblocks pblock_sr_0] [get_cells -quiet [list shift_reg_0]]
resize_pblock [get_pblocks pblock_sr_0] -add {SLICE_X54Y91:SLICE_X57Y99}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_sr_0]

create_pblock pblock_sr_1
add_cells_to_pblock [get_pblocks pblock_sr_1] [get_cells -quiet [list shift_reg_1]]
resize_pblock [get_pblocks pblock_sr_1] -add {SLICE_X62Y56:SLICE_X65Y65}
set_property EXCLUDE_PLACEMENT 1 [get_pblocks pblock_sr_1]
