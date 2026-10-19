# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.
#
# BRAM shadow register netlist pass (7-series and UltraScale).
#
# A configuration access to BRAM content frames (SK-RAFT readback, inject,
# revert) overwrites the BRAM output latch when the port has no output
# register (DO_REG = 0). This pass puts a shadow register behind every
# such output: a flip-flop on the opposite clock edge of the BRAM read
# clock that copies the output in the half cycle after each read. The
# loads of the output are moved to the shadow register.
#
# Per BRAM port:
#   - skipped when the output register is on (DOA_REG/DOB_REG/DO_REG = 1)
#   - skipped when no output pin of the port has a load
#   - skipped when every load of an output pin is already a shadow in the
#     source: a flip-flop on the opposite edge of the same clock whose CE
#     is the port enable registered on the BRAM edge (CE tied on when the
#     enable is tied on). An opposite-edge flip-flop with any other CE
#     (for example CE = 1, loading every cycle) is not a shadow: after a
#     freeze it loads the overwritten output, so a shadow is inserted in
#     front of it. -trust_existing accepts any opposite-edge flip-flop.
#   - skipped when the cell matches an -exclude pattern
#   - skipped when the port is never enabled (enable tied off)
#   - UltraScale RAMB36E2/RAMB18E2: SDP when READ_WIDTH_A is the full
#     width (72/36), else per port; FIFO36E2/FIFO18E2 with REGISTER_MODE =
#     UNREGISTERED. RAMB*E2 cascades (CASCADE_ORDER), FWFT FIFOs without
#     the output register and URAM are reported, not changed
# Cascaded RAMB36E1 (64K x 1, RAM_EXTENSION = UPPER/LOWER): the output of
# the pair is the UPPER output, which gets the shadow; its enable covers
# both halves. The LOWER outputs have no loads and are skipped.
# Shadow clock enable: the OR of the port enables and output latch resets
# (RAMB18E1/RAMB36E1; both halves of a cascade), registered on the BRAM
# clock edge. One enable flip-flop is shared by every port with the same
# clock and terms.
# With the enable tied on, the shadow loads every cycle (no enable FF).
# Inverted BRAM pins (IS_*_INVERTED) are followed.
# Loads that sample on the BRAM edge (directly, or through logic) move to
# the shadow output: it holds the word half a cycle before they sample, so
# their timing does not change. Loads that sample on the opposite edge get
# a LUT3 mux, registered enable ? DO : shadow, per bit: they take DO in the
# half cycle after a read, as before (the shadow would be one cycle late
# for them, since it loads on that same edge), and the shadow otherwise.
# A load whose logic reaches registers on both edges gets the mux and a
# warning.
#
# The clock of a shadowed BRAM must stop so that the BRAM read edge is
# followed by the shadow edge before the freeze (a BUFGCE, which stops
# low, for a non-inverted BRAM clock). The pass warns when the BRAM clock
# comes from a buffer that stops on the wrong level.
#
# Usage, on a synthesized netlist (before opt_design):
#   source bram_shadow_pass.tcl
#   bram_shadow::run                    ;# change the netlist
#   bram_shadow::run -dry_run           ;# only report
#   bram_shadow::run -report file.rpt   ;# report file name
#   bram_shadow::run -exclude {u_a/* u_b}  ;# leave these BRAM cells alone
#   bram_shadow::run -trust_existing    ;# any opposite-edge FF is a shadow
# In a project, bram_shadow_hook.tcl is the STEPS.OPT_DESIGN.TCL.PRE hook.
# See README.md for the rules and how to read the report.

namespace eval bram_shadow {
    variable uid 0
    variable consts
    variable enables
    variable dry_run 0
    variable trust_existing 0
    variable counts
}

# ---------------------------------------------------------------- helpers

proc bram_shadow::next_id {} {
    variable uid
    return [incr uid]
}

proc bram_shadow::name_in {parent base} {
    if {$parent eq ""} { return $base }
    return "$parent/$base"
}

