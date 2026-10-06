####################################################################################
# Company: SolidKosmos S.A.
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
# Script Name: build.tcl
#
# Usage:   vivado -mode batch -source build.tcl -tclargs <board> [-gui]
# Example: vivado -mode batch -source build.tcl -tclargs zedboard
#
# The script builds xadc_top for <board>, from synthesis to bitstream. Then it
# runs report_power on the implemented design. It copies these files to
# ../src/design_files/:
#   - xadc_top.bit        The bitstream.
#   - xadc_top.ebd        The essential bits, if Vivado writes the file.
#   - xadc_top_power.rpt  The Vivado power estimate (report_power).
# Add -gui (at any position in the arguments) to open the project in the
# Vivado GUI at the end. The script then does not exit.
####################################################################################

# board -> part. The script gets g_zynq from the ARCHITECTURE of the part.
array set board_info {
    basys3   {part xc7a35tcpg236-1}
    zedboard {part xc7z020clg484-1}
}
# To add your own board:
#   1. cp xdc/custom_template.xdc xdc/<your_board_name>.xdc
#   2. Fill the PACKAGE_PIN/IOSTANDARD placeholders in that file.
#   3. Add an entry here, for example:
#        my_board {part xc7a100tcsg324-1}

set top xadc_top

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
        start_gui
    } else {
        exit $code
    }
}

if { [llength $argv] < 1 } {
    puts "ERROR: missing <board>."
    puts "Usage: vivado -mode batch -source build.tcl -tclargs <board> \[-gui\]"
    puts "Known boards: [lsort [array names board_info]]"
    exit 1
}

set board [lindex $argv 0]
if { ![info exists board_info($board)] } {
    puts "ERROR: unknown board '$board'."
    puts "Known boards: [lsort [array names board_info]]"
    exit 1
}
set part_name [dict get $board_info($board) part]

set part_obj [get_parts -quiet $part_name]
if { $part_obj eq "" } {
    puts "ERROR: unknown part '$part_name' for board '$board'."
    exit 1
}

# The XADC is in 7-series and Zynq-7000 devices only. UltraScale devices
# use SYSMON, which this design does not support. The patterns also accept
# the defense-grade (q) and automotive (a) versions of the families.
# Spartan-7 XC7S6 and XC7S15 do not have an XADC.
# Note: on low-voltage (-1L/-2L) parts, set the VCCINT and VCCBRAM alarm
# limits in xadc_top.vhd (INIT_51, INIT_55, INIT_58, INIT_5C) for the
# VCCINT of the part.
set part_arch [string tolower [get_property ARCHITECTURE $part_obj]]
if { [string match "*zynq" $part_arch] } {
    set g_zynq 1
} elseif { [regexp {(artix7|kintex7|virtex7|spartan7)} $part_arch] &&
           ![regexp {^x[ac]7s(6|15)[^0-9]} [string tolower $part_name]] } {
    set g_zynq 0
} else {
    puts "ERROR: part '$part_name' (ARCHITECTURE '$part_arch') has no XADC."
    puts "This design supports only 7-series and Zynq-7000 devices."
    exit 1
}

set script_dir [file dirname [file normalize [info script]]]
set src_dir    "$script_dir/src"
set xdc_path   "$script_dir/xdc/$board.xdc"
set proj_name  "xadc_monitor_$board"
set proj_dir   "$script_dir/build/$proj_name"
set dest_dir   "$script_dir/../src/design_files"

set vhdl_files {
    bscan_primitive_wrapper.vhd
    bscan_user_register_io.vhd
    bscan_interface.vhd
    xadc_top.vhd
}

foreach f $vhdl_files {
    if { ![file exists "$src_dir/$f"] } {
        puts "ERROR: missing source file $src_dir/$f"
        exit 1
    }
}
if { ![file exists $xdc_path] } {
    puts "ERROR: missing constraints file $xdc_path"
    exit 1
}

create_project $proj_name $proj_dir -part $part_name -force
set_property target_language VHDL [current_project]

set src_paths {}
foreach f $vhdl_files {
    lappend src_paths "$src_dir/$f"
}
add_files -norecurse -fileset [get_filesets sources_1] $src_paths
add_files -norecurse -fileset [get_filesets constrs_1] $xdc_path

set_property top $top [get_filesets sources_1]
set_property generic "g_zynq=$g_zynq" [get_filesets sources_1]
update_compile_order -fileset sources_1

puts "----------------------------------------------------------------------"
puts "Board:       $board ($part_name)"
puts "Top:         $top (g_zynq=$g_zynq)"
puts "Constraints: $xdc_path"
puts "----------------------------------------------------------------------"

launch_runs synth_1 -jobs 4
wait_on_run synth_1
if { [get_property PROGRESS [get_runs synth_1]] != "100%" } {
    puts "ERROR: synth_1 did not complete. Refer to $proj_dir/$proj_name.runs/synth_1/runme.log"
    finish 1
    return
}

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if { [get_property PROGRESS [get_runs impl_1]] != "100%" } {
    puts "ERROR: impl_1 did not complete. Refer to $proj_dir/$proj_name.runs/impl_1/runme.log"
    finish 1
    return
}

set impl_dir "$proj_dir/$proj_name.runs/impl_1"
set bit_path "$impl_dir/$top.bit"
set ebd_path "$impl_dir/$top.ebd"
if { ![file exists $bit_path] } {
    puts "ERROR: bitstream not found at $bit_path"
    finish 1
    return
}

file mkdir $dest_dir
file copy -force $bit_path "$dest_dir/$top.bit"
set copied_files [list "$top.bit"]
if { [file exists $ebd_path] } {
    file copy -force $ebd_path "$dest_dir/$top.ebd"
    lappend copied_files "$top.ebd"
}

# Vivado power estimate of the implemented design (UG907). The default
# operating conditions apply (25 C ambient). main.py reads this report.
open_run impl_1
report_power -file "$dest_dir/${top}_power.rpt"
lappend copied_files "${top}_power.rpt"

puts "----------------------------------------------------------------------"
puts "Bitstream written: $bit_path"
puts "Files in $dest_dir:"
foreach f $copied_files { puts "  - $f" }
puts "----------------------------------------------------------------------"

finish 0
