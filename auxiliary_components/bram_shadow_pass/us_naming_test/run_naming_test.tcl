# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# UltraScale naming test for bram_shadow_pass.tcl. Synthesizes
# us_naming_top.v (non-project, no constraints, no board), runs the pass,
# and checks that every BRAM got the expected number of shadow flip-flops
# and the expected report line. Then implements the changed netlist to a
# bitstream, to check that it is legal and the added cells stay.
# Usage (from any directory):
#   vivado -mode batch -source run_naming_test.tcl
#   vivado -mode batch -source run_naming_test.tcl -tclargs <part>
# Default part: the first installed part of FREE_PARTS (devices of the free
# Vivado ML Standard edition, no license needed). Writes us_naming_pass.rpt
# and us_naming_top.bit next to this script. The last line is
# NAMING TEST: PASS or FAIL.

set dir [file dirname [file normalize [info script]]]
set FREE_PARTS {xcku025-ffva1156-1-c xcku035-fbva676-1-c
                xcau10p-sbvb484-1-e xcau15p-sbvb484-1-e}
if {[llength $argv]} {
    set part [lindex $argv 0]
} else {
    set part ""
    foreach p $FREE_PARTS {
        if {[llength [get_parts -quiet $p]]} { set part $p; break }
    }
    if {$part eq ""} {
        error "none of $FREE_PARTS is installed; give a part with -tclargs"
    }
}
puts "Naming test part: $part"

read_verilog "$dir/us_naming_top.v"
synth_design -top us_naming_top -part $part

source [file join [file dirname $dir] bram_shadow_pass.tcl]
set rpt "$dir/us_naming_pass.rpt"
bram_shadow::run -report $rpt

# Shadow FFs whose D is on an output pin of inst
proc shadow_count {inst} {
    set n 0
    foreach p [get_pins -quiet -of_objects [get_cells $inst] \
                   -filter {DIRECTION == OUT}] {
        set net [get_nets -quiet -of_objects $p]
        if {$net eq ""} { continue }
        foreach l [get_pins -quiet -leaf -of_objects $net \
                       -filter {DIRECTION == IN}] {
            set c [get_cells -of_objects $l]
            if {[string match "*bram_shadow_reg_*" [get_property NAME $c]] &&
                [get_property REF_PIN_NAME $l] eq "D"} {
                incr n
            }
        }
    }
    return $n
}

set results {}
set fails 0
proc check {ok msg} {
    upvar results results fails fails
    lappend results [format "%-4s %s" [expr {$ok ? "ok" : "FAIL"}] $msg]
    if {!$ok} { incr fails }
}

# 1. shadow flip-flops per BRAM
set expected {u_tdp 36 u_wide 75 u_r18 16 u_fifo0 64 u_fifo1 0
              u_cas0 0 u_cas1 0 u_shd 0 u_pipe 8}
set total 0
foreach {inst n} $expected {
    set got [shadow_count $inst]
    check [expr {$got == $n}] "$inst: $got shadow FFs (expected $n)"
    incr total $n
}

# 2. DO/shadow mux LUTs (only u_pipe has opposite-edge loads)
set muxes [llength [get_cells -quiet -hierarchical \
                        -filter {NAME =~ *bram_shadow_mux_*}]]
check [expr {$muxes == 8}] "$muxes DO/shadow mux LUTs (expected 8)"

# 3. report lines
set f [open $rpt]
set text [read $f]
close $f
foreach {inst pattern} {
    u_tdp   {port A: shadowed 36 pins.*port B: DO_REG = 1}
    u_wide  {SDP read port: shadowed 75 pins}
    u_r18   {port A: shadowed 16 pins.*port B: no loads}
    u_fifo0 {read port: shadowed 64 pins}
    u_fifo1 {REGISTER_MODE = REGISTERED}
    u_cas0  {cascade .*not changed}
    u_cas1  {cascade .*not changed}
    u_shd   {port A: already shadowed \(8 pins\)}
    u_pipe  {port A: shadowed 8 pins.*8 opposite-edge loads}
} {
    set line ""
    foreach l [split $text "\n"] {
        if {[string match "$inst *" $l]} { set line $l }
    }
    check [regexp $pattern $line] "$inst report: $line"
}
check [regexp {errors:\s+0} $text] "no errors in the pass report"

# 4. the changed netlist goes through implementation to a bitstream, and
#    the added cells stay. The design has no pin constraints: the checks
#    for unconstrained I/O are made warnings.
set_property SEVERITY Warning [get_drc_checks {NSTD-1 UCIO-1}]
set bit "$dir/us_naming_top.bit"
file delete -force $bit
if {[catch {
    opt_design
    place_design
    route_design
    write_bitstream -force $bit
} msg]} {
    check 0 "implementation: $msg"
}
check [file exists $bit] "bitstream written ([file tail $bit])"
set left [llength [get_cells -quiet -hierarchical \
                       -filter {NAME =~ *bram_shadow_reg_*}]]
check [expr {$left == $total}] \
    "after implementation: $left shadow FFs (expected $total)"
set left [llength [get_cells -quiet -hierarchical \
                       -filter {NAME =~ *bram_shadow_mux_*}]]
check [expr {$left == 8}] \
    "after implementation: $left DO/shadow mux LUTs (expected 8)"

puts "\n[join $results \n]"
puts "\nPart: $part"
puts "NAMING TEST: [expr {$fails ? "FAIL ($fails)" : "PASS"}]"
