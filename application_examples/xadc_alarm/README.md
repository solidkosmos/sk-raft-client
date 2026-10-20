# XADC alarm: set off and clear the temperature alarm through JTAG

This example sets off and clears the temperature alarm (ALM0) of the XADC. The script moves the thresholds of the alarm around the temperature of the FPGA, and shows the state of the alarm. The temperature does not change: only the thresholds move.

The example has five stages. Each stage waits for Enter. During a stage, the script reads the temperature, the thresholds and the alarm twice per second, and writes the line again in place:

```
Device: serial number 210183BA251CA, part number XC7A35T
Original values: CONFIG0 = 0000h, CONFIG1 = 0000h, lower = -273.1C, upper = -273.1C
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

The script gives the thresholds in degrees Celsius. The SK-RAFT server converts them into the values of the alarm registers, with the transfer function of the family of the device, and decodes the state of the alarms from the flag register. The server accesses the XADC through the JTAG interface (the `XADC_DRP` instruction). The example does not need a design, and it does not program the FPGA.

## How the temperature alarm works

ALM0 has hysteresis. Two thresholds control it:

| Temperature | ALM0 |
| --- | --- |
| Above the upper threshold (`TEMPERATURE_UPPER`, alarm register `50h`) | Goes on. |
| Below the lower threshold (`TEMPERATURE_LOWER`, alarm register `54h`) | Goes off. |
| Between the two thresholds | Does not change. |

The XADC is in the default mode of the sequencer after power-up, and when the design does not use the XADC. In the default mode, the XADC disables all the alarms, except the over-temperature alarm (OT) (UG480 and UG580, Sequencer Modes). Thus the script sets the XADC to the single channel mode, on the temperature sensor. In this mode, the XADC converts only the temperature, and the alarms operate. The other sensors keep their last values until the end of the example.

The single channel mode is available in the XADC of the 7 series devices (UG480) and in the SYSMON of the UltraScale and UltraScale+ devices (UG580), with the same register values. Thus the same script operates on all these devices.

## What the script does

1. It reads the original values of `CONFIG0`, `CONFIG1` and of the two thresholds, and the temperature at the start (T).
2. It sets the thresholds of stage 1. Then it writes `CONFIG0` and `CONFIG1` to set the single channel mode, on the temperature sensor.
3. It moves the thresholds for each stage, and shows the state of ALM0:

| Stage | Lower threshold | Upper threshold | ALM0 |
| --- | --- | --- | --- |
| 1 | T + 5C | T + 10C | Off |
| 2 | T - 5C | T + 5C | Stays off |
| 3 | T - 10C | T - 5C | Goes on |
| 4 | T - 5C | T + 5C | Stays on |
| 5 | T + 5C | T + 10C | Goes off |

Stages 2 and 4 use the same thresholds, but ALM0 is different: the state of ALM0 depends on the earlier stage. This is the hysteresis. Stage 1 puts ALM0 off, also if the alarm was on before the example.

4. It writes back the original values: `CONFIG1` first, then `CONFIG0` and the two thresholds. The script also does this step when you press Ctrl+C, or when an error occurs.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `dev.xadc_alarm(TEMPERATURE_UPPER)`, `dev.xadc_alarm(TEMPERATURE_LOWER)` | Read a threshold, in degrees Celsius. |
| `dev.set_xadc_alarm(TEMPERATURE_UPPER, value)`, `dev.set_xadc_alarm(TEMPERATURE_LOWER, value)` | Set a threshold, in degrees Celsius. The server converts the value, writes the alarm register and reads it back. |
| `dev.xadc_flags()` | Read the state of the alarms: `temperature` is ALM0. `jtag_read_only` shows if the design allows only reads through JTAG. |
| `dev.xadc(TEMPERATURE)` | Read the temperature, in degrees Celsius. |
| `dev.read_xadc_register(XadcRegister.CONFIG0)`, `dev.write_xadc_register(XadcRegister.CONFIG0, value)` | Read and write the channel of the single channel mode, as a raw 16-bit value. |
| `dev.read_xadc_register(XadcRegister.CONFIG1)`, `dev.write_xadc_register(XadcRegister.CONFIG1, value)` | Read and write the mode of the sequencer, as a raw 16-bit value. |

During the example, `CONFIG0` is `1000h`:

| Bits | Name | Value | Meaning |
| --- | --- | --- | --- |
| 13-12 | AVG1-AVG0 | `01` | Average of 16 samples, as in the default mode. |
| 5-0 | CH5-CH0 | `000000` | The on-chip temperature sensor. |

During the example, `CONFIG1` is `3FDCh`:

| Bits | Name | Value | Meaning |
| --- | --- | --- | --- |
| 15-12 | SEQ3-SEQ0 | `0011` | Single channel mode (sequencer off). |
| 11-8 | ALM6-ALM3 | `1111` | The VCCBRAM alarm and the alarms of the PS supplies are disabled. |
| 7-4 | CAL3-CAL0 | `1101` | Correction of the ADC offset and of the supply sensors. CAL1 is `0`, because the UltraScale SYSMON does not support it. |
| 3-2 | ALM2-ALM1 | `11` | The VCCAUX and VCCINT alarms are disabled. |
| 1 | ALM0 | `0` | The temperature alarm is enabled. |
| 0 | OT | `0` | The over-temperature alarm is enabled, as in the default mode. |

## Supported devices

| Family | Monitor | Temperature transfer function | Boards, for example |
| --- | --- | --- | --- |
| 7 series, Zynq-7000 | XADC (UG480) | 503.975 / 273.15 | Basys 3 (XC7A35T), ZedBoard (XC7Z020) |
| UltraScale | SYSMONE1 (UG580) | 501.3743 / 273.6777 (on-chip reference) | |
| UltraScale+, Zynq UltraScale+ | SYSMONE4 (UG580) | 509.3140064 / 280.2308787 (internal reference) | ZUBoard 1CG (XCZU1CG) |

The script is the same for all these devices. The server selects the temperature transfer function by the family of the device. The server refuses the devices of other families, for example Versal devices.

## Requirements

- SK-RAFT server, with the FPGA board connected through JTAG. The server must support the XADC alarms (`FpgaXadcAlarm`, `FpgaXadcSetAlarm` and `FpgaXadcFlags`).
- A 7 series, UltraScale or UltraScale+ device, for example one of the boards above.
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

At the end, the script writes back the original values of `CONFIG0`, `CONFIG1` and of the two thresholds. The XADC goes back to its original mode, for example the default mode, and all the sensors update again. If the script cannot write back the values (for example, if the connection to the server stops), switch the board off and on, or program the FPGA again.

While the example runs, a design that uses the XADC sees the changes: only the temperature updates, and the alarm outputs (ALM and OT) change. Thus run the example with a design that does not use the XADC, or with no design.

## Use the alarms in your own script

```python
from skraft import SkraftFpga, TEMPERATURE_UPPER, VCCINT_LOWER

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BA251CA") as dev:
        print(dev.xadc_alarm(TEMPERATURE_UPPER).value)  # degrees Celsius
        dev.set_xadc_alarm(TEMPERATURE_UPPER, 85.0)     # degrees Celsius
        dev.set_xadc_alarm(VCCINT_LOWER, 0.97)          # volts
        flags = dev.xadc_flags()
        print("ALM0 is on" if flags.temperature else "ALM0 is off")
