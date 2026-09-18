####################################################################################
# Company: SolidKosmos S.A.
#
# Script Name: create_project.tcl
# Description: Portable, device-agnostic project-creation script for
#              get_started_examples. Recreates the Vivado project from the
#              source files sitting next to this script (sources_1/new,
#              constrs_1) targeting whatever part and constraints file the
#              caller supplies -- nothing about the target device or board
#              is hardcoded here.
#
# Usage (Vivado batch mode, from anywhere):
#   vivado -mode batch -source create_project.tcl -tclargs <part> <xdc_path> [project_name] [project_dir]
#
# Required args:
#   <part>       Target FPGA part, e.g. xc7a35tcpg236-1
#   <xdc_path>   Path to your board's constraints (.xdc) file
#
# Optional args:
#   [project_name]  Defaults to "get_started_examples"
#   [project_dir]   Defaults to "./<project_name>" relative to the
#                    directory Vivado was launched from
#
# Example (Basys-3):
#   vivado -mode batch -source create_project.tcl -tclargs xc7a35tcpg236-1 C:/boards/Basys-3-Master.xdc
#
# NOTE ON TOP MODULE: this project holds several independent, self-contained
# example designs (adder_top, targeted_top, bscan_adder_top,
# dsp_target_top, ff_lut_top, brams_top) rather than one
# single top-level design. This script intentionally leaves the synthesis
# top unset -- after it runs, set whichever example you're building as the
# top yourself, e.g.:
#   set_property top adder_top [get_filesets sources_1]
#   update_compile_order -fileset sources_1
#
# NOTE ON DEVICE FAMILY: bram_sdp_native_wrapper.vhd, dsp_wrapper.vhd, and
# clk_gen_wrapper.vhd each take a g_family generic ("7SERIES", "ULTRASCALE",
# or "ULTRASCALEPLUS") that selects which primitive gets instantiated --
# RAMB36E1 vs RAMB36E2 in the BRAM wrapper, and PLLE2_BASE vs PLLE3_BASE vs
# PLLE4_BASE in clk_gen_wrapper. That generic is set in VHDL where each
# example instantiates the wrapper -- it is source-level, not a project
# property, so this script cannot set it for you. Make sure it matches the
# -part family you pass in below, for all three wrappers.
####################################################################################

# --- Parse arguments ---------------------------------------------------------
if { [llength $argv] < 2 } {
    puts "ERROR: missing required arguments."
    puts "Usage: vivado -mode batch -source create_project.tcl -tclargs <part> <xdc_path> \[project_name\] \[project_dir\]"
    exit 1
}

set part_name [lindex $argv 0]
set xdc_path  [file normalize [lindex $argv 1]]
set proj_name "get_started_examples"
set proj_dir  "./$proj_name"

if { [llength $argv] >= 3 } { set proj_name [lindex $argv 2] }
if { [llength $argv] >= 4 } { set proj_dir  [lindex $argv 3] }

if { ![file exists $xdc_path] } {
    puts "ERROR: XDC file not found: $xdc_path"
    exit 1
}

# --- Locate the source tree relative to this script itself -------------------
# (so this works no matter where the caller's CWD is, as long as this script
# stays next to sources_1/ and constrs_1/)
set script_dir [file dirname [file normalize [info script]]]
set src_dir    "$script_dir/sources_1/new"

if { ![file isdirectory $src_dir] } {
    puts "ERROR: expected source directory not found: $src_dir"
    puts "(this script must stay next to the sources_1/ folder it was shipped with)"
    exit 1
}

set vhdl_files {
    adder.vhd
    bram_sdp_native_wrapper.vhd
    bscan_interface.vhd
    bscan_primitive_wrapper.vhd
    bscan_user_register_io.vhd
    clk_gen_wrapper.vhd
    dsp_wrapper.vhd
    adder_top.vhd
    targeted_top.vhd
    bscan_adder_top.vhd
    dsp_target_top.vhd
    ff_lut_top.vhd
    brams_top.vhd
    examples_utilities_pkg.vhd
    heartbeat.vhd
    lut_memory_array.vhd
    secded_dec8b.vhd
    secded_enc8b.vhd
    single_adder.vhd
    sr_module.vhd
    tmr_adder.vhd
    vec_tmr_voter.vhd
}

set missing_files {}
foreach f $vhdl_files {
    if { ![file exists "$src_dir/$f"] } {
        lappend missing_files $f
    }
}
if { [llength $missing_files] > 0 } {
    puts "ERROR: missing expected source file(s) under $src_dir:"
    foreach f $missing_files { puts "  - $f" }
    exit 1
}

# --- Create the project -------------------------------------------------------
create_project $proj_name $proj_dir -part $part_name -force

set_property target_language     VHDL [current_project]
set_property simulator_language  VHDL [current_project]
set_property default_lib         xil_defaultlib [current_project]

# --- Add design sources --------------------------------------------------------
set src_paths {}
foreach f $vhdl_files {
    lappend src_paths "$src_dir/$f"
}
add_files -norecurse -fileset [get_filesets sources_1] $src_paths

# --- Add constraints -------------------------------------------------------------
add_files -fileset [get_filesets constrs_1] -norecurse $xdc_path
set_property target_constrs_file \
    [lindex [get_files -of_objects [get_filesets constrs_1] "*/[file tail $xdc_path]"] 0] \
    [get_filesets constrs_1]

update_compile_order -fileset sources_1

puts "----------------------------------------------------------------------"
puts "Project '$proj_name' created at '$proj_dir'"
puts "Part:        $part_name"
puts "Constraints: $xdc_path"
puts "No synthesis top module was set -- pick one of the top-level example"
puts "designs as your top before running synthesis (see header comment)."
puts "----------------------------------------------------------------------"

exit 0