# Property value, or default when the property is missing or empty
proc bram_shadow::prop {obj name {default ""}} {
    if {[catch {get_property -quiet $name $obj} value] || $value eq ""} {
        return $default
    }
    return $value
}

# 1 for 1'b1, 1 or TRUE
proc bram_shadow::is_one {value} {
    return [expr {[string match "*1" $value] ||
                  [string equal -nocase $value TRUE]}]
}

proc bram_shadow::pin_net {pin} {
    if {$pin eq ""} { return "" }
    return [get_nets -quiet -of_objects $pin]
}

proc bram_shadow::driver_pin {net} {
    if {$net eq ""} { return "" }
    return [get_pins -quiet -leaf -of_objects $net -filter {DIRECTION == OUT}]
}

# What drives net, for comparing nets: the leaf driver pin, or the
# top-level port when the net comes straight from a port (out-of-context
# netlists have no input buffers)
proc bram_shadow::driver_id {net} {
    set d [driver_pin $net]
    if {$d ne ""} { return $d }
    if {$net eq ""} { return "" }
    return [get_ports -quiet -of_objects $net]
}

proc bram_shadow::loads {net} {
    if {$net eq ""} { return {} }
    return [get_pins -quiet -leaf -of_objects $net -filter {DIRECTION == IN}]
}

# 0 or 1 for a constant net (no net = 0), "" for a signal
proc bram_shadow::const_value {net} {
    if {$net eq ""} { return 0 }
    set type [prop $net TYPE]
    if {$type in {GND GROUND}} { return 0 }
    if {$type in {VCC POWER}} { return 1 }
    set drv [driver_pin $net]
    if {[llength $drv] == 1} {
        set ref [get_property REF_NAME [get_cells -of_objects $drv]]
        if {$ref eq "GND"} { return 0 }
        if {$ref eq "VCC"} { return 1 }
    }
    return ""
}

# Output pins of a cell by bus or pin name
proc bram_shadow::pins_of {cell names} {
    set result {}
    set cname [get_property NAME $cell]
    foreach name $names {
        set p [get_pins -quiet -of_objects $cell -filter "BUS_NAME == $name"]
        if {![llength $p]} {
            set p [get_pins -quiet "$cname/${name}\[*\]"]
        }
        if {![llength $p]} {
            set p [get_pins -quiet -of_objects $cell \
                       -filter "REF_PIN_NAME == $name"]
        }
        foreach q $p { lappend result $q }
    }
    return $result
}

# A GND or VCC net in the hierarchy level parent (one per level)
proc bram_shadow::const_net {parent value} {
    variable consts
    set key "$parent|$value"
    if {[info exists consts($key)]} { return $consts($key) }
    set id [next_id]
    if {$value} { set ref VCC; set out P } else { set ref GND; set out G }
    set cname [name_in $parent "bram_shadow_${ref}_$id"]
    set nname [name_in $parent "bram_shadow_${ref}_net_$id"]
    create_cell -reference $ref $cname
    create_net $nname
    set net [get_nets $nname]
    connect_net -net $net -objects [get_pins "$cname/$out"]
    set consts($key) $net
    return $net
}

# 1 when the BRAM clock, as seen by the BRAM, stops high after a freeze:
# the gating buffer stops on the level that leaves no shadow edge after
# the last BRAM edge
proc bram_shadow::stops_wrong {clk_drv clk_inv} {
    if {$clk_drv eq ""} { return 0 }
    set c [get_cells -quiet -of_objects $clk_drv]
    if {$c eq ""} { return 0 }
    set ref [get_property REF_NAME $c]
    if {$ref in {BUFGCE_1 BUFGMUX_1}} {
        set high 1
    } elseif {$ref in {BUFGCTRL BUFHCE BUFGCE BUFGMUX BUFMRCE}} {
        set high [is_one [prop $c INIT_OUT 0]]
    } else {
        return 0
    }
    return [expr {$high != $clk_inv}]
}

