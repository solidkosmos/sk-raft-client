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
# The script creates the Vivado project of the 7-series SEM arbitration
# example for the Digilent Basys 3 and opens it in the Vivado GUI. It uses
# the sources and the constraints in hw/, creates the SEM IP (sem_0) and
# sets sem_arbitration_7series as the top. It does not build the project: run
# Generate Bitstream in the GUI. The bitstream run also writes the EBD file
# (BITSTREAM.SEU.ESSENTIALBITS in the XDC). The default project is
# sem_arbitration/sem_arbitration.xpr next to this script. ../src/main.py
# reads the .bit and .ebd files from sem_arbitration/sem_arbitration.runs/
# impl_1/.
#
# The script was written for Vivado 2025.2 (SEM IP sem 4.1).
################################################################################

# Target part and top. To use another 7-series board, change the part and the
# XDC file.
set part_name  xc7a35tcpg236-1
set top        sem_arbitration_7series

# Leave the Vivado GUI open on success; exit with an error code on failure
proc finish {code} {
    if { $code == 0 } {
        puts [string repeat "-" 70]
        puts "Opening the project in the Vivado GUI..."
        puts [string repeat "-" 70]
        # start_gui fails if the GUI is already open (script run from the GUI)
        catch { start_gui }
    } else {
        exit $code
    }
}

if { [llength $argv] > 2 } {
    puts "ERROR: too many arguments."
    puts "Usage: vivado -mode batch -source create_project.tcl\
        -tclargs \[project_name\] \[project_dir\]"
    exit 1
}

# The default project directory is next to this script (not the directory
# where you start Vivado), so that main.py finds the .bit and .ebd files.
set script_dir [file dirname [file normalize [info script]]]
set proj_name "sem_arbitration"
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

set srcs_dir   "$script_dir/hw"
set xdc_path   "$srcs_dir/xdc/basys3.xdc"

if { ![file isdirectory $srcs_dir] } {
    puts "ERROR: expected source directory not found: $srcs_dir"
    exit 1
}

if { ![file exists $xdc_path] } {
    puts "ERROR: expected constraints file not found:"
    puts "  $xdc_path"
    exit 1
}

# The shared components, relative to auxiliary_components/ at the root of
# the repository. The build uses these reference files directly.
set aux_dir [file normalize "$script_dir/../../../auxiliary_components"]
set aux_files {
    bscan/bscan_interface.vhd
    bscan/bscan_primitive_wrapper.vhd
    bscan/bscan_user_register_io.vhd
    safe_clk_gen/clk_gen_wrapper.vhd
}

# The VHDL sources, relative to hw/
set vhdl_files {
    src/examples_utilities_pkg.vhd
    src/fifo_mem.vhd
    src/rx_module.vhd
    src/tx_module.vhd
    src/uart_rx_tx.vhd
    src/monitor_interface.vhd
    src/sem_arbitration_7series.vhd
}

set missing_files {}
foreach f $vhdl_files {
    if { ![file exists "$srcs_dir/$f"] } {
        lappend missing_files $f
    }
}
foreach f $aux_files {
    if { ![file exists "$aux_dir/$f"] } {
        lappend missing_files "$aux_dir/$f"
    }
}
if { [llength $missing_files] > 0 } {
    puts "ERROR: missing expected source file(s) under $srcs_dir:"
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

# The SEM controller (PG036). The settings:
#   - correction on, with the repair method. Classification off.
#   - error injection off: SK-RAFT does the injections.
#   - no injection or retrieval shim: the commands and the reports go
#     through the monitor interface (UART).
#   - 100 MHz clock (icap_clk).
create_ip -name sem -vendor xilinx.com -library ip -version 4.1 \
    -module_name sem_0
set_property -dict [list \
    CONFIG.ENABLE_CORRECTION     {true} \
    CONFIG.CORRECTION_METHOD     {repair} \
    CONFIG.ENABLE_CLASSIFICATION {false} \
    CONFIG.ENABLE_INJECTION      {false} \
    CONFIG.INJECTION_SHIM        {none} \
    CONFIG.RETRIEVAL_SHIM        {none} \
    CONFIG.VALIDATE_DETECTION    {false} \
    CONFIG.CLOCK_FREQ            {100} \
] [get_ips sem_0]
generate_target {instantiation_template synthesis} [get_ips sem_0]

set_property top $top [get_filesets sources_1]
update_compile_order -fileset sources_1

puts "----------------------------------------------------------------------"
puts "Project '$proj_name' created at '$proj_dir'"
puts "Part:        $part_name"
puts "Top:         $top"
puts "Constraints: $xdc_path"
puts "----------------------------------------------------------------------"
puts "Run Generate Bitstream in the GUI. The .bit and .ebd files go to"
puts "  $proj_dir/$proj_name.runs/impl_1/"

finish 0
