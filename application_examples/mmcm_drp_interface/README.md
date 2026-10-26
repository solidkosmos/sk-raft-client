# MMCM dynamic reconfiguration: the client script changes the MMCM clocks over BSCAN

This example shows how to change the output clocks of an MMCM while the design runs. The client script sends Dynamic Reconfiguration Port (DRP) accesses to the FPGA through a BSCAN register, and a small state machine in the design does each access on the DRP of the MMCM. The script reads and writes the MMCM registers in the sequence of XAPP888, and the effect shows on two LEDs: each MMCM output clock drives a heartbeat.

![Block diagram of the Basys 3 design. The board clock goes through the safe clock generation PLL and a clock gate (BUFGCE) to safe_clk. safe_clk clocks BSCAN USER1, the DRP control FSM and the DRP of the MMCM, and it is the MMCM input clock (CLKIN1). Over JTAG, BSCAN USER1 receives the DRP packets and sends them to the DRP control FSM, which drives the DRP signals (DADDR, DI, DEN, DWE) and RST of the MMCM and waits for DRDY. The current DRP address, the DO of the MMCM and the error bit of the FSM go back to USER1 for the read. CLKOUT0 and CLKOUT1 of the MMCM each drive a heartbeat (a BUFG and a counter) on an LED, led_o[0] and led_o[1].](images/mmcm_drp_interface_blocks.svg)

## Tested on

| Board | Device |
| --- | --- |
| Digilent Basys 3 | Artix-7 `xc7a35tcpg236-1` |

The MMCM wrapper supports 7 series (`MMCME2_ADV`), UltraScale (`MMCME3_ADV`) and UltraScale+ (`MMCME4_ADV`): the `g_family` generic selects the primitive. For another board, change the part, `g_family` and the XDC file in `create_project.tcl`. The DRP addresses in `main.py` are the 7-series addresses (XAPP888); on UltraScale, the power register is `0x27`.

## Files

| File | Description |
| --- | --- |
| `src/main.py` | The test script: the DRP accesses over BSCAN, the XAPP888 reconfiguration sequence, the stages. |
| `create_project.tcl` | Creates the Vivado project with the sources and the constraints, and builds the bitstream. |
| `hw/src/mmcm_drp_interface_top.vhd` | The top: the safe clock, BSCAN USER1, the DRP control FSM, the MMCM and the two heartbeats. |
| `hw/src/DRP_control.vhd` | The DRP control FSM: one DRP access for each packet, the MMCM reset and the watchdog. |
| `hw/src/mmcm_wrapper.vhd` | The MMCM with all ports, for 7 series, UltraScale and UltraScale+. |
| `hw/src/heartbeat.vhd` | A counter that toggles its output every 10,000,000 clock cycles. |
| `hw/xdc/basys3.xdc` | Pins, clocks and bitstream settings. |
| `images/` | The block diagram. |

The build adds the BSCAN interface and the safe-startup PLL from `auxiliary_components/`.

## BSCAN register

| Register | Write (32 bits) | Read (24 bits) |
| --- | --- | --- |
| USER1 | The DRP packet. Bits 31:25: padding. Bit 24: MMCM RST. Bit 23: 1 = write, 0 = read. Bits 22:16: DRP address. Bits 15:0: DRP write data. | Bits 23:17: the current DRP address. Bits 16:1: the DO of the MMCM. Bit 0: the DRP error (watchdog timeout). |

The length of each direction is a whole number of bytes. The write has 7 padding bits for this reason.

On the Basys 3, LD0 shows the heartbeat of CLKOUT0 (`led_o[0]`) and LD1 the heartbeat of CLKOUT1 (`led_o[1]`).

## How the DRP control works

Each BSCAN write is one packet. On the rising edge of the BSCAN `avail` signal, the design moves the packet to the safe clock domain and gives the FSM a one-cycle command:

