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
# The script creates the Vivado project of the NEORV32 hardening example for
# the Digilent Basys 3 and opens it in the Vivado GUI. It uses the sources and
# the constraints in hw/ and sets neorv32_test_setup_bootloader as
# the top. It does not build the project: run Generate Bitstream in the GUI.
# The bitstream run also writes the EBD and LL files. The default project is
# test_neo/test_neo.xpr, and neorv_fi_example/run_injection.py reads the
# .bit, .ebd and .ll files from test_neo/test_neo.runs/impl_1/.
#
# Notes:
#   1. The sem_0 IP (Soft Error Mitigation controller) is not part of the
#      project. Add it with create_ip and generate_target if you want
#      configuration-memory scrubbing in the design.
#   2. The project does not use partial reconfiguration. If you want it, add
#      "set_property pr_flow 1 [current_project]" after create_project, and
#      set up the PR configurations and runs that the Vivado PR flow needs.
#   3. The top has a HARDEN_EN generic (default true). It switches the
#      SolidKosmos hardening of the NEORV32 core. See the comment near the end
#      of this script for the unhardened baseline.
#   4. The implementation run executes the BRAM hold register pass before
#      opt_design (auxiliary_components/bram_hold_pass at the root of the
#      repository). It protects the words the NEORV32 read from its block
#      RAMs (IMEM, DMEM) against the SK-RAFT accesses to BRAM content
#      frames. Its report is bram_hold_pass.rpt in the impl_1 directory.
################################################################################

# Target part and top. To use another board, change the part and the XDC file
# (see "Porting to a Different Board" in README.md).
set part_name  xc7a35tcpg236-1
set top        neorv32_test_setup_bootloader
set lib_name   neorv32

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

set proj_name "test_neo"
set proj_dir  "./$proj_name"

# A project name without a directory gets its own default directory. Thus
# two different builds never share the same project directory.
if { [llength $argv] >= 1 } {
    set proj_name [lindex $argv 0]
    set proj_dir  "./$proj_name"
}
if { [llength $argv] >= 2 } { set proj_dir  [lindex $argv 1] }

set part_obj [get_parts -quiet $part_name]
if { $part_obj eq "" } {
    puts "ERROR: unknown/invalid part '$part_name' --"
    puts "check the part name at the top of create_project.tcl."
    exit 1
}

set script_dir [file dirname [file normalize [info script]]]
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

# The VHDL sources, relative to hw/. All of them are in the VHDL library
# neorv32.
# SolidKosmos sources: the test harness and the hardening blocks
set src_files {
    src/bscan_interface.vhd
    src/bscan_primitive_wrapper.vhd
    src/bscan_user_register_io.vhd
    src/clk_cycle_ctrlr.vhd
    src/clk_gen_wrapper.vhd
    src/examples_utilities_pkg.vhd
    src/harness_controller.vhd
    src/par_checker.vhd
    src/par_generator.vhd
    src/secded_dec32b.vhd
    src/secded_dec8b.vhd
    src/secded_ecc_dec_4bit.vhd
    src/secded_ecc_enc_4bit.vhd
    src/secded_enc32b.vhd
    src/secded_enc8b.vhd
    src/tester.vhd
}
# NEORV32 core (vendored, some files modified), the NEORV32 test setup
# (the top) and the application image
set neorv32_files {
    neorv32/core/neorv32_package.vhd
    neorv32/core/neorv32_bootloader_image.vhd
    neorv32/core/neorv32_boot_rom.vhd
    neorv32/core/neorv32_bus.vhd
    neorv32/core/neorv32_prim.vhd
    neorv32/core/neorv32_cache.vhd
    neorv32/core/neorv32_cfs.vhd
    neorv32/core/neorv32_clint.vhd
    neorv32/core/neorv32_cpu_decompressor.vhd
    neorv32/core/neorv32_cpu_frontend.vhd
    neorv32/core/neorv32_cpu_control.vhd
    neorv32/core/neorv32_cpu_hwtrig.vhd
    neorv32/core/neorv32_cpu_counters.vhd
    neorv32/core/neorv32_cpu_regfile.vhd
    neorv32/core/neorv32_cpu_cp_shifter.vhd
    neorv32/core/neorv32_cpu_cp_muldiv.vhd
    neorv32/core/neorv32_cpu_cp_bitmanip.vhd
    neorv32/core/neorv32_cpu_cp_fpu.vhd
    neorv32/core/neorv32_cpu_cp_cfu.vhd
    neorv32/core/neorv32_cpu_cp_cond.vhd
    neorv32/core/neorv32_cpu_cp_crypto.vhd
    neorv32/core/neorv32_cpu_alu.vhd
    neorv32/core/neorv32_cpu_lsu.vhd
    neorv32/core/neorv32_cpu_pmp.vhd
    neorv32/core/neorv32_cpu_trace.vhd
    neorv32/core/neorv32_cpu.vhd
    neorv32/core/neorv32_debug_auth.vhd
    neorv32/core/neorv32_debug_dm.vhd
    neorv32/core/neorv32_debug_dtm.vhd
    neorv32/core/neorv32_dma.vhd
    neorv32/core/neorv32_dmem.vhd
    neorv32/core/neorv32_gpio.vhd
    neorv32/core/neorv32_gptmr.vhd
    neorv32/core/neorv32_imem.vhd
    neorv32/core/neorv32_neoled.vhd
    neorv32/core/neorv32_onewire.vhd
    neorv32/core/neorv32_pwm.vhd
    neorv32/core/neorv32_sdi.vhd
    neorv32/core/neorv32_slink.vhd
    neorv32/core/neorv32_spi.vhd
    neorv32/core/neorv32_sys.vhd
    neorv32/core/neorv32_sysinfo.vhd
    neorv32/core/neorv32_xbus.vhd
    neorv32/core/neorv32_wdt.vhd
    neorv32/core/neorv32_uart.vhd
    neorv32/core/neorv32_twi.vhd
    neorv32/core/neorv32_twd.vhd
    neorv32/core/neorv32_trng.vhd
    neorv32/core/neorv32_tracer.vhd
    neorv32/core/neorv32_top.vhd
    neorv32/neorv32_application_image.vhd
    neorv32/neorv32_test_setup_bootloader.vhd
}
set vhdl_files [concat $src_files $neorv32_files]

