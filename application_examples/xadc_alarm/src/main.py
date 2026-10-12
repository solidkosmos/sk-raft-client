# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example: set off and clear the temperature alarm of the XADC.

The script moves the thresholds of the temperature alarm (ALM0) of the
XADC around the temperature of the FPGA, and shows the state of the alarm.
The temperature does not change, only the thresholds move. The server
writes the alarm registers and reads the flag register through the JTAG
interface. The script does not program the FPGA.

ALM0 has hysteresis. It goes on when the temperature is above the upper
threshold (ALARM0, 50h). Then it stays on until the temperature is below
the lower threshold (ALARM4, 54h).

In the default mode of the sequencer, the XADC disables all the alarms,
except the over-temperature alarm (OT). Thus the script sets the XADC to
the Independent ADC mode (CONFIG1, 41h). In this mode, ADC A monitors the
on-chip sensors as in the default mode, and the alarms operate. At the
end, the script writes back the original values of CONFIG1, ALARM0 and
ALARM4.

The script is for 7 series FPGAs and Zynq-7000 SoCs (UG480).
"""

import os
import threading

from skraft import TEMPERATURE, SkraftError, SkraftFpga, XadcRegister

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BA251CA"

# The distance between the thresholds and the temperature at the start,
# in degrees Celsius. During the example, the temperature of the die
# changes by less than this distance.
MARGIN_C = 5.0

# The time between two reads, in seconds.
READ_PERIOD_S = 0.5

# The registers of the temperature alarm.
UPPER = XadcRegister.ALARM0  # 50h: ALM0 goes on above this temperature
LOWER = XadcRegister.ALARM4  # 54h: ALM0 goes off below this temperature

# The value of CONFIG1 (41h) during the example (UG480, Control
# Registers):
#   bits 15-12  SEQ3-SEQ0 = 1000: Independent ADC mode.
#   bits 11-8   ALM6-ALM3 = 1111: VCCBRAM and PS supply alarms disabled.
#   bits 7-4    CAL3-CAL0 = 1010: offset and gain correction for the ADC
#               and for the supply sensors.
#   bits 3-2    ALM2-ALM1 = 11: VCCAUX and VCCINT alarms disabled.
#   bit 1       ALM0 = 0: temperature alarm enabled.
#   bit 0       OT = 0: over-temperature alarm enabled, as in default mode.
ALARM_MODE = 0x8FAC

# The bits of the flag register (3Fh).
FLAG_ALM0 = 0x0001  # 1: the temperature alarm is on
FLAG_JTGR = 0x0400  # 1: the design allows only reads through JTAG

# The stages of the example: (what happens, lower threshold, upper
# threshold). The thresholds are distances from the temperature at the
# start, in degrees Celsius. Stages 2 and 4 use the same thresholds, but
# ALM0 is different: this is the hysteresis.
STAGES = [
    ("both thresholds are above the temperature. ALM0 is off.",
     MARGIN_C, 2 * MARGIN_C),
    ("the temperature is between the thresholds. ALM0 stays off.",
     -MARGIN_C, MARGIN_C),
    ("the temperature is above the upper threshold. ALM0 goes on.",
     -2 * MARGIN_C, -MARGIN_C),
    ("the temperature is between the thresholds. ALM0 stays on.",
     -MARGIN_C, MARGIN_C),
    ("the temperature is below the lower threshold. ALM0 goes off.",
     MARGIN_C, 2 * MARGIN_C),
]

# A background thread monitors the Enter key. Thus, the read loop below
# does not wait for input. Press Enter at any time to go to the next stage.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# The script writes the line of the alarm again in place with ANSI escape
# sequences. os.system("") makes the classic Windows console accept these
# sequences. Other terminals ignore this call.
os.system("")
CLEAR_TO_END_OF_LINE = "\033[K"


# The temperature transfer function of the XADC, with the on-chip reference
# (UG480, ADC Transfer Functions). dev.xadc(TEMPERATURE) uses the same
# function. The 12-bit code is in bits 15-4 of the register.
def to_celsius(raw: int) -> float:
    return (raw >> 4) * 503.975 / 4096 - 273.15


def to_raw(celsius: float) -> int:
    code = round((celsius + 273.15) * 4096 / 503.975)
    return min(max(code, 0), 0xFFF) << 4


def write_register(dev, register: XadcRegister, value: int) -> None:
    # SK-RAFT: write the register, then read it back. If the design
    # disables the JTAG access to the XADC, the value does not change.
    dev.write_xadc_register(register, value)
    read_back = dev.read_xadc_register(register)
    if read_back != value:
        raise RuntimeError(f"{register.name} is {read_back:04X}h after "
                           f"the write of {value:04X}h")


def set_thresholds(dev, lower: float, upper: float) -> None:
    # Keep the lower threshold below the upper threshold: when the
    # thresholds go up, write the upper threshold first.
    writes = [(LOWER, lower), (UPPER, upper)]
    if to_raw(upper) > dev.read_xadc_register(UPPER):
        writes.reverse()
    for register, celsius in writes:
        write_register(dev, register, to_raw(celsius))


def show_alarm(dev) -> None:
    watch_for_enter()
    while True:
        # SK-RAFT: read the temperature, the thresholds from the alarm
        # registers and the state of ALM0 from the flag register.
        temperature = dev.xadc(TEMPERATURE).value
        lower = to_celsius(dev.read_xadc_register(LOWER))
        upper = to_celsius(dev.read_xadc_register(UPPER))
        alarm = dev.read_xadc_register(XadcRegister.FLAG) & FLAG_ALM0
        print(f"\rTemp = {temperature:6.1f}C | lower = {lower:6.1f}C | "
              f"upper = {upper:6.1f}C | ALM0 = {'ON' if alarm else 'off'}"
              f"{CLEAR_TO_END_OF_LINE}", end="", flush=True)
        if stop.wait(READ_PERIOD_S):
            break


def run_stages(dev) -> None:
    # SK-RAFT: read the original values, to write them back at the end.
    original = {register: dev.read_xadc_register(register)
                for register in (XadcRegister.CONFIG1, UPPER, LOWER)}
    print("Original values: " + ", ".join(
        f"{register.name} = {value:04X}h"
        for register, value in original.items()))
    start = dev.xadc(TEMPERATURE).value
    print(f"Temperature at the start: {start:.1f}C. "
          "The thresholds move around this value.")
    print("-" * 80)
    try:
        for number, (text, lower, upper) in enumerate(STAGES, 1):
            set_thresholds(dev, start + lower, start + upper)
            if number == 1:
                # Enable the alarms only after the first thresholds are in
                # place. They put ALM0 off, whatever its state was before.
                write_register(dev, XadcRegister.CONFIG1, ALARM_MODE)
            print(f"\nStage {number} of {len(STAGES)}: {text}")
            print("Press Enter for the next stage.")
            show_alarm(dev)
    finally:
        # SK-RAFT: write back the original values. CONFIG1 first, thus the
        # alarms stop before the thresholds change.
        for register, value in original.items():
            dev.write_xadc_register(register, value)
        print("\nWrote back the original values of CONFIG1, ALARM0 and "
              "ALARM4.")


def main() -> None:
    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                print(f"Device: serial number {dev.serial_number}, "
                      f"part number {dev.part_number}")
                if not dev.part_number.startswith("XC7"):
                    print("This example is for 7 series FPGAs and "
                          "Zynq-7000 SoCs only.")
                    return
                if dev.read_xadc_register(XadcRegister.FLAG) & FLAG_JTGR:
                    print("The design allows only reads of the XADC "
                          "through JTAG (JTAG_XADC = StatusOnly).")
                    return
                run_stages(dev)
    except (SkraftError, RuntimeError) as e:
        print(f"Example failed: {e}")
        return
    except KeyboardInterrupt:
        print("Interrupted.")
        return

    print("Example done.")


if __name__ == "__main__":
    main()
