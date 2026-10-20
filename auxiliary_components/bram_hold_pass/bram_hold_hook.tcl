# STEPS.OPT_DESIGN.TCL.PRE hook: runs the BRAM hold pass on the linked
# netlist before opt_design. The report goes to bram_hold_pass.rpt in
# the implementation run directory.
source [file join [file dirname [file normalize [info script]]] \
            bram_hold_pass.tcl]
bram_hold::run