set missing_files {}
foreach f $vhdl_files {
    if { ![file exists "$srcs_dir/$f"] } {
        lappend missing_files $f
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
set_property default_lib         $lib_name [current_project]
set_property enable_vhdl_2008    1 [current_project]

set src_paths {}
foreach f $vhdl_files {
    lappend src_paths "$srcs_dir/$f"
}
add_files -norecurse -fileset [get_filesets sources_1] $src_paths
set_property library $lib_name \
    [get_files -of_objects [get_filesets sources_1]]

add_files -fileset [get_filesets constrs_1] -norecurse $xdc_path
set xdc_file [lindex [get_files -of_objects [get_filesets constrs_1] \
    "*/[file tail $xdc_path]"] 0]
set_property target_constrs_file $xdc_file [get_filesets constrs_1]

set_property top $top [get_filesets sources_1]
set_property top $top [get_filesets sim_1]
set_property top_lib $lib_name [get_filesets sim_1]
update_compile_order -fileset sources_1

puts "----------------------------------------------------------------------"
puts "Project '$proj_name' created at '$proj_dir'"
puts "Part:        $part_name"
puts "Top:         $top"
puts "Constraints: $xdc_path"
puts "----------------------------------------------------------------------"

# To build the unhardened baseline for a fault-injection comparison, remove
# the "#" of the next line. Generics are resolved at synthesis time. Thus use
# a separate project name (the first argument) for each variant, to keep both
# bitstreams.
# set_property generic HARDEN_EN=false [get_filesets sources_1]

# The bitstream run also writes the logic location (LL) file. The EBD file
# (essential bits) comes from BITSTREAM.SEU.ESSENTIALBITS in the XDC.
set_property STEPS.WRITE_BITSTREAM.ARGS.LOGIC_LOCATION_FILE true \
    [get_runs impl_1]

# The BRAM hold register pass, as the hook before opt_design. It writes
# bram_hold_pass.rpt in the impl_1 run directory.
set hold_hook [file normalize \
    "$script_dir/../../auxiliary_components/bram_hold_pass/bram_hold_hook.tcl"]
if { ![file exists $hold_hook] } {
    puts "ERROR: BRAM hold pass not found: $hold_hook"
    exit 1
}
set_property STEPS.OPT_DESIGN.TCL.PRE $hold_hook [get_runs impl_1]

puts "Run Generate Bitstream in the GUI. The .bit, .ebd, .ll and"
puts "bram_hold_pass.rpt files go to"
puts "  $proj_dir/$proj_name.runs/impl_1/"

finish 0