# 1 when ff's CE makes it a shadow: CE driven by a flip-flop on the BRAM
# edge (same clock) whose D is the port enable (en_drv: the driver of the
# enable net), or CE tied on when the port enable is tied on (en_always)
proc bram_shadow::is_shadow_ce {ff clk_drv clk_inv en_drv en_always} {
    set ce_net [pin_net [get_pins -quiet -of_objects $ff \
                             -filter {REF_PIN_NAME == CE}]]
    set c [const_value $ce_net]
    if {$c ne ""} { return [expr {$c == 1 && $en_always}] }
    if {$en_drv eq ""} { return 0 }
    set drv [driver_pin $ce_net]
    if {[llength $drv] != 1 || [get_property REF_PIN_NAME $drv] ne "Q"} {
        return 0
    }
    set r [get_cells -of_objects $drv]
    if {[get_property REF_NAME $r] ni {FDRE FDCE FDPE FDSE}} { return 0 }
    set rc [get_pins -quiet -of_objects $r -filter {REF_PIN_NAME == C}]
    if {[driver_id [pin_net $rc]] ne $clk_drv} { return 0 }
    if {[is_one [prop $r IS_C_INVERTED 0]] != $clk_inv} { return 0 }
    if {[is_one [prop $r IS_D_INVERTED 0]]} { return 0 }
    set rd [get_pins -quiet -of_objects $r -filter {REF_PIN_NAME == D}]
    return [expr {[driver_id [pin_net $rd]] eq $en_drv}]
}

# What the loads of net are:
#   shadow    every load is a shadow flip-flop (opposite edge, shadow CE)
#   opposite  every load is an opposite-edge flip-flop, but at least one
#             has another CE (not a shadow)
#   other     anything else
proc bram_shadow::load_kind {net clk_drv clk_inv en_drv en_always} {
    set lds [loads $net]
    if {![llength $lds]} { return other }
    set kind shadow
    foreach p $lds {
        if {[get_property REF_PIN_NAME $p] ne "D"} { return other }
        set c [get_cells -of_objects $p]
        if {[get_property REF_NAME $c] ni {FDRE FDCE FDPE FDSE}} {
            return other
        }
        set cpin [get_pins -quiet -of_objects $c -filter {REF_PIN_NAME == C}]
        if {[driver_id [pin_net $cpin]] ne $clk_drv} { return other }
        if {[is_one [prop $c IS_C_INVERTED 0]] == $clk_inv} { return other }
        if {![is_shadow_ce $c $clk_drv $clk_inv $en_drv $en_always]} {
            set kind opposite
        }
    }
    return $kind
}

# ------------------------------------------------------------ load edges

# 1 for a cell with a clock pin (a register, a BRAM, ...)
proc bram_shadow::is_sequential {cell} {
    return [llength [get_pins -quiet -of_objects $cell -filter {IS_CLOCK}]]
}

# Edge on which a sequential cell samples, relative to the BRAM clock:
# same, opposite, mixed, or none (not clocked by the BRAM clock)
proc bram_shadow::cell_edge {cell clk_drv clk_inv} {
    set result none
    foreach cp [get_pins -quiet -of_objects $cell -filter {IS_CLOCK}] {
        if {[driver_id [pin_net $cp]] ne $clk_drv} { continue }
        set inv [is_one [prop $cell \
                    "IS_[get_property REF_PIN_NAME $cp]_INVERTED" 0]]
        set e [expr {$inv == $clk_inv ? "same" : "opposite"}]
        if {$result eq "none"} {
            set result $e
        } elseif {$result ne $e} {
            return mixed
        }
    }
    return $result
}

