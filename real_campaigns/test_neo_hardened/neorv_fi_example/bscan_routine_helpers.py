# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""BSCAN routines of the NEORV32 hardening example, for run_injection.py.

BSCAN user register map:
U1 : reset control (write) / CRC output (read)
U2 : step count input (write) / step counter (read)
U3 : root clock enable (write) / synchronized root clock enable (read)
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from skraft import (
    BscanPrimitive,
    FpgaDevice,
    FpgaRandomInjectionReport,
    TargetMemory,
)

# U2 reads 0 when the countdown has reached zero.
COUNT_ZERO = bytes(4)


def _build_area(ebits: bool, bram: bool, ff: bool, lut: bool) -> TargetMemory:
    """Map the target flags to a TargetMemory. Each campaign uses one flag, so
    each campaign injects into one memory type only."""
    area = TargetMemory(0)
    # ebits: essential configuration bits (EBD).
    if ebits: area |= TargetMemory.ESSENTIAL_CRAM
    if bram:  area |= TargetMemory.BRAM
    if ff:    area |= TargetMemory.FF
    if lut:   area |= TargetMemory.LUTRAM
    return area


# Root clock enable (U3)
#
# The root clock enable gates the safe clock to all logic of the design
# (harness and DUT). It is 0 after programming: write 1 before a run.

def enable_root_clock(dev: FpgaDevice) -> None:
    """Turn on the root clock (U3 = 1)."""
    dev.write_bscan(BscanPrimitive(3, 1), 0x1)

def disable_root_clock(dev: FpgaDevice) -> None:
    """Turn off the root clock (U3 = 0). Thus no logic in the design
    changes state."""
    dev.write_bscan(BscanPrimitive(3, 1), 0x0)

def read_root_clock(dev: FpgaDevice) -> bool:
    """Read the synchronized root clock enable from U3."""
    return dev.read_bscan(BscanPrimitive(3, 1)) != bytes([0])


def _inject_gated(dev: FpgaDevice, target: TargetMemory,
                  exclude_pblock: Iterable[str] | None = None,
                  ) -> FpgaRandomInjectionReport:
    """Turn off the root clock, inject a random fault, then turn on the root
    clock again. The fault is not injected into the pblocks in
    exclude_pblock. Returns the injection report."""
    # Turn off the root clock (U3 = 0). Thus no logic in the design changes
    # state during the injection.
    disable_root_clock(dev)
    if read_root_clock(dev):
        print("[ROOT CLOCK] still on after the disable write")
    try:
        return dev.inject_random(target, exclude_pblock=exclude_pblock)
    finally:
        # Turn on the root clock again (U3 = 1), also if the injection causes
        # an error.
        enable_root_clock(dev)


# Reset control (U1)
#
# The DUT reset is active low: 0 holds the NEORV32 in reset, 1 lets it run.

def assert_reset(dev: FpgaDevice) -> None:
    """Hold the DUT in reset (U1 = 0)."""
    dev.write_bscan(BscanPrimitive(1, 1), 0x0)

def release_reset(dev: FpgaDevice) -> None:
    """Release the DUT reset (U1 = 1)."""
    dev.write_bscan(BscanPrimitive(1, 1), 0x1)


# Read-back (U1 / U2)

def read_cnt_reg(dev: FpgaDevice) -> bytes:
    """Read the current value of the step counter from U2."""
    return dev.read_bscan(BscanPrimitive(2, 32))

def read_crc(dev: FpgaDevice) -> bytes:
    """Read the hardware CRC from U1."""
    return dev.read_bscan(BscanPrimitive(1, 32))


# Step / countdown commands (U2)
#
# Each write to U2 is one command. The harness gives the clock-cycle
# controller a one-cycle valid pulse for each write, so a write of 0 between
# two commands is not necessary. A read (read_bscan) does not go through
# Update-DR, so it never gives a command. Use reads to poll the status.

def load_steps(dev: FpgaDevice, steps: int) -> None:
    """Write the step count to U2. The controller loads it when it is idle."""
    dev.write_bscan(BscanPrimitive(2, 32), steps)

def start_run(dev: FpgaDevice) -> None:
    """Send the start command (0x1) on U2 to start the countdown."""
    dev.write_bscan(BscanPrimitive(2, 32), 0x1)

