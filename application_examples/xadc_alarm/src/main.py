# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Example: set off and clear the temperature alarm of the XADC.

The script moves the thresholds of the temperature alarm (ALM0) of the
XADC around the temperature of the FPGA, and shows the state of the alarm.
The temperature does not change, only the thresholds move. The server
converts the thresholds into the values of the alarm registers, and reads
the state of the alarms from the flag register, through the JTAG
interface. The script does not program the FPGA.

ALM0 has hysteresis. It goes on when the temperature is above the upper
threshold (TEMPERATURE_UPPER). Then it stays on until the temperature is
below the lower threshold (TEMPERATURE_LOWER).

In the default mode of the sequencer, the XADC disables all the alarms,
except the over-temperature alarm (OT). Thus the script sets the XADC to
the single channel mode, on the temperature sensor (CONFIG0, 40h, and
CONFIG1, 41h). In this mode, the XADC converts only the temperature, and
the alarms operate. The other sensors keep their last values until the
end. At the end, the script writes back the original values of CONFIG0,
CONFIG1 and of the two thresholds.

The script is for 7 series FPGAs and Zynq-7000 SoCs (XADC, UG480), and for
UltraScale and UltraScale+ devices (SYSMON, UG580). The same register
values operate on all of them.
"""

import os
import threading

from skraft import (
    TEMPERATURE,
    TEMPERATURE_LOWER,
    TEMPERATURE_UPPER,
    SkraftError,
    SkraftFpga,
    XadcRegister,
)

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BA2524A"

# The distance between the thresholds and the temperature at the start,
# in degrees Celsius. During the example, the temperature of the die
# changes by less than this distance.
MARGIN_C = 5.0

# The time between two reads, in seconds.
READ_PERIOD_S = 0.5

# The values of CONFIG0 (40h) and CONFIG1 (41h) during the example. The
# XADC (UG480) and the SYSMON (UG580) use the same bits.
# CONFIG0:
#   bits 13-12  AVG1-AVG0 = 01: average of 16 samples, as in default mode.
#   bits 5-0    CH5-CH0 = 000000: the on-chip temperature sensor.
TEMPERATURE_CHANNEL = 0x1000
# CONFIG1:
#   bits 15-12  SEQ3-SEQ0 = 0011: single channel mode (sequencer off).
#   bits 11-8   ALM6-ALM3 = 1111: VCCBRAM and PS supply alarms disabled.
#   bits 7-4    CAL3-CAL0 = 1101: correction of the ADC offset and of the
#               supply sensors. CAL1 is 0: the UltraScale SYSMON does not
#               support it.
#   bits 3-2    ALM2-ALM1 = 11: VCCAUX and VCCINT alarms disabled.
#   bit 1       ALM0 = 0: temperature alarm enabled.
#   bit 0       OT = 0: over-temperature alarm enabled, as in default mode.
ALARM_MODE = 0x3FDC

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


def set_thresholds(dev, lower: float, upper: float) -> None:
    # SK-RAFT: set the two thresholds, in degrees Celsius. The server
    # converts them, and reads each register back to verify the write.
    # Keep the lower threshold below the upper threshold: when the
    # thresholds go up, set the upper threshold first.
    if upper > dev.xadc_alarm(TEMPERATURE_UPPER).value:
        dev.set_xadc_alarm(TEMPERATURE_UPPER, upper)
        dev.set_xadc_alarm(TEMPERATURE_LOWER, lower)
    else:
        dev.set_xadc_alarm(TEMPERATURE_LOWER, lower)
        dev.set_xadc_alarm(TEMPERATURE_UPPER, upper)


def show_alarm(dev) -> None:
    watch_for_enter()
    while True:
        # SK-RAFT: read the temperature, the two thresholds and the state
        # of the alarms.
        temperature = dev.xadc(TEMPERATURE).value
        lower = dev.xadc_alarm(TEMPERATURE_LOWER).value
        upper = dev.xadc_alarm(TEMPERATURE_UPPER).value
        alarm = dev.xadc_flags().temperature
        print(f"\rTemp = {temperature:6.1f}C | lower = {lower:6.1f}C | "
              f"upper = {upper:6.1f}C | ALM0 = {'ON' if alarm else 'off'}"
              f"{CLEAR_TO_END_OF_LINE}", end="", flush=True)
        if stop.wait(READ_PERIOD_S):
            break


def run_stages(dev) -> None:
    # SK-RAFT: read the original values, to write them back at the end.
    config0 = dev.read_xadc_register(XadcRegister.CONFIG0)
    config1 = dev.read_xadc_register(XadcRegister.CONFIG1)
    original_lower = dev.xadc_alarm(TEMPERATURE_LOWER).value
    original_upper = dev.xadc_alarm(TEMPERATURE_UPPER).value
    print(f"Original values: CONFIG0 = {config0:04X}h, "
          f"CONFIG1 = {config1:04X}h, lower = {original_lower:.1f}C, "
          f"upper = {original_upper:.1f}C")
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
                # Select the channel first, then the mode.
                dev.write_xadc_register(XadcRegister.CONFIG0,
                                        TEMPERATURE_CHANNEL)
                dev.write_xadc_register(XadcRegister.CONFIG1, ALARM_MODE)
            print(f"\nStage {number} of {len(STAGES)}: {text}")
            print("Press Enter for the next stage.")
            show_alarm(dev)
    finally:
        # SK-RAFT: write back the original values. CONFIG1 first, thus the
        # alarms stop before the channel and the thresholds change.
        dev.write_xadc_register(XadcRegister.CONFIG1, config1)
        dev.write_xadc_register(XadcRegister.CONFIG0, config0)
        dev.set_xadc_alarm(TEMPERATURE_UPPER, original_upper)
        dev.set_xadc_alarm(TEMPERATURE_LOWER, original_lower)
        print("\nWrote back the original values of CONFIG0, CONFIG1 and of "
              "the thresholds.")


def main() -> int:
    try:
        # SK-RAFT: open the connection. Then attach to the target device.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                print(f"Device: serial number {dev.serial_number}, "
                      f"part number {dev.part_number}")
                # SK-RAFT: the server refuses the devices that do not have
                # a supported XADC or SYSMON.
                if dev.xadc_flags().jtag_read_only:
                    print("The design allows only reads of the XADC "
                          "through JTAG (JTAG_XADC = StatusOnly).")
                    return 1
                run_stages(dev)
    except SkraftError as e:
        print(f"Example failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130

    print("Example done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