# Edge on which a load of a BRAM output samples the word: the load's own
# edge for a sequential cell, else the edges of the registers its logic
# reaches (all_fanout endpoints). same, opposite, mixed or none.
proc bram_shadow::load_edge {pin clk_drv clk_inv} {
    set cell [get_cells -of_objects $pin]
    if {[is_sequential $cell]} { return [cell_edge $cell $clk_drv $clk_inv] }
    if {[catch {all_fanout -quiet -from $pin -endpoints_only -flat} ends]} {
        return mixed
    }
    set result none
    foreach e $ends {
        set c [get_cells -quiet -of_objects $e]
        if {$c eq "" || ![is_sequential $c]} { continue }
        set k [cell_edge $c $clk_drv $clk_inv]
        if {$k eq "none"} { continue }
        if {$result eq "none"} {
            set result $k
        } elseif {$result ne $k} {
            return mixed
        }
    }
    return $result
}

# ---------------------------------------------------------------- enables

# Read terms of a port: list of {net inverted}. The shadow loads when any
# term is active.
proc bram_shadow::terms_of {spec} {
    set terms {}
    foreach t $spec {
        lassign $t cell pin invprop
        set p [lindex [pins_of $cell $pin] 0]
        lappend terms [list [pin_net $p] [is_one [prop $cell $invprop 0]]]
    }
    return $terms
}

# always, never, or the list of distinct signal terms
proc bram_shadow::terms_state {terms} {
    set sig {}
    foreach t $terms {
        lassign $t net inv
        set c [const_value $net]
        if {$c ne ""} {
            if {$c ^ $inv} { return always }
            continue
        }
        if {$t ni $sig} { lappend sig $t }
    }
    if {![llength $sig]} { return never }
    return [lsort $sig]
}

# ------------------------------------------------------- netlist changes

# Net for the shadow CE: VCC net, or an enable FF output (the OR of the
# signal terms, registered on the BRAM clock edge)
proc bram_shadow::shadow_ce {parent clk_net clk_inv sig} {
    variable enables
    variable counts
    if {$sig eq "always"} { return [const_net $parent 1] }
    set key [join [list $parent [driver_id $clk_net] $clk_inv $sig] |]
    if {[info exists enables($key)]} { return $enables($key) }

    set id [next_id]
    set n [llength $sig]
    if {$n == 1 && ![lindex $sig 0 1]} {
        set d_net [lindex $sig 0 0]
    } else {
        if {$n > 6} { error "more than 6 enable terms" }
        set lname [name_in $parent "bram_shadow_en_lut_$id"]
        set d_name [name_in $parent "bram_shadow_en_d_$id"]
        create_cell -reference "LUT$n" $lname
        set init 0
        for {set idx 0} {$idx < (1 << $n)} {incr idx} {
            set out 0
            for {set k 0} {$k < $n} {incr k} {
                if {(($idx >> $k) & 1) ^ [lindex $sig $k 1]} { set out 1 }
            }
            if {$out} { set init [expr {$init | (1 << $idx)}] }
        }
        set_property INIT [format "%d'h%X" [expr {1 << $n}] $init] \
            [get_cells $lname]
        for {set k 0} {$k < $n} {incr k} {
            connect_net -net [lindex $sig $k 0] -objects [get_pins "$lname/I$k"]
        }
        create_net $d_name
        set d_net [get_nets $d_name]
        connect_net -net $d_net -objects [get_pins "$lname/O"]
        dict incr counts luts
    }

    set fname [name_in $parent "bram_shadow_en_reg_$id"]
    set qname [name_in $parent "bram_shadow_en_$id"]
    create_cell -reference FDRE $fname
    set ff [get_cells $fname]
    set_property INIT "1'b0" $ff
    set_property IS_C_INVERTED [expr {$clk_inv ? "1'b1" : "1'b0"}] $ff
    create_net $qname
    set q_net [get_nets $qname]
    connect_net -net $d_net -objects [get_pins "$fname/D"]
    connect_net -net $q_net -objects [get_pins "$fname/Q"]
    connect_net -net $clk_net -objects [get_pins "$fname/C"]
    connect_net -net [const_net $parent 1] -objects [get_pins "$fname/CE"]
    connect_net -net [const_net $parent 0] -objects [get_pins "$fname/R"]
    set_property DONT_TOUCH true $ff
    dict incr counts enable_ffs
    set enables($key) $q_net
    return $q_net
}

