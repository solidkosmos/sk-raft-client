# SEM arbitration: SK-RAFT injects, the SEM corrects

This example shows how SK-RAFT and the Soft Error Mitigation (SEM) controller of the FPGA can share the configuration logic. SK-RAFT injects upsets into the configuration memory (CRAM) while the SEM is idle. Then the SEM scans the CRAM again and reports what it finds on the UART of the board. The script compares the reports of the SEM with the injected bits (output of experiment 1, shortened):

```
SEM status after I: idle
clock off
injected far 00020518 (block type 0) word  50 bit  0
clock on
> O
  SEM| SC 04
  SEM| SED OK
  SEM| PA 00020518
  SEM| WD 32 BT 00
  SEM| COR
  ...
    FAR       WORD  BIT  REPORTED
    00020518    50    0  yes, PA 00020518
The SEM reported 1 of 1 injected bits.
```

The lines that start with `SEM|` are the UART text of the SEM.

![Block diagram of the Basys 3 design. The board clock goes through the safe clock generation PLL and a clock gate (BUFGCE) to sem_clk, which drives the SEM controller and the monitor interface. BSCAN USER1 sets the clock enable, USER2 gives the ICAP grant to the SEM and reads icap_request, USER3 reads the 8 SEM status bits. The SEM controller sits in pblock_sem (the target of experiments 4 and 5) and reads and corrects the configuration frames through ICAPEX and FRAME_ECCEX (ICAPE2 and FRAME_ECCE2 on the Basys 3, ICAPE3 and FRAME_ECCE3 on the TE0841). Over JTAG, SK-RAFT injects upsets into the CRAM (experiments 1 to 3) and reads it back. The monitor interface connects the SEM monitor port to the UART of the host. The SEM is PG036 on 7 series and PG187 on UltraScale. The TE0841 design is the same, with 10 status bits.](images/sem_arbitration_blocks.svg)

## Supported boards

The example has a design for two boards. One script, `src/main.py`, works with both.

| Folder | Board | Device | SEM IP |
| --- | --- | --- | --- |
| `basys3/` | Digilent Basys 3 | Artix-7 `xc7a35tcpg236-1` | `sem` 4.1 (PG036) |
| `te0841/` | Trenz TE0841-02 | Kintex UltraScale `xcku040-sfva784-1-i` | `sem_ultra` 3.1 (PG187) |

## Files

| File | Description |
| --- | --- |
| `src/main.py` | The test script: board settings, BSCAN and SK-RAFT operations, the experiments. |
| `src/sem_monitor.py` | Helpers for `main.py`: the UART reader of the SEM and the parsing of the SEM reports and status. |
| `<board>/create_project.tcl` | Creates the Vivado project with the sources, the constraints and the SEM IP. |
| `basys3/hw/src/sem_arbitration_7series.vhd`, `te0841/hw/src/sem_arbitration_us.vhd` | The top: the SEM, ICAP, frame ECC, the BSCAN registers and the clock enable. |
| `<board>/hw/src/monitor_interface.vhd`, `fifo_mem.vhd`, `uart_rx_tx.vhd`, `rx_module.vhd`, `tx_module.vhd` | The UART bridge of the SEM monitor port (9600 8-N-1). |
| `<board>/hw/src/bscan_*.vhd`, `clk_gen_wrapper.vhd`, `examples_utilities_pkg.vhd` | The BSCAN interface and the safe-startup PLL of the getting-started examples. |
| `<board>/hw/xdc/` | Pins, clocks, bitstream settings (EBD, per-frame CRC) and the pblock of the SEM, `pblock_sem`. |
| `images/` | The block diagram. |

## BSCAN registers

Both designs use the same registers:

| Register | Write | Read |
| --- | --- | --- |
| USER1 | Clock enable of the SEM and the monitor interface: 1 = the clock operates, 0 = stopped. 0 after programming. | The value written last. |
| USER2 | The ICAP grant of the SEM. 0 after programming. Basys 3: bit 0 = `icap_grant`. TE0841: bit 0 = `cap_gnt`, bit 1 = `cap_rel`. | Basys 3: `icap_request`. TE0841: bit 0 = `cap_req`, bit 1 = `cap_gnt`. |
| USER3 | | The SEM status signals: 8 bits on the Basys 3, 10 bits on the TE0841 (see `status_names` in `main.py`). |

On the Basys 3, the LEDs show `icap_request` (LD0), `status_heartbeat` (LD1), `status_initialization` (LD2) and SEM idle (LD15).

## How the arbitration works

Each experiment does these steps:

1. Program the design, start the clock (USER1 = 1) and set the ICAP grant to 1 (USER2 = 1). The SEM initializes and goes to observation.
2. Send `I`. The SEM goes to idle: it stops scanning and does not use the ICAP.
3. Stop the clock (USER1 = 0), inject the upsets of the experiment, start the clock again (USER1 = 1).
4. Send `O`. The SEM goes back to observation, without a new initialization, and scans the CRAM.
5. Show the injected bits, which of them the SEM reported, and the SEM status.

The clock is stopped during the injections because SK-RAFT injects a bit as a read-modify-write of the whole frame, through the same configuration logic that the SEM uses. With the clock stopped, the frame address in each report (`PA` - Physical Address) is the FAR of the injected frame.

The script does not reset the SEM (`R 00`). In observation, the SEM ignores `R 00`. A reset from idle works, but then the SEM initializes with the upsets in the CRAM, and it does not report them.

