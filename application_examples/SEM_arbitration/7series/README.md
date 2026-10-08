# SEM arbitration: does the SEM detect upsets injected while it was frozen?

This example tests if the Soft Error Mitigation (SEM) controller of a 7-series device detects CRAM upsets that SK-RAFT injects while the SEM is stopped.

SK-RAFT and the SEM both use the configuration logic of the device. Thus the design has an arbitration block: SK-RAFT isolates the SEM from the ICAP and stops its clock before an injection, and connects it again after the injection. The script reads the reports of the SEM through the UART of the board.

## BSCAN registers

| Register | Write | Read |
| --- | --- | --- |
| USER1 | Clock enable of the SEM: 1 = the clock operates, 0 = the clock is stopped. The value at power-up is 0. | |
| USER2 | Isolation of the SEM: 1 = isolated from the ICAP, 0 = connected. | The actual state (1 = isolated). |

The order of the operations is important:

- Connect the SEM before you start its clock. If the SEM starts while it is isolated, it reads zeros from the ICAP and halts (`HLT`).
- Isolate the SEM only when it is idle (after the `I>` prompt). Do not isolate a SEM that operates.

## What the script does

The script waits for Enter before each stage. While it waits, it shows the UART output of the SEM.

1. It programs the design. The SEM is isolated and its clock is stopped.
2. It connects the SEM and starts its clock. The SEM starts. The script sends `I` (idle) and `S` (status) and reads the status.
3. It sends `I`, isolates the SEM and stops its clock.
4. It injects `INJECTION_NUMBER` random CRAM upsets into `pblock_1`. The pblock contains no logic, thus the upsets do not change the SEM or the UART. The SEM can detect the upsets, because its ECC and CRC check full frames.
5. It connects the SEM, starts its clock and sends `RESTART_COMMAND`. Then it reads the reports of the SEM and prints which injected bits the SEM found.
6. It programs the FPGA again to remove the upsets.

## Run the example

1. At the top of `example.py`, set `SK_RAFT_SERVER_IP`, `SERIAL_NUMBER` and the paths of the bitstream, EBD and XDC files in `design`.
2. Set `UART_PORT` to the COM port of the USB-UART of the board. The SEM monitor uses 9600 baud, 8-N-1.
3. Install pySerial (`pip install pyserial`), then run the script:

```bash
python example.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `TARGET_MEMORY` | `TargetMemory.CRAM` | The memory for the injections. |
| `TARGET_PBLOCK` | `"pblock_1"` | The pblock for the injections, as the XDC file names it. |
| `INJECTION_NUMBER` | `10` | The number of upsets in stage 4. |
| `RESTART_COMMAND` | `"O"` | The command that starts the SEM again after the injections: `O` (observation) or `R 00` (initialization). |

## Result

The script prints a table of the injected bits (FAR, word, bit, block type) and shows if the SEM reported each one. If the SEM reports locations that the script did not inject, or if the SEM halts, the script also prints this.

If you stop the script with Ctrl+C, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.