# Shadow one BRAM output pin. The loads on the BRAM edge move to the
# shadow output. The loads in mux_loads (opposite edge) get
# sel ? DO : shadow, so they take the BRAM output directly in the half
# cycle after a read, as before, and the shadow at other times. With sel
# "" (port always enabled) they stay on DO.
proc bram_shadow::shadow_pin {parent pin clk_net clk_inv ce_net mux_loads sel} {
    variable counts
    set net [pin_net $pin]
    set id [next_id]
    set fname [name_in $parent "bram_shadow_reg_$id"]
    set rname [name_in $parent "bram_shadow_raw_$id"]
    create_cell -reference FDRE $fname
    set ff [get_cells $fname]
    set_property INIT "1'b0" $ff
    set_property IS_C_INVERTED [expr {$clk_inv ? "1'b0" : "1'b1"}] $ff
    create_net $rname
    set raw [get_nets $rname]
    disconnect_net -net $net -objects $pin
    connect_net -net $raw -objects [list $pin [get_pins "$fname/D"]]
    connect_net -net $net -objects [get_pins "$fname/Q"]
    connect_net -net $clk_net -objects [get_pins "$fname/C"]
    connect_net -net $ce_net -objects [get_pins "$fname/CE"]
    connect_net -net [const_net $parent 0] -objects [get_pins "$fname/R"]
    set_property DONT_TOUCH true $ff
    dict incr counts shadow_ffs

    if {![llength $mux_loads]} { return }
    if {$sel eq ""} {
        set m_net $raw
    } else {
        set lname [name_in $parent "bram_shadow_mux_$id"]
        set mname [name_in $parent "bram_shadow_mux_net_$id"]
        create_cell -reference LUT3 $lname
        set lut [get_cells $lname]
        # O = I2 ? I0 : I1 (I0 = DO, I1 = shadow, I2 = registered enable)
        set_property INIT "8'hAC" $lut
        connect_net -net $raw -objects [get_pins "$lname/I0"]
        connect_net -net $net -objects [get_pins "$lname/I1"]
        connect_net -net $sel -objects [get_pins "$lname/I2"]
        create_net $mname
        set m_net [get_nets $mname]
        connect_net -net $m_net -objects [get_pins "$lname/O"]
        set_property DONT_TOUCH true $lut
        dict incr counts mux_luts
    }
    foreach l $mux_loads {
        disconnect_net -net [get_nets -of_objects $l] -objects $l
        connect_net -hierarchical -net $m_net -objects $l
    }
}

