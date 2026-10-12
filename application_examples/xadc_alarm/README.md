# XADC alarm: set off and clear the temperature alarm through JTAG

This example sets off and clears the temperature alarm (ALM0) of the XADC. The script moves the thresholds of the alarm around the temperature of the FPGA, and shows the state of the alarm from the flag register. The temperature does not change: only the thresholds move.

The example has five stages. Each stage waits for Enter. During a stage, the script reads the temperature, the thresholds and the alarm twice per second, and writes the line again in place:

```
Device: serial number 210183BA251CA, part number XC7A35T
Original values: CONFIG1 = 0000h, ALARM0 = 0000h, ALARM4 = 0000h
Temperature at the start: 46.4C. The thresholds move around this value.
--------------------------------------------------------------------------------

Stage 1 of 5: both thresholds are above the temperature. ALM0 is off.
Press Enter for the next stage.
Temp =   46.5C | lower =   51.4C | upper =   56.4C | ALM0 = off

Stage 2 of 5: the temperature is between the thresholds. ALM0 stays off.
Press Enter for the next stage.
Temp =   46.4C | lower =   41.4C | upper =   51.4C | ALM0 = off

Stage 3 of 5: the temperature is above the upper threshold. ALM0 goes on.
Press Enter for the next stage.
Temp =   46.5C | lower =   36.4C | upper =   41.4C | ALM0 = ON
```

The values above are an example. The values of your device and board are different.

The SK-RAFT server writes and reads the XADC registers through the JTAG interface (the `XADC_DRP` instruction). The example does not need a design, and it does not program the FPGA.

## How the temperature alarm works

ALM0 has hysteresis. Two alarm registers set its thresholds:

| Temperature | ALM0 |
| --- | --- |
| Above the upper threshold (`ALARM0`, `50h`) | Goes on. |
| Below the lower threshold (`ALARM4`, `54h`) | Goes off. |
| Between the two thresholds | Does not change. |

The XADC is in the default mode of the sequencer after power-up, and when the design does not use the XADC. In the default mode, the XADC disables all the alarms, except the over-temperature alarm (OT) (UG480, Sequencer Modes). Thus the script sets the XADC to the Independent ADC mode. In this mode, ADC A monitors the on-chip sensors as in the default mode, and the alarms operate. The values of the sensors continue to update.

## What the script does

1. It reads the original values of `CONFIG1`, `ALARM0` and `ALARM4`, and the temperature at the start (T).
2. It writes the thresholds of stage 1. Then it writes `CONFIG1` to set the Independent ADC mode.
3. It moves the thresholds for each stage, and shows the state of ALM0:

| Stage | Lower threshold | Upper threshold | ALM0 |
| --- | --- | --- | --- |
| 1 | T + 5C | T + 10C | Off |
| 2 | T - 5C | T + 5C | Stays off |
| 3 | T - 10C | T - 5C | Goes on |
| 4 | T - 5C | T + 5C | Stays on |
| 5 | T + 5C | T + 10C | Goes off |

Stages 2 and 4 use the same thresholds, but ALM0 is different: the state of ALM0 depends on the earlier stage. This is the hysteresis. Stage 1 puts ALM0 off, also if the alarm was on before the example.

4. It writes back the original values: `CONFIG1` first, then `ALARM0` and `ALARM4`. The script also does this step when you press Ctrl+C, or when an error occurs.

## Registers

| Register | Address | Access | Use in the example |
| --- | --- | --- | --- |
| `XadcRegister.FLAG` | `3Fh` | Read only | Bit 0: ALM0 (1 = on). Bit 10: JTGR (1 = the design allows only reads through JTAG). |
| `XadcRegister.CONFIG1` | `41h` | Read and write | The sequencer mode and the alarm enables. |
| `XadcRegister.ALARM0` | `50h` | Read and write | The upper threshold of the temperature alarm. |
| `XadcRegister.ALARM4` | `54h` | Read and write | The lower threshold of the temperature alarm. |

During the example, `CONFIG1` is `8FACh`:

| Bits | Name | Value | Meaning |
| --- | --- | --- | --- |
| 15-12 | SEQ3-SEQ0 | `1000` | Independent ADC mode. |
| 11-8 | ALM6-ALM3 | `1111` | The VCCBRAM alarm and the alarms of the PS supplies are disabled. |
| 7-4 | CAL3-CAL0 | `1010` | Offset and gain correction for the ADC and for the supply sensors. |
| 3-2 | ALM2-ALM1 | `11` | The VCCAUX and VCCINT alarms are disabled. |
| 1 | ALM0 | `0` | The temperature alarm is enabled. |
| 0 | OT | `0` | The over-temperature alarm is enabled, as in the default mode. |

