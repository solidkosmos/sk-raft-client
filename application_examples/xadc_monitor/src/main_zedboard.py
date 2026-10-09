# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example: read the temperatures and the voltages of the ZedBoard
(Zynq-7000, XC7Z020).

The script reads all the temperature and voltage sensors of the FPGA once
per second, until you press Enter. The server reads the sensors from the
XADC, through the JTAG interface. Each sensor has one line, with its
current value and its highest and lowest values since power-up or the
last XADC reset. The script writes the lines again after each read.

The XADC does not need a design. If the design does not use the XADC, or
the FPGA is not configured, the XADC monitors the on-chip sensors by
itself. Thus, the script does not program the FPGA. Note: a design can
disable the JTAG access to the XADC (BITSTREAM.GENERAL.JTAG_XADC).

dev.xadc() gives the values in SI units: degrees Celsius (C) for
temperatures and volts (V) for voltages. The script shows the voltages in
millivolts (mV).
"""

import os
import threading

from skraft import (
    MAX_TEMPERATURE,
    MAX_VCCAUX,
    MAX_VCCBRAM,
    MAX_VCCINT,
    MAX_VCCO_DDR,
    MAX_VCCPAUX,
    MAX_VCCPINT,
    MIN_TEMPERATURE,
    MIN_VCCAUX,
    MIN_VCCBRAM,
    MIN_VCCINT,
    MIN_VCCO_DDR,
    MIN_VCCPAUX,
    MIN_VCCPINT,
    TEMPERATURE,
    VCCAUX,
    VCCBRAM,
    VCCINT,
    VCCO_DDR,
    VCCPAUX,
    VCCPINT,
    SkraftError,
    SkraftFpga,
)

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210248781184"

# The ZedBoard has a Zynq-7000 device. Thus ZYNQ is True, and the script
# also reads the supplies of the Processing System (PS).
ZYNQ = True

# The time between two reads, in seconds.
READ_PERIOD_S = 1.0

# The sensors, one line each: (label, current value, highest value,
# lowest value).
TEMPERATURES = [
    ("Temp", TEMPERATURE, MAX_TEMPERATURE, MIN_TEMPERATURE),
]
# The supply voltages.
VOLTAGES = [
    ("vint", VCCINT, MAX_VCCINT, MIN_VCCINT),
    ("vaux", VCCAUX, MAX_VCCAUX, MIN_VCCAUX),
    ("vbram", VCCBRAM, MAX_VCCBRAM, MIN_VCCBRAM),
]
# The PS supply voltages, Zynq-7000 only.
PS_VOLTAGES = [
    ("vpint", VCCPINT, MAX_VCCPINT, MIN_VCCPINT),
    ("vpaux", VCCPAUX, MAX_VCCPAUX, MIN_VCCPAUX),
    ("vddr", VCCO_DDR, MAX_VCCO_DDR, MIN_VCCO_DDR),
]

# A background thread monitors the Enter key. Thus, the read loop below
# does not wait for input. Press Enter at any time to stop.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# The script writes the lines again in place with ANSI escape sequences.
# os.system("") makes the classic Windows console accept these sequences.
# Other terminals ignore this call.
os.system("")
CLEAR_TO_END_OF_LINE = "\033[K"


def lines_up(n: int) -> str:
    # Move the cursor to the start of the line n lines up.
    return f"\033[{n}F"


def celsius(value: float) -> str:
    return f"{value:6.1f}C"  # dev.xadc() gives C


def millivolts(value: float) -> str:
    return f"{value * 1000:5.0f}mV"  # dev.xadc() gives V


def sensor_lines(dev, voltages) -> list[str]:
    # SK-RAFT: each dev.xadc() call reads one XADC sensor. The script
    # reads all the sensors first. Then it writes all the lines.
    lines = []
    for sensors, show in ((TEMPERATURES, celsius), (voltages, millivolts)):
        for label, current, highest, lowest in sensors:
            lines.append(f"{label:<5} = {show(dev.xadc(current).value)} | "
                         f"max={show(dev.xadc(highest).value)} | "
                         f"min={show(dev.xadc(lowest).value)}")
    return lines


def main() -> None:
    voltages = VOLTAGES + PS_VOLTAGES if ZYNQ else VOLTAGES
    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:

            with client.attach(SERIAL_NUMBER) as dev:
                print(f"Device: serial number {dev.serial_number}, "
                      f"part number {dev.part_number}")
                print("Reading the XADC once per second. "
                      "Press Enter to stop.")
                print("max/min: the highest and lowest values since "
                      "power-up or the last XADC reset.")
                print("-" * 80)
                watch_for_enter()
                written = 0  # the number of lines on the screen
                while True:
                    lines = sensor_lines(dev, voltages)
                    # Go back to the first line. Then write all the lines
                    # again.
                    if written:
                        print(lines_up(written), end="")
                    for line in lines:
                        print(f"{line}{CLEAR_TO_END_OF_LINE}")
                    written = len(lines)
                    if stop.wait(READ_PERIOD_S):
                        break
    except SkraftError as e:
        print(f"Example failed: {e}")
        return
    except KeyboardInterrupt:
        print("Interrupted.")
        return

    print("Example done.")


if __name__ == "__main__":
    main()