# One BRAM read port. spec: list of {cell pin inverted-property}, the
# enables (and output latch resets) that can change the output.
# Returns a report line.
proc bram_shadow::port {cell label outs clk inv_clk spec} {
    variable dry_run
    variable trust_existing
    variable counts
    set parent [prop $cell PARENT]
    set used {}
    foreach p [pins_of $cell $outs] {
        if {[llength [loads [pin_net $p]]]} { lappend used $p }
    }
    if {![llength $used]} {
        dict incr counts skipped_unused
        return "$label: no loads"
    }

    set sig [terms_state [terms_of $spec]]
    if {$sig eq "never"} {
        dict incr counts skipped_disabled
        return "$label: port never enabled"
    }

    set clk_pin [lindex [pins_of $cell $clk] 0]
    set clk_net [pin_net $clk_pin]
    set clk_inv [is_one [prop $cell $inv_clk 0]]
    set clk_drv [driver_id $clk_net]

    # A source shadow is recognised only for a single, non-inverted enable
    # term, or an enable tied on
    set en_always [expr {$sig eq "always"}]
    set en_drv ""
    if {!$en_always && [llength $sig] == 1 && ![lindex $sig 0 1]} {
        set en_drv [driver_id [lindex $sig 0 0]]
    }

    set todo {}
    set not_shadow 0
    foreach p $used {
        set kind [load_kind [pin_net $p] $clk_drv $clk_inv $en_drv $en_always]
        if {$kind eq "shadow" || ($kind eq "opposite" && $trust_existing)} {
            continue
        }
        if {$kind eq "opposite"} { incr not_shadow }
        lappend todo $p
    }
    if {![llength $todo]} {
        dict incr counts skipped_shadowed
        return "$label: already shadowed ([llength $used] pins)"
    }

    set note ""
    if {$not_shadow} {
        set note " ($not_shadow of these pins feed only opposite-edge flip-flops\
                  that are not shadows: CE is not the registered enable)"
        dict incr counts not_shadow_pins $not_shadow
    }
    set warn ""
    if {[stops_wrong $clk_drv $clk_inv]} {
        set warn " WARNING: clock buffer [get_cells -of_objects $clk_drv]\
                  stops on the wrong level for the shadow"
        dict incr counts warnings
    }

    # Loads on the opposite edge (or reaching both edges) keep taking DO
    # right after a read: they get the DO/shadow mux
    set plan {}
    set n_mux 0
    set n_mixed 0
    foreach p $todo {
        set ml {}
        foreach l [loads [pin_net $p]] {
            set e [load_edge $l $clk_drv $clk_inv]
            if {$e in {opposite mixed}} { lappend ml $l; incr n_mux }
            if {$e eq "mixed"} { incr n_mixed }
        }
        lappend plan [list $p $ml]
    }
    if {$n_mux} {
        if {$en_always} {
            append note " ($n_mux opposite-edge loads stay on DO: the port\
                         reads every cycle)"
        } else {
            append note " ($n_mux opposite-edge loads get DO in the half\
                         cycle after a read, the shadow otherwise)"
        }
        dict incr counts mux_loads $n_mux
    }
    if {$n_mixed} {
        append warn " WARNING: $n_mixed loads reach registers on both clock\
                     edges; they get the DO/shadow mux, so a register on the\
                     BRAM edge behind them is not protected when a read is\
                     on the last edge before a freeze (fix by hand)"
        dict incr counts warnings
    }

    set n [llength $todo]
    if {$dry_run} {
        dict incr counts shadow_ffs $n
        return "$label: would shadow $n pins$note$warn"
    }
    set ce [shadow_ce $parent $clk_net $clk_inv $sig]
    set sel [expr {$en_always ? "" : $ce}]
    foreach item $plan {
        lassign $item p ml
        shadow_pin $parent $p $clk_net $clk_inv $ce $ml $sel
    }
    dict incr counts shadowed_ports
    return "$label: shadowed $n pins$note$warn"
}

# The LOWER RAMB36E1 of a cascade: the driver of CASCADEIN<port>
proc bram_shadow::cascade_lower {cell port} {
    set pin [lindex [pins_of $cell "CASCADEIN$port"] 0]
    set drv [driver_pin [pin_net $pin]]
    if {[llength $drv] != 1} { error "no LOWER driving CASCADEIN$port" }
    return [get_cells -of_objects $drv]
}

# One TDP port of a RAMB18E1/RAMB36E1
proc bram_shadow::tdp_port {cell port {e2 0}} {
    variable counts
    if {$port eq "A"} {
        set outs [expr {$e2 ? {DOUTADOUT DOUTPADOUTP} : {DOADO DOPADOP}}]
        set clk CLKARDCLK; set en ENARDEN; set rst RSTRAMARSTRAM
    } else {
        set outs [expr {$e2 ? {DOUTBDOUT DOUTPBDOUTP} : {DOBDO DOPBDOP}}]
        set clk CLKBWRCLK; set en ENBWREN; set rst RSTRAMB
    }
    if {[prop $cell DO${port}_REG 0] == 1} {
        dict incr counts skipped_doreg
        return "port $port: DO_REG = 1"
    }
    set spec [list [list $cell $en IS_${en}_INVERTED] \
                   [list $cell $rst IS_${rst}_INVERTED]]
    set ext [prop $cell RAM_EXTENSION_$port NONE]
    set label "port $port"
    if {$ext eq "UPPER"} {
        # The output mixes both latches of the cascade: the shadow loads
        # when either half is enabled or reset
        set lower [cascade_lower $cell $port]
        lappend spec [list $lower $en IS_${en}_INVERTED] \
                     [list $lower $rst IS_${rst}_INVERTED]
        set label "port $port (cascade UPPER, LOWER $lower)"
    } elseif {$ext eq "LOWER"} {
        set label "port $port (cascade LOWER)"
    }
    return [port $cell $label $outs $clk IS_${clk}_INVERTED $spec]
}

