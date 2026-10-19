# STEPS.OPT_DESIGN.TCL.PRE hook: runs the BRAM shadow pass on the linked
# netlist before opt_design. The report goes to bram_shadow_pass.rpt in
# the implementation run directory.
source [file join [file dirname [file normalize [info script]]] \
            bram_shadow_pass.tcl]
bram_shadow::run