1. If bit 24 (RST) is 1, the FSM asserts RST of the MMCM and does one DRP access: DEN for one clock cycle, DWE = bit 23, with the address and the data of the packet. Then it waits for DRDY.
2. RST stays asserted between packets. A packet with bit 24 = 0 does no DRP access: it releases RST, and the MMCM locks again.
3. If DRDY does not come within 1023 clock cycles, the FSM sets the error bit and keeps RST asserted. The script then decides what to do. The next successful access clears the error bit.

The DO of the MMCM goes directly to the BSCAN read register. The script reads it after each read packet.

## How a reconfiguration works

The script changes the MMCM in the sequence of XAPP888:

1. Write the power register (`0x28`) with `0xFFFF`. This first packet also asserts RST.
2. For each register to change: read it, keep the bits outside the field, set the field, write it, and read it back to check it.
3. Release RST (a packet with bit 24 = 0) and wait 100 ms for the lock.

The registers of each output are ClkReg1 (PHASE MUX, HIGH TIME, LOW TIME) and ClkReg2 (MX, EDGE, NO COUNT, DELAY TIME, and the fractional bits of CLKOUT0). For an integer divide D with a 50 % duty cycle, HIGH TIME = D / 2 (rounded down), LOW TIME = D - HIGH TIME and EDGE = D mod 2. The VCO frequency does not change in this example, so the lock and filter registers stay as they are.

| Output | ClkReg1 | ClkReg2 |
| --- | --- | --- |
| CLKOUT0 | `0x08` | `0x09` |
| CLKOUT1 | `0x0A` | `0x0B` |

## The stages

The MMCM starts with a VCO of 1000 MHz (M = 10, D = 1) and CLKOUT0 and CLKOUT1 at 1000 MHz / 10 = 100 MHz. Each heartbeat toggles every 10,000,000 cycles of its clock. The script waits for Enter before each stage.

| # | Change | Result on the LEDs |
| --- | --- | --- |
| 0 | Program the FPGA. | Both LEDs toggle every 100 ms, together. |
| 1 | CLKOUT0 and CLKOUT1 divide 10 -> 50 (20 MHz), in one reconfiguration. | Both LEDs toggle every 0.5 s, together. |
| 2 | CLKOUT1 divide 100 (10 MHz) for 1 s, then 50 again. | The CLKOUT1 heartbeat falls 0.5 s behind, half of its 1 s blink period. The two LEDs blink in alternation. |

Stage 2 does not change the phase of the clock. It changes the offset between the two heartbeat counters. A phase shift of the MMCM moves a clock by less than one clock period (for example, 25 ns for 90 degrees at 10 MHz), so it does not show on LEDs that toggle every 0.5 s. `main.py` has the functions for a phase change (`phase_changes`, `phase_fields`) for a test with an oscilloscope.

## Requirements

- SK-RAFT server, with the board connected through JTAG.
- Vivado 2025.2 (the version that the Tcl script was written for) to build the design.
- Python 3.9 or a later version, with the `skraft` package (`api/python`).

## Generate the design

1. Open the Vivado Tcl shell and run the script:

   ```bash
   vivado -mode batch -source create_project.tcl
   ```

   The script creates the project `mmcm_drp_interface/mmcm_drp_interface.xpr` next to itself and builds the bitstream.
2. The `.bit` file goes to `mmcm_drp_interface/mmcm_drp_interface.runs/impl_1/`. `main.py` reads it from there.

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`.
2. Run the script:

   ```bash
   python src/main.py
   ```

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `SERIAL_NUMBER` | `"210183BFD452A"` | The serial number of the board. `get_devices()` gives the connected boards. |
| `SLOW_DIVIDE` | `50` | The divide of CLKOUT0 and CLKOUT1 in stage 1. |
| `LAG_DIVIDE` / `LAG_TIME_S` | `100` / `1.0` | The divide of CLKOUT1 in stage 2, and the time it runs at that divide, in seconds. |

## References

- XAPP888, *MMCM and PLL Dynamic Reconfiguration*: the bit fields and the DRP addresses of the MMCM registers, and the reconfiguration sequence.