# ------------------------------------------------------------------ pass

proc bram_shadow::run {args} {
    variable uid 0
    variable consts
    variable enables
    variable dry_run 0
    variable trust_existing 0
    variable counts
    array unset consts
    array unset enables
    set counts [dict create shadowed_ports 0 shadow_ffs 0 enable_ffs 0 \
                    luts 0 skipped_doreg 0 skipped_unused 0 \
                    skipped_shadowed 0 skipped_disabled 0 \
                    skipped_other 0 excluded 0 not_shadow_pins 0 \
                    mux_loads 0 mux_luts 0 \
                    warnings 0 errors 0]
    set report_file bram_shadow_pass.rpt
    set exclude {}
    for {set i 0} {$i < [llength $args]} {incr i} {
        switch -- [lindex $args $i] {
            -dry_run        { set dry_run 1 }
            -trust_existing { set trust_existing 1 }
            -report         { set report_file [lindex $args [incr i]] }
            -exclude        { set exclude [lindex $args [incr i]] }
            default  { error "bram_shadow::run: unknown option\
                              [lindex $args $i]" }
        }
    }

    set lines {}
    set cells [get_cells -quiet -hierarchical -filter \
        {IS_PRIMITIVE && (REF_NAME =~ RAMB* || REF_NAME =~ FIFO* || \
         REF_NAME =~ URAM*)}]
    foreach cell $cells {
        set ref [get_property REF_NAME $cell]
        set skip 0
        foreach pattern $exclude {
            if {[string match $pattern [get_property NAME $cell]]} {
                set skip 1
            }
        }
        if {$skip} {
            dict incr counts excluded
            lappend lines "$cell ($ref): excluded"
            continue
        }
        if {[catch {
            set out {}
            switch -- $ref {
                RAMB36E1 - RAMB18E1 {
                    if {[prop $cell RAM_MODE TDP] eq "SDP"} {
                        if {[prop $cell DOA_REG 0] == 1} {
                            dict incr counts skipped_doreg
                            lappend out "SDP read port: DO_REG = 1"
                        } else {
                            lappend out [port $cell "SDP read port" \
                                {DOADO DOPADOP DOBDO DOPBDOP SBITERR \
                                 DBITERR RDADDRECC} \
                                CLKARDCLK IS_CLKARDCLK_INVERTED \
                                [list [list $cell ENARDEN \
                                           IS_ENARDEN_INVERTED] \
                                      [list $cell RSTRAMARSTRAM \
                                           IS_RSTRAMARSTRAM_INVERTED]]]
                        }
                    } else {
                        lappend out [tdp_port $cell A]
                        lappend out [tdp_port $cell B]
                    }
                }
                RAMB36E2 - RAMB18E2 {
                    set full [expr {$ref eq "RAMB36E2" ? 72 : 36}]
                    set order "[prop $cell CASCADE_ORDER_A NONE]\
                               [prop $cell CASCADE_ORDER_B NONE]"
                    if {$order ne "NONE NONE"} {
                        dict incr counts skipped_other
                        lappend out "cascade (CASCADE_ORDER $order),\
                                     not changed"
                    } elseif {[prop $cell READ_WIDTH_A 0] == $full} {
                        # Full-width read: both outputs belong to port A
                        if {[prop $cell DOA_REG 0] == 1} {
                            dict incr counts skipped_doreg
                            lappend out "SDP read port: DO_REG = 1"
                        } else {
                            lappend out [port $cell "SDP read port" \
                                {DOUTADOUT DOUTPADOUTP DOUTBDOUT \
                                 DOUTPBDOUTP SBITERR DBITERR RDADDRECC} \
                                CLKARDCLK IS_CLKARDCLK_INVERTED \
                                [list [list $cell ENARDEN \
                                           IS_ENARDEN_INVERTED] \
                                      [list $cell RSTRAMARSTRAM \
                                           IS_RSTRAMARSTRAM_INVERTED]]]
                        }
                    } else {
                        lappend out [tdp_port $cell A 1]
                        lappend out [tdp_port $cell B 1]
                    }
                }
                FIFO36E2 - FIFO18E2 {
                    set mode [prop $cell REGISTER_MODE UNREGISTERED]
                    if {$mode ne "UNREGISTERED"} {
                        dict incr counts skipped_doreg
                        lappend out "read port: REGISTER_MODE = $mode"
                    } elseif {[is_one [prop $cell FIRST_WORD_FALL_THROUGH \
                                           FALSE]]} {
                        dict incr counts skipped_other
                        lappend out "read port: FWFT without output\
                                     register, not supported"
                    } else {
                        lappend out [port $cell "read port" \
                            {DOUT DOUTP SBITERR DBITERR} \
                            RDCLK IS_RDCLK_INVERTED \
                            [list [list $cell RDEN IS_RDEN_INVERTED]]]
                    }
                }
                FIFO36E1 - FIFO18E1 {
                    if {[prop $cell DO_REG 1] == 1} {
                        dict incr counts skipped_doreg
                        lappend out "read port: DO_REG = 1"
                    } else {
                        lappend out [port $cell "read port" \
                            {DO DOP SBITERR DBITERR} \
                            RDCLK IS_RDCLK_INVERTED \
                            [list [list $cell RDEN IS_RDEN_INVERTED]]]
                    }
                }
                default {
                    dict incr counts skipped_other
                    lappend out "$ref not supported, not changed"
                }
            }
            lappend lines "$cell ($ref): [join $out {; }]"
        } msg]} {
            dict incr counts errors
            lappend lines "$cell ($ref): ERROR $msg"
        }
    }

    set mode [expr {$dry_run ? { (dry run)} : {}}]
    if {$trust_existing} { append mode " (trust existing)" }
    set head [list "BRAM shadow pass$mode" \
        "  block RAM cells:          [llength $cells]" \
        "  ports shadowed:           [dict get $counts shadowed_ports]" \
        "  shadow FFs:               [dict get $counts shadow_ffs]" \
        "  enable FFs / LUTs:        [dict get $counts enable_ffs] /\
                                     [dict get $counts luts]" \
        "  ports skipped, DO_REG = 1: [dict get $counts skipped_doreg]" \
        "  ports skipped, no loads:  [dict get $counts skipped_unused]" \
        "  ports skipped, shadowed:  [dict get $counts skipped_shadowed]" \
        "  ports skipped, disabled:  [dict get $counts skipped_disabled]" \
        "  cells not changed:        [dict get $counts skipped_other]" \
        "  cells excluded:           [dict get $counts excluded]" \
        "  pins on non-shadow opposite-edge FFs (protected):\
                                     [dict get $counts not_shadow_pins]" \
        "  opposite-edge loads / DO-shadow mux LUTs:\
                                     [dict get $counts mux_loads] /\
                                     [dict get $counts mux_luts]" \
        "  clock level warnings:     [dict get $counts warnings]" \
        "  errors:                   [dict get $counts errors]" ""]
    set text [join [concat $head $lines] "\n"]
    set f [open $report_file w]
    puts $f $text
    close $f
    puts $text
    return $counts
}
