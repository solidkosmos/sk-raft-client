####################################################################################
# Company: SolidKosmos S.A.
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
# Script Name: create_project.tcl
#
# Usage: vivado -mode batch -source create_project.tcl -tclargs <device> <top> [project_name] [project_dir] [-gui]
# Example: vivado -mode batch -source create_project.tcl -tclargs basys3 brams_top
# Add -gui (at any position in the arguments) to open the built project in
# the Vivado GUI at the end. The script then does not exit, and you can
# examine or change the project.
#
# The script finds the part and clk_freq of <device> and the file
# xdc/<device>/<top>.xdc. It creates the project and sets <top> as the
# synthesis top. It gets g_family directly from the ARCHITECTURE property of
# the part in Vivado (you supply only the part and clk_freq). Then it builds
# the project to a bitstream and copies the design files to
# design_examples/<device>/<top>/ (see the end of this script).
####################################################################################

# device -> {part, clk_freq (MHz)}. The script gets the family from the part
# (see below). The family is not stored here.
array set device_info {
    basys3   {part xc7a35tcpg236-1 clk_freq 100}
    zedboard {part xc7z020clg484-1 clk_freq 100}
}
# Only basys3 (Basys 3) and zedboard (ZedBoard) are tested and supplied with
# this suite. To add your own board:
#   1. cp -r xdc/custom_template xdc/<your_board_name>
#   2. Fill the PACKAGE_PIN/IOSTANDARD placeholders in each .xdc file in
#      that folder (and the pblock SLICE/RAMB ranges, if you use pblocks).
#   3. Add an entry here, for example:
#        my_board {part xc7a100tcsg324-1 clk_freq 100}
# The build then creates design_examples/<your_board_name>/ for the files.

set known_tops {
    targeted_top
    bscan_adder_top
    ff_lut_top
    brams_top
}

# Tops with g_family/clk_freq generics (bscan_adder_top has neither, only op_len)
set tops_with_device_generics {
    targeted_top
    ff_lut_top
    brams_top
}

# Optional -gui flag (at any position in tclargs): open the project in the
# Vivado GUI at the end, and do not exit. You can then examine or change the
# project. Remove the flag before the script parses the positional arguments.
set gui_requested 0
set filtered_argv {}
foreach a $argv {
    if { $a eq "-gui" } {
        set gui_requested 1
    } else {
        lappend filtered_argv $a
    }
}
set argv $filtered_argv

proc finish {code} {
    global gui_requested
    if { $gui_requested } {
        puts "----------------------------------------------------------------------"
        puts "Opening project in the Vivado GUI for further inspection/manipulation..."
        puts "----------------------------------------------------------------------"
        start_gui
    } else {
        exit $code
    }
}

if { [llength $argv] < 2 } {
    puts "ERROR: missing required arguments."
    puts "Usage: vivado -mode batch -source create_project.tcl -tclargs <device> <top> \[project_name\] \[project_dir\] \[-gui\]"
    puts "Known devices: [lsort [array names device_info]]"
    puts "Known tops:    $known_tops"
    exit 1
}

set device    [lindex $argv 0]
set top       [lindex $argv 1]
# The default proj_name/proj_dir use device and top as keys. Thus two
# different builds never share the same project directory (and never reuse
# or corrupt it without a message). Give arguments 3 and 4 to override them.
set proj_name "get_started_examples_${device}_${top}"
set proj_dir  "./$proj_name"

if { [llength $argv] >= 3 } { set proj_name [lindex $argv 2] }
if { [llength $argv] >= 4 } { set proj_dir  [lindex $argv 3] }

if { ![info exists device_info($device)] } {
    puts "ERROR: unknown device '$device'."
    puts "Known devices: [lsort [array names device_info]]"
    exit 1
}
set part_name        [dict get $device_info($device) part]
set device_clk_freq  [dict get $device_info($device) clk_freq]

# Get g_family directly from the part database of Vivado. The user does not
# supply it. get_parts/get_property operate without a project, so a project
# is not necessary yet.
set part_obj [get_parts -quiet $part_name]
if { $part_obj eq "" } {
    puts "ERROR: unknown/invalid part '$part_name' for device '$device' --"
    puts "check the part name in device_info."
    exit 1
}
set part_arch [string tolower [get_property ARCHITECTURE $part_obj]]
switch -exact -- $part_arch {
    artix7 - artix7l - kintex7 - kintex7l - virtex7 - virtex7l - zynq {
        set device_family "7SERIES"
    }
    kintexu - virtexu {
        set device_family "ULTRASCALE"
    }
    kintexuplus - virtexuplus - zynquplus - zynquplusrfsoc {
        set device_family "ULTRASCALEPLUS"
    }
    default {
        puts "ERROR: part '$part_name' has ARCHITECTURE '$part_arch', which"
        puts "this suite doesn't recognize as 7SERIES/ULTRASCALE/ULTRASCALEPLUS."
        puts "Add a case for '$part_arch' to the switch in create_project.tcl."
        exit 1
    }
}

if { [lsearch -exact $known_tops $top] < 0 } {
    puts "ERROR: unknown top '$top'."
    puts "Known tops: $known_tops"
    exit 1
}

