# XADC monitor: temperature and voltages through JTAG

This example reads the temperature and voltage sensors of the FPGA once per second. Each sensor has one line, with its current value and its highest and lowest values. The script writes the lines again after each read, so the values update in place:

```
Device: serial number 210183BA251CA, part number XC7A35T
Reading the XADC once per second. Press Enter to stop.
max/min: the highest and lowest values since power-up or the last XADC reset.
--------------------------------------------------------------------------------
Temp  =   46.4C | max=  47.2C | min=  30.1C
vint  =   999mV | max= 1003mV | min=  997mV
vaux  =  1799mV | max= 1802mV | min= 1796mV
vbram =  1000mV | max= 1002mV | min=  998mV
```

The values above are an example. The values of your device and board are different. The first line shows the serial number of the JTAG cable and the part number of the device that the SK-RAFT server selected.

The SK-RAFT server reads the sensors through the JTAG interface (the `XADC_DRP` instruction). The example does not need a design, and it does not program the FPGA. If the FPGA is not configured, or the design does not use the sensors, the device monitors its on-chip sensors by itself.

## Supported devices

The folder has one script for each board:

| Script | Board | Device | Family | PS supplies |
| --- | --- | --- | --- | --- |
| `src/main_basys3.py` | Basys 3 | XC7A35T | 7 series | No |
| `src/main_zedboard.py` | ZedBoard | XC7Z020 | Zynq-7000 | Yes (`vpint`, `vpaux`, `vddr`) |
| `src/main_zuboard_1cg.py` | ZUBoard 1CG | XCZU1CG | Zynq UltraScale+ | No |

The scripts are the same, except for the `ZYNQ` setting. `src/main_basys3.py` also works with other 7 series boards. For another Zynq-7000 board, use `src/main_zedboard.py`.

In 7 series and Zynq-7000 devices, the sensors are in the XADC (UG480). In Zynq UltraScale+ devices, they are in the System Monitor, SYSMON (UG580). The `skraft` library and the scripts call both of them XADC.

## What the example reads

| Label | Sensor | Selectors (value, max, min) | Status registers | Unit | Devices |
| --- | --- | --- | --- | --- | --- |
| `Temp` | Die temperature | `TEMPERATURE`, `MAX_TEMPERATURE`, `MIN_TEMPERATURE` | `00h`, `20h`, `24h` | C | All |
| `vint` | Internal core supply | `VCCINT`, `MAX_VCCINT`, `MIN_VCCINT` | `01h`, `21h`, `25h` | mV | All |
| `vaux` | Auxiliary supply | `VCCAUX`, `MAX_VCCAUX`, `MIN_VCCAUX` | `02h`, `22h`, `26h` | mV | All |
| `vbram` | Block RAM supply | `VCCBRAM`, `MAX_VCCBRAM`, `MIN_VCCBRAM` | `06h`, `23h`, `27h` | mV | All |
| `vpint` | PS internal supply | `VCCPINT`, `MAX_VCCPINT`, `MIN_VCCPINT` | `0Dh`, `28h`, `2Ch` | mV | Zynq-7000 only |
| `vpaux` | PS auxiliary supply | `VCCPAUX`, `MAX_VCCPAUX`, `MIN_VCCPAUX` | `0Eh`, `29h`, `2Dh` | mV | Zynq-7000 only |
| `vddr` | PS DDR I/O supply | `VCCO_DDR`, `MAX_VCCO_DDR`, `MIN_VCCO_DDR` | `0Fh`, `2Ah`, `2Eh` | mV | Zynq-7000 only |

`max` and `min` are the highest and the lowest values since power-up or the last XADC reset.

## Requirements

- SK-RAFT server, with the FPGA board connected through JTAG.
- A 7 series FPGA, a Zynq-7000 device or a Zynq UltraScale+ device, for example one of the boards above.
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- A terminal that supports ANSI escape sequences, for example Windows Terminal, the Windows 10/11 console, or a Linux or macOS terminal.
- No design files. The example does not upload or program a bitstream.

## Run the example

1. At the top of the script for your board, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`.
2. Run the script for your board:

```bash
cd src
python main_basys3.py        # Basys 3, or another 7 series board
python main_zedboard.py      # ZedBoard
python main_zuboard_1cg.py   # ZUBoard 1CG
```

3. Press Enter to stop.

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `SERIAL_NUMBER` | `"210183BA251CA"` | The serial number of the target board. `get_devices()` gives the connected boards. |
| `ZYNQ` | `True` in `main_zedboard.py`, `False` in the other scripts | `True` adds the PS supplies (`vpint`, `vpaux`, `vddr`). Set it only for a Zynq-7000 device. The server reads these sensors only in Zynq-7000 devices: on other devices, the script stops with an error. |
| `READ_PERIOD_S` | `1.0` | The time between two reads, in seconds. |

## Result

The script only reads the sensors. It does not change the configuration of the FPGA. Thus you can run it before or after the other examples, with no reprogramming.

## Read the XADC in your own script

```python
from skraft import SkraftFpga, TEMPERATURE, VCCINT, MAX_VCCINT

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BA251CA") as dev:
        print(dev.serial_number, dev.part_number)
        print(dev.xadc(TEMPERATURE).value)  # degrees Celsius
        print(dev.xadc(VCCINT).value)       # volts
        print(dev.xadc(MAX_VCCINT).value)   # volts, highest since power-up
        print(dev.xadc(0x01).value)         # volts: VCCINT, by its DRP address
```

`client.attach()` returns the device with its serial number and its part number. `dev.xadc()` accepts a selector of the `skraft` library, or the DRP address of a status register (UG480, UG580). It returns an `XadcSensor` with two attributes:

- `addr`: the DRP address that the server read.
- `value`: the value, in SI units. Degrees Celsius for temperatures, volts for voltages.

The library has a selector for each sensor in the table above. It also has `VREFP` and `VREFN`, the voltages on the reference inputs of the ADC. On a board that uses the on-chip reference, these pins connect to ground, and both values are 0 V. Thus the example does not show them.

`dev.xadc()` reads only the on-chip sensors. It does not read the external analog inputs (VP/VN and VAUX), the calibration registers or the flag register. For the alarms and the flag register, use `dev.xadc_alarm()`, `dev.set_xadc_alarm()` and `dev.xadc_flags()`: see the `xadc_alarm` example. If a read fails, `dev.xadc()` raises `XadcError`. `XadcError` is a `SkraftError`.

## Troubleshooting

| Problem | Cause | Solution |
| --- | --- | --- |
| `XADC sensor 0Dh is available only in Zynq-7000 SoCs, not in ...` | `ZYNQ = True`, but the device is not a Zynq-7000 device. | Set `ZYNQ = False`, or use the script for your board. |
| `DRP address ...h is not an XADC sensor` | Your script gives a DRP address that is not a supported sensor. | Use a selector, or an address from the table above. |
| `Temp` is approximately -273C and all voltages are 0mV | The device returned only zeros. A possible cause: the design on the FPGA disables the JTAG access to the sensors (`BITSTREAM.GENERAL.JTAG_XADC` on 7 series and Zynq-7000 devices). | Program the FPGA with a design that does not disable the JTAG access. |
| The part number is empty | The SK-RAFT server is older than the client, and does not send the part number. | Update the SK-RAFT server. |
| A new block of lines appears each second | The terminal does not support ANSI escape sequences (for example, some IDE consoles). | Run the script in a terminal window. |