## The experiments

The results are from runs with `SEED` 12, the default.

| # | Target | Upsets | Result on the Basys 3 | Result on the TE0841 |
| --- | --- | --- | --- | --- |
| 1 | Anywhere | One single bit upset (SBU) | The SEM corrects the bit and reports it (`SED OK`, `COR`). | The SEM corrects the bit and reports it (`ECC`, `COR`). |
| 2 | Anywhere | Two adjacent bits in one word of a frame | The SEM detects a double error (`DED`) and stops as uncorrectable. | The SEM corrects both bits and reports them. |
| 3 | Anywhere | Three bits in one frame, in different words | The SEM cannot correct the frame. It corrects a wrong bit (word 89, bit 13), then reports `CRC` and stops as uncorrectable. | The SEM cannot correct the frame. It reports `COR` without corrected bits, then stops as uncorrectable. |
| 4 | The SEM | One SBU | The SEM corrects the bit and reports it. | The SEM corrects the bit and reports it. |
| 5 | The SEM | `NUM_SEM_UPSETS` (1000) SBUs, one at a time: steps 2 to 4 for each SBU | The SEM corrects 4 SBUs, then it stops answering (round 5: FAR `00400410`, word 40, bit 21). | The SEM corrects 6 SBUs, then it stops answering (round 7: FAR `00025907`, word 114, bit 16). |

"Anywhere" is a random CRAM bit of the device, outside `pblock_sem` (`exclude_pblock` of `inject_random`). "The SEM" is a random essential bit inside `pblock_sem`. Experiments 2 and 3 add the other bits to the frame of the first bit with `inject_at`.

Each experiment starts with a new programming of the FPGA, so that it starts from a clean CRAM. Experiment 5 stops when the SEM reports an uncorrectable error, does not answer `O`, or sends the same report `LOOP_LIMIT` times in one round. With the same seed, the script injects the same bits in every run: on the TE0841, two runs failed on the same bit. With other seeds, the SEM on the Basys 3 also failed after 9 corrected SBUs, or repeated a wrong correction without end (a correction loop). Its status signals did not show the fatal state (all state bits set).

Other results of the tests:

- **BRAM content.** The SEM checks only the configuration frames (block type 0), so it cannot detect an upset in BRAM content (block type 1) and gives no report; the script prints a `BRAM content bit:` line for such picks. This includes the SEM's own BRAMs (three RAMB18E1 without ECC that hold its firmware and data buffer), so an upset there can silently change how the SEM works.
- **Matching.** A report matches an injected bit if the word and the bit are the same. The script shows the `PA` of the matching report. A report that matches no injected bit is shown as "reported, not injected".

## Requirements

- SK-RAFT server, with the board connected through JTAG.
- A USB-UART connection to the board (on the Basys 3, the USB cable gives JTAG and UART).
- Vivado 2025.2 (the version that the Tcl scripts were written for) to build the design.
- Python 3.9 or a later version, with the `skraft` package (`api/python`) and pySerial (`pip install pyserial`).

## Generate the design

1. Open the Vivado Tcl shell and run the script of your board, for example:

   ```bash
   vivado -mode batch -source basys3/create_project.tcl
   ```

   The script creates the project `<board>/sem_arbitration/sem_arbitration.xpr` next to itself, creates the SEM IP and opens the project in the Vivado GUI.
2. Run Generate Bitstream. The `.bit` and `.ebd` files go to `<board>/sem_arbitration/sem_arbitration.runs/impl_1/`. `main.py` reads them from there.

## Run the example

1. At the top of `src/main.py`, set `BOARD` and `SK_RAFT_SERVER_IP`.
2. In `BOARDS`, set `serial_number` and `uart_port` for your board.
3. Run the script:

   ```bash
   python src/main.py
   ```

| Constant | Default | Description |
| --- | --- | --- |
| `BOARD` | `BOARDS["basys3"]` | The board: `BOARDS["basys3"]` or `BOARDS["te0841"]`. |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `serial_number`, `uart_port` (in `BOARDS`) | for each board | The serial number of the board (`get_devices()` gives the connected boards) and the COM port of its USB-UART. |
| `EXPERIMENTS` | `(1, 2, 3, 4, 5)` | The experiments to run, in this order. |
| `SEM_PBLOCK` | `"pblock_sem"` | The pblock of the SEM in the XDC files. |
| `SEED` | `12` | The seed of the random picks. With the same seed, each experiment hits the same bits in every run. |
| `NUM_SEM_UPSETS` | `1000` | The maximum number of rounds of experiment 5. |
| `QUIET_S` | `1.0` | A SEM reply is complete when the UART is silent for this time, in seconds. |
| `WAIT_S` | `10.0` | The maximum time for the SEM to initialize or to reply, in seconds. |
| `REPORT_WAIT_S` | `0.5` | After the reply to `O`, the time to wait for more SEM reports, in seconds. |
| `LOOP_LIMIT` | `3` | The number of identical SEM reports in one round that is a correction loop. |

At the end, the script programs the FPGA again, so that the CRAM is correct. If the script stops before the end (an error or Ctrl+C), the CRAM is not correct. Program the FPGA again before you do other work.

## Note on the TE0841 (UltraScale)

- The script does not use USER2 bit 1 (`cap_rel`). With it, SK-RAFT can do the release handshake of PG187: set `cap_rel`, wait until `cap_req` is 0, then clear `cap_gnt`.
