import time
import serial

from skraft import FpgaDevice, BscanPrimitive, InjectionArea

# BSCAN user register map:
# U1 : reset control (write) / CRC output (read)
# U2 : step count input (write) / step counter (read)


def _build_area(cram: bool, bram: bool, ff: bool, lut: bool) -> InjectionArea:
    """Map the four target flags to a combined InjectionArea."""
    area = InjectionArea.CRAM
    if cram: area |= InjectionArea.ESSENTIAL_CRAM
    if bram: area |= InjectionArea.BRAM
    if ff:   area |= InjectionArea.FLIP_FLOP
    if lut:  area |= InjectionArea.LUTRAM
    return area


# Reset control (U1)

def enable_reset(dev: FpgaDevice) -> None:
    dev.write_bscan(BscanPrimitive(1, 1), 0x1)

def disable_reset(dev: FpgaDevice) -> None:
    dev.write_bscan(BscanPrimitive(1, 1), 0x0)


# Read-back (U1 / U2)

def read_cnt_reg(dev: FpgaDevice) -> bytes:
    """Read the current step-counter value from U2."""
    return dev.read_bscan(BscanPrimitive(2, 32))

def read_crc(dev: FpgaDevice) -> bytes:
    """Read the hardware CRC from U1."""
    return dev.read_bscan(BscanPrimitive(1, 32))


# Step / countdown helpers (U2)

def run_x_cycles(dev: FpgaDevice, steps: int) -> bytes:
    """Write step count to U2, then clear. Returns the shifted-out echo."""
    reg = BscanPrimitive(2, 32)
    dev.write_bscan(reg, steps)
    return dev.write_bscan(reg, 0x0)

def start_run(dev: FpgaDevice) -> None:
    """Pulse the start bit on U2 to begin the countdown."""
    reg = BscanPrimitive(2, 32)
    dev.write_bscan(reg, 0x1)
    dev.write_bscan(reg, 0x0)

def reset_count_register(dev: FpgaDevice) -> None:
    """Pulse the reset bit on U2 to clear the countdown register."""
    reg = BscanPrimitive(2, 32)
    dev.write_bscan(reg, 0x2)
    dev.write_bscan(reg, 0x0)


# Composite helpers

def send_steps(dev: FpgaDevice, steps: int) -> int:
    """Load step count into U2, verify with read-back, then pulse start.
    Retries up to 5 times. Returns 0 on success, 1 on failure."""
    for attempt in range(5):
        echo = run_x_cycles(dev, steps)
        if echo == read_cnt_reg(dev):
            start_run(dev)
            return 0
        print(f"Counter mismatch on attempt {attempt + 1}/5, retrying.")
        reset_count_register(dev)
    print("Counter mismatch after 5 attempts.")
    return 1


def start_clean_run(dev: FpgaDevice, steps: int) -> int:
    """Reset the DUT, load the step count, and wait for countdown to reach zero.
    Returns 0 on success, 1 on failure."""
    disable_reset(dev)
    enable_reset(dev)
    if send_steps(dev, steps):
        return 1
    while True:
        try:
            if read_cnt_reg(dev) == bytes([0, 0, 0, 0]):
                return 0
        except KeyboardInterrupt:
            print("Interrupted.")
            dev.release()
            return 1


def start_run_n_inject(
    dev: FpgaDevice,
    steps: int,
    cram: bool, bram: bool, ff: bool, lut: bool,
) -> tuple:
    """Reset the DUT, load the step count, wait for countdown to zero, then inject a random fault.
    Returns (flag, inject_report, counter):
        flag 0 = injection at natural end of countdown
        flag 1 = timeout or step-send failure (discard this run)"""
    disable_reset(dev)
    enable_reset(dev)
    target  = _build_area(cram, bram, ff, lut)
    counter = read_cnt_reg(dev)

    if send_steps(dev, steps):
        return 1, dev.inject_random(target), counter

    start_time = time.time()
    while True:
        try:
            counter = read_cnt_reg(dev)
            if counter == bytes([0, 0, 0, 0]):
                return 0, dev.inject_random(target), counter
            if time.time() - start_time > 1:
                return 1, dev.inject_random(target), counter
        except KeyboardInterrupt:
            print("Interrupted.")
            dev.release()
            return 1, None, counter


def run_to_end_and_read(dev: FpgaDevice, ser: serial.Serial) -> bytes:
    """Poll the countdown register until it reaches zero, or until 5 s timeout.
    Returns the last counter value read."""
    start_time = time.time()
    counter    = read_cnt_reg(dev)
    while counter != bytes([0, 0, 0, 0]):
        try:
            counter = read_cnt_reg(dev)
            if time.time() - start_time >= 5:
                print(f"Benchmark timeout. Last counter: {counter}")
                return counter
        except (KeyboardInterrupt, Exception) as e:
            print(f"Caught {e}, stopping.")
            dev.release()
            break
    return counter
