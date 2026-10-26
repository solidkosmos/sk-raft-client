################################################################################
# Company: SolidKosmos S.A.
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
# Script Name: create_project.tcl
#
# Usage: vivado -mode batch -source create_project.tcl
#            -tclargs [project_name] [project_dir]
# Example: vivado -mode batch -source create_project.tcl
#
# The script creates the Vivado project of the MMCM dynamic reconfiguration
# example for the Digilent Basys 3 and builds it to a bitstream. It uses the
# sources and the constraints in hw/ and the shared components in
# auxiliary_components/ at the root of the repository, and sets
# mmcm_drp_interface_top as the top. The default project is
# mmcm_drp_interface/mmcm_drp_interface.xpr next to this script.
# src/main.py reads the .bit file from
# mmcm_drp_interface/mmcm_drp_interface.runs/impl_1/.
#
# The script was written for Vivado 2025.2.
################################################################################

# Target part and top. To use another 7-series board, change the part and the
# XDC file. For UltraScale or UltraScale+, also change g_family below.
set part_name  xc7a35tcpg236-1
set top        mmcm_drp_interface_top
set family     7SERIES

if { [llength $argv] > 2 } {
    puts "ERROR: too many arguments."
    puts "Usage: vivado -mode batch -source create_project.tcl\
        -tclargs \[project_name\] \[project_dir\]"
    exit 1
}

# The default project directory is next to this script (not the directory
# where you start Vivado), so that main.py finds the .bit file.
set script_dir [file dirname [file normalize [info script]]]
set proj_name "mmcm_drp_interface"
set proj_dir  "$script_dir/$proj_name"

# A project name without a directory gets its own default directory. Thus
# two different builds never share the same project directory.
if { [llength $argv] >= 1 } {
    set proj_name [lindex $argv 0]
    set proj_dir  "$script_dir/$proj_name"
}
if { [llength $argv] >= 2 } { set proj_dir  [lindex $argv 1] }

set part_obj [get_parts -quiet $part_name]
if { $part_obj eq "" } {
    puts "ERROR: unknown/invalid part '$part_name' --"
    puts "check the part name at the top of create_project.tcl."
    exit 1
}

set srcs_dir "$script_dir/hw"
set xdc_path "$srcs_dir/xdc/basys3.xdc"

# The shared components, relative to auxiliary_components/ at the root of
# the repository. The build uses these reference files directly.
set aux_dir [file normalize "$script_dir/../../auxiliary_components"]
set aux_files {
    bscan/bscan_interface.vhd
    bscan/bscan_primitive_wrapper.vhd
    bscan/bscan_user_register_io.vhd
    safe_clk_gen/clk_gen_wrapper.vhd
}

# The VHDL sources, relative to hw/
set vhdl_files {
    src/heartbeat.vhd
    src/mmcm_wrapper.vhd
    src/DRP_control.vhd
    src/mmcm_drp_interface_top.vhd
}

set missing_files {}
foreach f $vhdl_files {
    if { ![file exists "$srcs_dir/$f"] } {
        lappend missing_files "$srcs_dir/$f"
    }
}
foreach f $aux_files {
    if { ![file exists "$aux_dir/$f"] } {
        lappend missing_files "$aux_dir/$f"
    }
}
if { ![file exists $xdc_path] } {
    lappend missing_files $xdc_path
}
if { [llength $missing_files] > 0 } {
    puts "ERROR: missing expected file(s):"
    foreach f $missing_files { puts "  - $f" }
    exit 1
}

create_project $proj_name $proj_dir -part $part_name -force

set_property target_language     VHDL [current_project]
set_property simulator_language  VHDL [current_project]

set src_paths {}
foreach f $vhdl_files {
    lappend src_paths "$srcs_dir/$f"
}
foreach f $aux_files {
    lappend src_paths "$aux_dir/$f"
}
add_files -norecurse -fileset [get_filesets sources_1] $src_paths

add_files -fileset [get_filesets constrs_1] -norecurse $xdc_path
set xdc_file [lindex [get_files -of_objects [get_filesets constrs_1] \
    "*/[file tail $xdc_path]"] 0]
set_property target_constrs_file $xdc_file [get_filesets constrs_1]

set_property top $top [get_filesets sources_1]
# g_family is a VHDL string generic: the value includes the quotes.
set_property generic "g_family=\"$family\"" [get_filesets sources_1]
update_compile_order -fileset sources_1

puts "----------------------------------------------------------------------"
puts "Project '$proj_name' created at '$proj_dir'"
puts "Part:        $part_name"
puts "Top:         $top (g_family = $family)"
puts "Constraints: $xdc_path"
puts "----------------------------------------------------------------------"

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if { [get_property PROGRESS [get_runs synth_1]] != "100%" } {
    puts "ERROR: synth_1 did not complete -- see\
        $proj_dir/$proj_name.runs/synth_1/runme.log"
    exit 1
}

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
set bit_path "$proj_dir/$proj_name.runs/impl_1/$top.bit"
if { ![file exists $bit_path] } {
    puts "ERROR: impl_1 did not write the bitstream -- see\
        $proj_dir/$proj_name.runs/impl_1/runme.log"
    exit 1
}

puts "----------------------------------------------------------------------"
puts "Bitstream written: $bit_path"
puts "Run the script: cd src; python main.py"
puts "----------------------------------------------------------------------"