def reset_count_register(dev: FpgaDevice) -> None:
    """Send the cancel command (0x2) on U2. The controller goes to idle."""
    dev.write_bscan(BscanPrimitive(2, 32), 0x2)


# Composite helpers
#
# The helpers do not catch errors or Ctrl+C. The with statements in
# run_injection.py release the device and close the connection.

def send_steps(dev: FpgaDevice, steps: int) -> int:
    """Load the step count into U2, read it back from U2, then start the
    countdown. Tries 5 times at most. Returns 0 on success, 1 on failure."""
    for attempt in range(5):
        # Write the step count.
        load_steps(dev, steps)
        # Read the count back. The controller shows the count while it
        # waits for the start command.
        if int.from_bytes(read_cnt_reg(dev), "big") == steps:
            # The read-back count is correct. Start the countdown.
            start_run(dev)
            return 0
        print(f"Counter mismatch on attempt {attempt + 1}/5, retrying.")
        # The count is wrong. Cancel, so that the controller is idle for the
        # next attempt.
        reset_count_register(dev)
    print("Counter mismatch after 5 attempts.")
    return 1


def start_clean_run(dev: FpgaDevice, steps: int) -> int:
    """Reset the DUT, load the step count, and wait until the countdown
    reaches zero. Returns 0 on success, 1 on failure."""
    # Give a reset pulse on U1. Thus the DUT starts the benchmark from the
    # beginning.
    assert_reset(dev)
    release_reset(dev)
    # Load the step count and start the countdown.
    if send_steps(dev, steps):
        return 1
    while True:
        # Poll for the end of the count.
        if read_cnt_reg(dev) == COUNT_ZERO:
            return 0


def start_run_n_inject(
    dev: FpgaDevice,
    steps: int,
    ebits: bool, bram: bool, ff: bool, lut: bool,
    exclude_pblock: Iterable[str] | None = None,
) -> tuple[int, FpgaRandomInjectionReport, bytes]:
    """Reset the DUT, load the step count, wait until the countdown reaches
    zero, then inject a random fault. The fault is not injected into the
    pblocks in exclude_pblock. The root clock (U3) is off during the
    injection and on again before this returns.
    Returns (flag, inject_report, counter):
        flag 0 = injection at the end of the countdown
        flag 1 = timeout or step-send failure (discard this run)"""
    # Give a reset pulse on U1. Thus the DUT starts the benchmark from the
    # beginning.
    assert_reset(dev)
    release_reset(dev)
    # The memory type to inject into.
    target  = _build_area(ebits, bram, ff, lut)
    # The counter value before the run. The function returns it if the step
    # send fails.
    counter = read_cnt_reg(dev)

    # Load the step count and start the countdown. On failure, discard the
    # run (flag 1).
    if send_steps(dev, steps):
        return 1, _inject_gated(dev, target, exclude_pblock), counter

    start_time = time.time()
    while True:
        # Poll for the end of the count.
        counter = read_cnt_reg(dev)
        if counter == COUNT_ZERO:
            # The count is at zero. Thus the DUT clock is stopped. Inject the
            # fault with the root clock off.
            return 0, _inject_gated(dev, target, exclude_pblock), counter
        # Timeout after 1 s. Inject, but the caller discards the run (flag 1).
        if time.time() - start_time > 1:
            last = int.from_bytes(counter, "big")
            print(f"Timeout: the count did not reach 0 within 1 s "
                  f"(step count {steps}, last counter 0x{last:08x})")
            return 1, _inject_gated(dev, target, exclude_pblock), counter


def run_to_end(dev: FpgaDevice) -> bytes:
    """Poll the step counter until it reaches zero, for 5 s at most.
    Returns the last counter value read."""
    start_time = time.time()
    counter    = read_cnt_reg(dev)
    while counter != COUNT_ZERO:
        # Poll for the end of the count.
        counter = read_cnt_reg(dev)
        # Timeout after 5 s. Return the last value. The caller checks it.
        if time.time() - start_time >= 5:
            print(f"Benchmark timeout. Last counter: 0x{counter.hex()}")
            return counter
    return counter
