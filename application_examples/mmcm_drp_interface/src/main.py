# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""MMCM dynamic reconfiguration over BSCAN (mmcm_drp_interface_top).

The MMCM starts with VCO = 1000 MHz (M = 10, D = 1) and CLKOUT0 and
CLKOUT1 at 1000 / 10 = 100 MHz. Each output drives a heartbeat LED that
toggles every 10,000,000 cycles (100 ms at 100 MHz):
  led_o[0] = CLKOUT0 ("clkout 1"), led_o[1] = CLKOUT1 ("clkout 2").

Stages (press Enter to go to the next one):
  0. Program the FPGA. The two heartbeats are synchronous.
  1. CLKOUT0 and CLKOUT1 divide 10 -> 50 (20 MHz): both LEDs toggle
     every 0.5 s.
  2. CLKOUT1 divide 100 (10 MHz) for 1 s, then 50 again. The CLKOUT1
     heartbeat falls 0.5 s behind (half of its 1 s blink period): from then
     on the two LEDs blink in alternation. The clock phase does not
     change; the heartbeat counters are 1 s apart.

Register addresses and bit fields: XAPP888 (v1.8), 7 series, Tables 1-3,
14 and 15. Each register change is a read-modify-write, as in the XAPP888
reference design: the bits outside the field keep their value.

BSCAN USER1 (see mmcm_drp_interface_top.vhd)
  write (32 bits): (31:25) padding, (24) MMCM RST,
                   (23) 1 = write / 0 = read, (22:16) DRP address,
                   (15:0) DRP data
  read  (24 bits): (23:17) current DRP address, (16:1) DO, (0) DRP error