set script_dir [file dirname [file normalize [info script]]]
set src_dir    "$script_dir/sources_1/new"
set xdc_path   "$script_dir/xdc/$device/$top.xdc"

if { ![file isdirectory $src_dir] } {
    puts "ERROR: expected source directory not found: $src_dir"
    exit 1
}

if { ![file exists $xdc_path] } {
    puts "ERROR: no bundled XDC for device '$device' + top '$top' at:"
    puts "  $xdc_path"
    exit 1
}

set vhdl_files {
    adder.vhd
    bram_sdp_native_wrapper.vhd
    bscan_interface.vhd
    bscan_primitive_wrapper.vhd
    bscan_user_register_io.vhd
    clk_gen_wrapper.vhd
    targeted_top.vhd
    bscan_adder_top.vhd
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

create_project $proj_name $proj_dir -part $part_name -force

set_property target_language     VHDL [current_project]
set_property simulator_language  VHDL [current_project]
set_property default_lib         xil_defaultlib [current_project]

set src_paths {}
foreach f $vhdl_files {
    lappend src_paths "$src_dir/$f"
}
add_files -norecurse -fileset [get_filesets sources_1] $src_paths

add_files -fileset [get_filesets constrs_1] -norecurse $xdc_path
set_property target_constrs_file \
    [lindex [get_files -of_objects [get_filesets constrs_1] "*/[file tail $xdc_path]"] 0] \
    [get_filesets constrs_1]

set_property top $top [get_filesets sources_1]
update_compile_order -fileset sources_1

# g_family is a VHDL string generic. The value must include the literal quotes
# (g_family=\"7SERIES\"), not only the bare text. clk_freq is an integer without quotes.
set generics_set 0
if { [lsearch -exact $tops_with_device_generics $top] >= 0 } {
    set_property generic "g_family=\"$device_family\" clk_freq=$device_clk_freq" [get_filesets sources_1]
    set generics_set 1
}

puts "----------------------------------------------------------------------"
puts "Project '$proj_name' created at '$proj_dir'"
puts "Device:      $device ($part_name)"
puts "Top:         $top"
puts "Constraints: $xdc_path"
if { $generics_set } {
    puts "Generics:    g_family=$device_family clk_freq=$device_clk_freq (from device table)"
} else {
    puts "Generics:    $top has no g_family/clk_freq -- using its own VHDL defaults"
}
puts "----------------------------------------------------------------------"

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if { [get_property PROGRESS [get_runs synth_1]] != "100%" } {
    puts "ERROR: synth_1 did not complete -- see $proj_dir/$proj_name.runs/synth_1/runme.log"
    finish 1
    return
}

# Always request the logic location file together with the .bit file. The
# file is harmless for the tops that do not use it (targeted_top,
# bscan_adder_top). The other tops must have it (ff_lut_top, brams_top).
set_property STEPS.WRITE_BITSTREAM.ARGS.LOGIC_LOCATION_FILE true [get_runs impl_1]

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if { [get_property PROGRESS [get_runs impl_1]] != "100%" } {
    puts "ERROR: impl_1 did not complete -- see $proj_dir/$proj_name.runs/impl_1/runme.log"
    finish 1
    return
}

set impl_dir  "$proj_dir/$proj_name.runs/impl_1"
set bit_path  "$impl_dir/$top.bit"
set ebd_path  "$impl_dir/$top.ebd"
set ll_path   "$impl_dir/$top.ll"

if { ![file exists $bit_path] } {
    puts "ERROR: expected bitstream not found at $bit_path"
    finish 1
    return
}

# top -> the example number N that uses this design.
# The script copies the design files (bit/ebd/ll and board.xdc) to
# design_examples/<device>/<top>/, next to this script. This is the same
# layout as the prebuilt files in design_examples.zip. If the folder does not
# exist (for example, for a new board), the script creates it. Files of a
# previous build or of the ZIP in that folder are overwritten.
array set top_to_example {
    targeted_top    1
    bscan_adder_top 2
    ff_lut_top      3
    brams_top       4
}

if { [info exists top_to_example($top)] } {
    set example_num  $top_to_example($top)
    set dest_dir      "$script_dir/design_examples/$device/$top"
    file mkdir $dest_dir

    file copy -force $bit_path "$dest_dir/$top.bit"
    set copied_files [list "$top.bit"]

    if { [file exists $ebd_path] } {
        file copy -force $ebd_path "$dest_dir/$top.ebd"
        lappend copied_files "$top.ebd"
    }
    if { [file exists $ll_path] } {
        file copy -force $ll_path "$dest_dir/$top.ll"
        lappend copied_files "$top.ll"
    }
    file copy -force $xdc_path "$dest_dir/board.xdc"
    lappend copied_files "board.xdc"

    puts "----------------------------------------------------------------------"
    puts "Bitstream written: $bit_path"
    puts "Example $example_num ready to run -- copied to [file normalize $dest_dir]:"
    foreach f $copied_files { puts "  - $f" }
    puts "----------------------------------------------------------------------"
} else {
    puts "----------------------------------------------------------------------"
    puts "Bitstream written: $bit_path"
    puts "NOTE: '$top' has no known example mapping -- design_examples/ not populated."
    puts "----------------------------------------------------------------------"
}

finish 0
