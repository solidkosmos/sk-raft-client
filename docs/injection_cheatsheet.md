# SK-RAFT injection setup cheat sheet

The rules that a design must obey for correct fault injection with SK-RAFT, and the reasons for them. For the general concepts (CRAM, ARAM, essential bits), refer to [`concepts.md`](concepts.md).

## 1. Use a safe-startup clock source

**Rule:** The source of each clock tree in the design must be a PLL or an MMCM with safe startup. The output clock must stay off until the PLL has locked.

**Why:** An experiment can program the FPGA again many times, for example to remove the upsets of one step before the next step. After each programming, the design starts again. Without safe startup, the design can run on the clock while the PLL is not stable, and start in an incorrect state. Then a failure that the script sees can come from the startup, and not from the injected fault.

**In this repository:**

- [`auxiliary_components/safe_clk_gen/`](../auxiliary_components/safe_clk_gen/README.md): `clk_gen_wrapper`, a PLL for 7-series, UltraScale and UltraScale+. It enables the output BUFGCE only after LOCKED has passed an 8-stage shift register.
- `targeted_top`, `ff_lut_top`, `brams_top` and `bram_readback_writeback_top` (in [`get_started/hw/sources_1/new/`](../get_started/hw/sources_1/new/)), [`test_neo_hardened`](../application_examples/test_neo_hardened/README.md) and [`sem_arbitration`](../application_examples/sem_arbitration/README.md) use `clk_gen_wrapper`.
- All the examples program the FPGA at the start, and some examples program it again between their steps (for example [example1](../get_started/example1/README.md) and [example4](../get_started/example4/README.md)).

## 2. Stop the clock during application memory injection

**Rule:** Before an injection into the application memory (`TargetMemory.FF`, `TargetMemory.LUTRAM` or `TargetMemory.BRAM`), stop the clock of the logic that uses that memory. Start the clock again after the injection.

**Why:** SK-RAFT gets access to the application memory through the configuration interface (readback, frame write, and capture of the flip-flop states). These operations are asynchronous to the application clock and change the application memory directly. If the clock runs during the access, the design can sample data that is not stable.

```python
dev.write_bscan(USER_CLK_EN, 0)         # stop the clock
dev.inject_random(TargetMemory.FF)      # inject
dev.write_bscan(USER_CLK_EN, 1)         # start the clock
```

**In this repository:**

- [`auxiliary_components/bscan/README.md`](../auxiliary_components/bscan/README.md#example-clock-gate-on-user1): the clock gate. A BSCAN USER register (USER1) drives the CE of a BUFGCE. The README has the VHDL, the XDC and the Python calls.
- [`auxiliary_components/README.md`](../auxiliary_components/README.md#how-they-fit-together): the full sequence (stop, inject, start, read the result).
- [example3](../get_started/example3/README.md) (flip-flops and LUTRAM) and [example4](../get_started/example4/README.md) (BRAM) stop the clock with USER1 for each injection.

**AMD references:**

- XAPP1230 (v1.1), *Configuration Readback Capture in UltraScale FPGAs*: "the user must stop the clocks with the associated logic to freeze the user state". For 7-series: "Xilinx recommends stopping the clock of the associated user logic while the GCAPTURE command is being loaded".
- UG470, *7 Series FPGAs Configuration User Guide*, Chapter 6, "Readback Capture" (GCAPTURE and the CAPTUREE2 primitive).
- UG570 (v1.17), *UltraScale Architecture Configuration User Guide*, Chapter 10, "Readback Capture" (pp. 193-194): "In the UltraScale FPGAs, you must stop or disable the clock associated with the user state elements being targeted throughout the duration of the readback capture sequence."
- UG953, *Vivado Design Suite 7 Series FPGA and Zynq 7000 SoC Libraries Guide*, `CAPTUREE2`: only flip-flop and latch states can be captured. LUTRAM, SRL and block RAM states can be read back, but not captured.

## 3. BRAM injection changes the BRAM output

**Rule:** For each BRAM port without an output register (`DO_REG = 0`), add a hold register behind the output. Use the BRAM hold register pass to add it.

**Why:** Each SK-RAFT access to a BRAM content frame (readback, inject and revert) changes the **output latch** of the BRAMs in that frame. The value on `DO` changes, but the stored content and the FIFO pointers do not change. If the design uses `DO` after the clock starts again, it gets the changed value and not the word that it read before the freeze. Ports with the output register (`DO_REG = 1`) keep the word while the clock is stopped, and do not need the hold register.

The pass works only if the design obeys these requirements:

1. The clock gate stops the clock **low**. Use a BUFGCE, not a BUFGCE_1.
2. The half-cycle paths to and from the hold register meet timing.
3. SK-RAFT injects only while the clock is stopped (rule 2).
4. The XDC excludes the BRAMs from power optimization:

   ```tcl
   set_power_opt -exclude_cells [get_cells -hier -filter {REF_NAME =~ RAMB*}]
   ```

**In this repository:**

- [`auxiliary_components/bram_hold_pass/README.md`](../auxiliary_components/bram_hold_pass/README.md): the problem, the hold register, the requirements and the report of the pass.
- [example4/readback_writeback](../get_started/example4/readback_writeback/README.md): shows the effect. The BRAM outputs a wrong word while the clock is stopped after an injection.
- [example4](../get_started/example4/README.md#bram-output-latch-and-the-hold-register): a BRAM protected by the pass.
- [`get_started/hw/create_project.tcl`](../get_started/hw/create_project.tcl) (list `tops_with_bram_hold`) and [`application_examples/test_neo_hardened/create_project.tcl`](../application_examples/test_neo_hardened/create_project.tcl) set the pass as the hook before `opt_design`.

**AMD references:**

- UG570 (v1.17), *UltraScale Architecture Configuration User Guide*, Chapter 10, "SEU Detection and Correction" (p. 192): "Block RAM content is skipped during readback to avoid interfering with user functions." The guide does not describe the effect on the output latch. The effect above comes from the measurements of example4/readback_writeback.