```

`dev.xadc_alarm()` returns an `XadcAlarm` with two attributes: `addr`, the DRP address of the alarm register, and `value`, the threshold in SI units. `dev.set_xadc_alarm()` sets a threshold in SI units. Both functions accept a selector of the `skraft` library, or the DRP address of the alarm register:

| Selectors (upper, lower) | Alarm registers | Unit | Devices |
| --- | --- | --- | --- |
| `TEMPERATURE_UPPER`, `TEMPERATURE_LOWER` | `50h`, `54h` | degC | All |
| `OT_LIMIT`, `OT_RESET` | `53h`, `57h` | degC | All |
| `VCCINT_UPPER`, `VCCINT_LOWER` | `51h`, `55h` | V | All |
| `VCCAUX_UPPER`, `VCCAUX_LOWER` | `52h`, `56h` | V | All |
| `VCCBRAM_UPPER`, `VCCBRAM_LOWER` | `58h`, `5Ch` | V | All |
| `VCCPINT_UPPER`, `VCCPINT_LOWER` | `59h`, `5Dh` | V | Zynq-7000 only |
| `VCCPAUX_UPPER`, `VCCPAUX_LOWER` | `5Ah`, `5Eh` | V | Zynq-7000 only |
| `VCCO_DDR_UPPER`, `VCCO_DDR_LOWER` | `5Bh`, `5Fh` | V | Zynq-7000 only |

The server converts the thresholds with the transfer functions of UG480 and UG580, the same functions as `dev.xadc()`. For the temperatures, it uses the transfer function of the family of the device (see Supported devices). It keeps the four least significant bits of the alarm register, and reads the register back after the write. A threshold outside the range of the ADC (for example, -273.15 to 230.70 degC and 0 to 2.9993 V for the 7 series) causes an error that gives the range.

`dev.xadc_flags()` returns an `XadcFlags`. The attributes `temperature`, `vccint`, `vccaux`, `over_temperature`, `vccbram`, `vccpint`, `vccpaux` and `vcco_ddr` are `True` while the alarm is on. The attributes `internal_reference`, `jtag_read_only` and `jtag_disabled` show the reference of the ADC and the JTAG access that the design allows. The flag register (`3Fh`) has the same bits in the XADC and in the SYSMON.

If a read or a write fails, the functions raise `XadcError`.

Caution: the four least significant bits of the `OT_LIMIT` register (`53h`) control the over-temperature limit. In 7 series devices, the value `0011b` enables the automatic shutdown, if the bitstream also enables it (`BITSTREAM.CONFIG.OVERTEMPPOWERDOWN`). If the register holds `0000h`, the limit is 125 degC. In UltraScale and UltraScale+ devices, the value `0011b` enables the limit of `OT_LIMIT`, else the limit is 125 degC. The automatic shutdown needs `BITSTREAM.CONFIG.OVERTEMPSHUTDOWN`. When the automatic shutdown is enabled, the device shuts down when the temperature is above the limit. `dev.set_xadc_alarm()` does not change these four bits.

## Troubleshooting

| Problem | Cause | Solution |
| --- | --- | --- |
| `the XADC of the ... family is not supported` | The device does not have an XADC or a SYSMON that the server supports, for example a Versal device. | Use a 7 series, UltraScale or UltraScale+ device. |
| `The design allows only reads of the XADC through JTAG (JTAG_XADC = StatusOnly).` | The design sets `BITSTREAM.GENERAL.JTAG_XADC` (or `JTAG_SYSMON`) to `StatusOnly`. | Program the FPGA with a design that does not limit the JTAG access to the XADC. |
| `XADC alarm 50h holds ...h after the write of ...h, the design may limit the JTAG access to the XADC` | The XADC ignores the writes through JTAG. A possible cause: the design disables the JTAG access to the XADC (`JTAG_XADC` or `JTAG_SYSMON` is `Disable`), or the PS of a Zynq-7000 device uses the XADC through its dedicated interface. | Program the FPGA with a design that does not disable the JTAG access. |
| `failed to read the XADC flags: unknown method FpgaXadcFlags ...` | The SK-RAFT server is older than the client, and does not support the XADC alarms. | Update the SK-RAFT server. |
| ALM0 goes off in stage 4 (UltraScale+ devices) | Bit 0 of the lower temperature register (`54h`) is `1`: the temperature alarm operates in the window mode, not in the hysteresis mode (UG580, Thermal Management). The server keeps this bit. | Use a design that keeps the hysteresis mode (bit 0 of `INIT_54` is `0`), or no design. |
| ALM0 does not go on in stage 3 | The design uses the XADC, and changes `CONFIG0`, `CONFIG1` or the thresholds through the DRP of the XADC. | Run the example with a design that does not use the XADC, or with no design. |
| The line shows `←[K`, or a new line appears at each read | The terminal does not support ANSI escape sequences (for example, some IDE consoles). | Run the script in a terminal window. |
