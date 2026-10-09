# XADC sensors: temperature and voltages through JTAG

This example reads the temperature and voltage sensors of the FPGA once per second. Each sensor has one line, with its current value and its highest and lowest values. The script writes the lines again after each read, so the values update in place:

```
<<<<<<< HEAD
xadc_monitor/
├── README.md
├── hw/
│   ├── build.tcl                     Vivado build script
│   ├── src/
│   │   ├── xadc_top.vhd              Top level: XADC, DRP read, snapshot
│   │   ├── bscan_interface.vhd       BSCAN modules (same as get_started/hw)
│   │   ├── bscan_primitive_wrapper.vhd
│   │   └── bscan_user_register_io.vhd
│   └── xdc/
│       ├── basys3.xdc
│       ├── zedboard.xdc
│       └── custom_template.xdc
├── images/
└── src/
    ├── main.py                       SK-RAFT client script
    ├── design_files/                 build.tcl writes the files here
    └── logs/                         main.py writes the CSV logs here
=======
Temp  =   46.4C | max=  47.2C | min=  30.1C
vint  =   999mV | max= 1003mV | min=  997mV
vaux  =  1799mV | max= 1802mV | min= 1796mV
vbram =  1000mV | max= 1002mV | min=  998mV
>>>>>>> b57b130069baef9b83cf8c881d2ee9eb5b9dab2b
```

The values above are an example. The values of your device and board are different.

The SK-RAFT server reads the sensors from the XADC of the FPGA, through the JTAG interface (the `XADC_DRP` instruction, UG480). The example does not need a design, and it does not program the FPGA. If the FPGA is not configured, or the design does not use the XADC, the XADC monitors the on-chip sensors by itself.

The example supports 7 series FPGAs and Zynq-7000 devices, for example the Basys 3 and the ZedBoard.

## What the example reads

| Label | Sensor | Selectors (value, max, min) | XADC status registers | Unit | Devices |
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
- A 7 series FPGA or a Zynq-7000 device. The server does not read the sensors of other device families.
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- A terminal that supports ANSI escape sequences, for example Windows Terminal, the Windows 10/11 console, or a Linux or macOS terminal.
- No design files. The example does not upload or program a bitstream.

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`. For a Zynq-7000 device, also set `ZYNQ = True`.
2. Run the script:

```bash
cd src
python main.py
```

3. Press Enter to stop.

| Constant | Default | Description |
| --- | --- | --- |
| `SK_RAFT_SERVER_IP` / `SK_RAFT_SERVER_PORT` | `"127.0.0.1"` / `50051` | The address of the SK-RAFT server. |
| `SERIAL_NUMBER` | `"210183BA251CA"` | The serial number of the target board. `get_devices()` gives the connected boards. |
| `ZYNQ` | `False` | `True` adds the PS supplies (`vpint`, `vpaux`, `vddr`). Set it only for a Zynq-7000 device. Other devices do not have these sensors, and the script stops with an error. |
| `READ_PERIOD_S` | `1.0` | The time between two reads, in seconds. |

## Result

The script only reads the sensors. It does not change the configuration of the FPGA. Thus you can run it before or after the other examples, with no reprogramming.

## Read the XADC in your own script

```python
from skraft import SkraftFpga, TEMPERATURE, VCCINT, MAX_VCCINT

with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
    with client.attach("210183BA251CA") as dev:
        print(dev.xadc(TEMPERATURE).value)  # degrees Celsius
        print(dev.xadc(VCCINT).value)       # volts
        print(dev.xadc(MAX_VCCINT).value)   # volts, highest since power-up
        print(dev.xadc(0x01).value)         # volts: VCCINT, by its DRP address
```

`dev.xadc()` accepts a selector of the `skraft` library, or the DRP address of an XADC status register (UG480). It returns an `XadcSensor` with two attributes:

- `addr`: the DRP address that the server read.
- `value`: the value, in SI units. Degrees Celsius for temperatures, volts for voltages.

The library has a selector for each sensor in the table above. It also has `VREFP` and `VREFN`, the voltages on the reference inputs of the ADC. On a board that uses the on-chip reference of the XADC, these pins connect to ground, and both values are 0 V. Thus the example does not show them.

The server reads only the on-chip sensors. It does not read the external analog inputs (VP/VN and VAUX), the calibration registers or the flag register. If a read fails, `dev.xadc()` raises `XadcError`. `XadcError` is a `SkraftError`.

## Troubleshooting

| Problem | Cause | Solution |
| --- | --- | --- |
| `... has no XADC, it is available only in 7 series FPGAs and Zynq-7000 SoCs` | The device is not a 7 series device. | Use a 7 series FPGA or a Zynq-7000 device. |
| `XADC sensor 0Dh is available only in Zynq-7000 SoCs, not in ...` | `ZYNQ = True`, but the device is not a Zynq-7000 device. | Set `ZYNQ = False`. |
| `DRP address ...h is not an XADC sensor` | Your script gives a DRP address that is not a supported sensor. | Use a selector, or an address from the table above. |
| `Temp` is approximately -273C and all voltages are 0mV | The XADC returned only zeros. A possible cause: the design on the FPGA disables the JTAG access to the XADC (`BITSTREAM.GENERAL.JTAG_XADC`). | Program the FPGA with a design that does not disable the JTAG access. |
| A new block of lines appears each second | The terminal does not support ANSI escape sequences (for example, some IDE consoles). | Run the script in a terminal window. |