The DRP control FSM does a DRP access only while bit 24 = 1. A packet with
bit 24 = 0 does no access; it releases the MMCM reset.
"""

import time
from pathlib import Path

from skraft import BscanPrimitive, Design, SkraftError, SkraftFpga

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
SERIAL_NUMBER = "210183BA2524A"  # use get_devices() if you do not know it

# The design file that create_project.tcl writes (default project
# mmcm_drp_interface/ next to create_project.tcl)
HERE = Path(__file__).resolve().parent
IMPL_DIR = (HERE.parent / "mmcm_drp_interface"
            / "mmcm_drp_interface.runs" / "impl_1")
design = Design(bit=str(IMPL_DIR / "mmcm_drp_interface_top.bit"))

# BSCAN USER1: 32 bits are written (25 used), 24 bits are read. Each
# length is a whole number of bytes.
USER1_WRITE = BscanPrimitive(1, 32)
USER1_READ = BscanPrimitive(1, 24)

# --------------------------------------------------------------------------- #
# XAPP888, Table 15: DRP addresses (7 series MMCM)
# --------------------------------------------------------------------------- #
CLKOUT_REG1 = {0: 0x08, 1: 0x0A, 2: 0x0C, 3: 0x0E, 4: 0x10, 5: 0x06, 6: 0x12}
CLKOUT_REG2 = {0: 0x09, 1: 0x0B, 2: 0x0D, 3: 0x0F, 4: 0x11, 5: 0x07, 6: 0x13}
POWER_REG = 0x28                 # 7 series (0x27 on UltraScale)

# Start-up setting of the design (mmcm_wrapper generics): VCO 1000 MHz,
# CLKOUT0 and CLKOUT1 divide 10
START_DIVIDE = 10

# Stage 1: both outputs divide 50 (1000 MHz / 50 = 20 MHz)
SLOW_DIVIDE = 50

# "clkout 2" of the request: CLKOUT1 (led_o[1])
PHASE_OUT = 1                    # stage 2

# Stage 2: CLKOUT1 at half speed for LAG_TIME_S. Its heartbeat then lags by
# LAG_TIME_S * (1 - SLOW_DIVIDE / LAG_DIVIDE) = 0.5 s.
LAG_DIVIDE = 100
LAG_TIME_S = 1.0

# --------------------------------------------------------------------------- #
# Bit fields (XAPP888, Tables 1 to 3)
# --------------------------------------------------------------------------- #
# ClkReg1: PHASE_MUX [15:13], RESERVED [12], HIGH TIME [11:6], LOW TIME [5:0]
# ClkReg2, CLKOUT1 to CLKOUT4: RESERVED [15:10], MX [9:8] (must be 00),
#   EDGE [7], NO COUNT [6], DELAY TIME [5:0]
# ClkReg2, CLKOUT0: RESERVED [15], FRAC [14:12], FRAC_EN [11],
#   FRAC_WF_R [10], MX [9:8] (must be 00), EDGE [7], NO COUNT [6],
#   DELAY TIME [5:0]


def phase_fields(phase_deg: float, divide: int) -> tuple[int, int]:
    """PHASE_MUX and DELAY TIME for a phase shift of an output with an
    integer divide. The step is 1/8 VCO period (45 / divide degrees)."""
    steps = round(phase_deg * divide / 45.0)   # in 1/8 VCO periods
    return steps % 8, steps // 8               # PHASE_MUX, DELAY TIME


def divide_fields(divide: int) -> tuple[int, int, int, int]:
    """HIGH TIME, LOW TIME, EDGE and NO COUNT for an integer divide with
    50 % duty cycle (XAPP888, Divider Group)."""
    if divide == 1:
        return 1, 1, 0, 1
    high = divide // 2
    return high, divide - high, divide % 2, 0


def phase_changes(out: int, phase_deg: float,
                  divide: int) -> list[tuple[int, int, int]]:
    """(address, keep mask, new bits) to set the phase of one output with
    the given divide. DELAY TIME has 6 bits: at most 63 VCO periods."""
    mux, delay = phase_fields(phase_deg, divide)
    if delay > 63:
        raise ValueError(f"{phase_deg} degrees at divide {divide} needs "
                         f"DELAY TIME {delay} (maximum 63)")
    return [
        # ClkReg1: change PHASE_MUX [15:13] only
        (CLKOUT_REG1[out], 0x1FFF, mux << 13),
        # ClkReg2: MX [9:8] = 00 and DELAY TIME [5:0]; keep RESERVED, EDGE,
        # NO COUNT (and the fractional bits of CLKOUT0)
        (CLKOUT_REG2[out], 0xFCC0, delay),
    ]


def divide_changes(out: int, divide: int) -> list[tuple[int, int, int]]:
    """(address, keep mask, new bits) to set the integer divide of one
    output (phase 0)."""
    high, low, edge, no_count = divide_fields(divide)
    if out == 0:
        # CLKOUT0: FRAC, FRAC_EN, FRAC_WF_R and MX = 0; keep RESERVED [15]
        # and DELAY TIME
        reg2 = (CLKOUT_REG2[0], 0x803F, (edge << 7) | (no_count << 6))
    else:
        # MX = 00; keep RESERVED [15:10] and DELAY TIME
        reg2 = (CLKOUT_REG2[out], 0xFC3F, (edge << 7) | (no_count << 6))
    return [
        # ClkReg1: HIGH TIME and LOW TIME; keep PHASE_MUX and RESERVED
        (CLKOUT_REG1[out], 0xF000, (high << 6) | low),
        reg2,
    ]


# --------------------------------------------------------------------------- #
# DRP access over BSCAN
# --------------------------------------------------------------------------- #
def packet(rst: int, write: int, addr: int, data: int) -> int:
    return (rst << 24) | (write << 23) | (addr << 16) | data


def status(dev) -> tuple[int, int, int]:
    """Read USER1: (current address, DO, error)."""
    value = int.from_bytes(dev.read_bscan(USER1_READ), "big")
    return (value >> 17) & 0x7F, (value >> 1) & 0xFFFF, value & 1


def drp_read(dev, addr: int) -> int:
    """DRP read (MMCM in reset). Returns DO."""
    dev.write_bscan(USER1_WRITE, packet(1, 0, addr, 0))
    cur, do, err = status(dev)
    if err or cur != addr:
        raise RuntimeError(f"DRP read {addr:#04x} failed: address {cur:#04x},"
                           f" error {err}")
    return do


def drp_write(dev, addr: int, data: int) -> None:
    """DRP write (MMCM in reset)."""
    dev.write_bscan(USER1_WRITE, packet(1, 1, addr, data))
    cur, _, err = status(dev)
    if err or cur != addr:
        raise RuntimeError(f"DRP write {addr:#04x} failed: address {cur:#04x},"
                           f" error {err}")


def reconfigure(dev, changes: list[tuple[int, int, int]]) -> float:
    """XAPP888 sequence: RST on, power register all 1, read-modify-write of
    each register, RST off, wait for the lock. Returns the time
    (time.perf_counter) at which RST was released."""
    drp_write(dev, POWER_REG, 0xFFFF)          # first access sets RST
    for addr, keep, bits in changes:
        old = drp_read(dev, addr)
        new = (old & keep) | bits
        drp_write(dev, addr, new)
        check = drp_read(dev, addr)
        print(f"  {addr:#04x}: {old:#06x} -> {new:#06x}"
              f" (read back {check:#06x})")
        if check != new:
            raise RuntimeError(f"register {addr:#04x} reads back {check:#06x}")
    dev.write_bscan(USER1_WRITE, packet(0, 0, 0, 0))   # RST off, no access
    released = time.perf_counter()
    time.sleep(0.1)                                    # MMCM lock time
    return released


def stage(text: str) -> None:
    print()
    print(text)


def main() -> int:
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                dev.upload_design_to_server(design)
                dev.program_fpga(design)
                stage("Stage 0: programmed. CLKOUT0 and CLKOUT1 at 100 MHz, "
                      "phase 0: the two LEDs blink together.")
                input("Press Enter for stage 1...")

                stage(f"Stage 1: CLKOUT0 and CLKOUT1 divide {START_DIVIDE} -> "
                      f"{SLOW_DIVIDE} ({1000 / SLOW_DIVIDE:g} MHz): both "
                      f"LEDs blink {SLOW_DIVIDE // START_DIVIDE}x slower.")
                reconfigure(dev, divide_changes(0, SLOW_DIVIDE)
                            + divide_changes(1, SLOW_DIVIDE))
                input("Press Enter for stage 2...")

                lag = LAG_TIME_S * (1 - SLOW_DIVIDE / LAG_DIVIDE)
                stage(f"Stage 2: CLKOUT{PHASE_OUT} divide {LAG_DIVIDE} for "
                      f"{LAG_TIME_S:g} s, then {SLOW_DIVIDE}: led_o"
                      f"[{PHASE_OUT}] falls {lag:g} s behind.")
                released = reconfigure(
                    dev, divide_changes(PHASE_OUT, LAG_DIVIDE))
                time.sleep(max(0.0, LAG_TIME_S
                               - (time.perf_counter() - released)))
                reconfigure(dev, divide_changes(PHASE_OUT, SLOW_DIVIDE))
                print("The two LEDs now blink in alternation.")
                print("Done.")
    except SkraftError as e:
        print(f"failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