The thresholds are raw 16-bit values. Bits 15-4 hold the 12-bit code of the temperature, and bits 3-0 are zero. The script converts between degrees Celsius and codes with the temperature transfer function of UG480 (on-chip reference): code = (T + 273.15) × 4096 / 503.975. `dev.xadc(TEMPERATURE)` uses the same function.

## Supported devices

| Board | Device | Family | Supported |
| --- | --- | --- | --- |
| Basys 3 | XC7A35T | 7 series | Yes |
| ZedBoard | XC7Z020 | Zynq-7000 | Yes |
| ZUBoard 1CG | XCZU1CG | Zynq UltraScale+ | No |

The script works with all the 7 series FPGAs and Zynq-7000 SoCs (UG480). On other devices, it stops before it writes a register. The System Monitor of Zynq UltraScale+ devices (SYSMON, UG580) has one ADC and a different temperature transfer function.

## Requirements

- SK-RAFT server, with the FPGA board connected through JTAG. The server must read the flag register.
- A 7 series FPGA or a Zynq-7000 device, for example one of the boards above.
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- A terminal that supports ANSI escape sequences, for example Windows Terminal, the Windows 10/11 console, or a Linux or macOS terminal.
- No design files. The example does not upload or program a bitstream.

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`.
2. Run the script:

```bash
cd src
python main.py
```

3. Press Enter to go to the next stage. After stage 5, press Enter to stop.

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `SERIAL_NUMBER` | `"210183BA251CA"` | The serial number of the target board. `get_devices()` gives the connected boards. |
| `MARGIN_C` | `5.0` | The distance between the thresholds and the temperature at the start, in degrees Celsius. The temperature must change by less than this value during the example. |
| `READ_PERIOD_S` | `0.5` | The time between two reads, in seconds. |

## Result

At the end, the script writes back the original values of `CONFIG1`, `ALARM0` and `ALARM4`. The XADC goes back to its original mode, for example the default mode. If the script cannot write back the values (for example, if the connection to the server stops), switch the board off and on, or program the FPGA again.

While the example runs, a design that uses the alarm outputs of the XADC (ALM and OT) sees the changes of the alarm. Thus run the example with a design that does not use the XADC, or with no design.

## Use the alarm registers in your own script

```python
from skraft import SkraftFpga, XadcRegister

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BA251CA") as dev:
        upper = dev.read_xadc_register(XadcRegister.ALARM0)  # raw 16 bits
        dev.write_xadc_register(XadcRegister.ALARM0, upper)
        flags = dev.read_xadc_register(XadcRegister.FLAG)
        print("ALM0 is on" if flags & 0x0001 else "ALM0 is off")
```

`dev.read_xadc_register()` reads the flag register (`3Fh`), the configuration registers (`40h` to `42h`) and the alarm registers (`50h` to `5Fh`). `dev.write_xadc_register()` writes the configuration registers and the alarm registers. The flag register is read only. Both functions accept an `XadcRegister`, or the DRP address as an `int`. The values are raw 16-bit contents: UG480 gives the meaning of each bit. The server refuses the other addresses, for example the test registers (`43h` to `47h`) and the sequence registers (`48h` to `4Fh`). If a read or a write fails, the functions raise `XadcError`.

Caution: the four least significant bits of `ALARM3` (`53h`) select the automatic shutdown at the over-temperature limit. The value `0011b` enables it, if the bitstream also enables it (`BITSTREAM.CONFIG.OVERTEMPPOWERDOWN`). Then the device shuts down when the temperature is above the limit in `ALARM3`.

## Troubleshooting

| Problem | Cause | Solution |
| --- | --- | --- |
| `This example is for 7 series FPGAs and Zynq-7000 SoCs only.` | The device is not a 7 series or Zynq-7000 device, for example a Zynq UltraScale+ device. | Use a 7 series or Zynq-7000 board. |
| `The design allows only reads of the XADC through JTAG (JTAG_XADC = StatusOnly).` | The design sets `BITSTREAM.GENERAL.JTAG_XADC` to `StatusOnly`. | Program the FPGA with a design that does not limit the JTAG access to the XADC. |
| `Example failed: ALARM0 is 0000h after the write of ...h` | The XADC ignores the writes through JTAG. A possible cause: the design disables the JTAG access to the XADC (`BITSTREAM.GENERAL.JTAG_XADC` is `Disable`), or the PS of a Zynq-7000 device uses the XADC through its dedicated interface. | Program the FPGA with a design that does not disable the JTAG access. |
| `DRP address 3Fh is not an XADC configuration or alarm register` | The SK-RAFT server is older than the client, and does not read the flag register. | Update the SK-RAFT server. |
| ALM0 does not go on in stage 3 | The design uses the XADC, and changes `CONFIG1` or the thresholds through the DRP of the XADC. | Run the example with a design that does not use the XADC, or with no design. |
| The line shows `←[K`, or a new line appears at each read | The terminal does not support ANSI escape sequences (for example, some IDE consoles). | Run the script in a terminal window. |
