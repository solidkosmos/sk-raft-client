# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""XADC monitor: read the die temperature and supply voltages through JTAG.

The script programs the FPGA with xadc_top.bit. Then, until you press Enter,
it does these steps one time for each sample period:

1. Write BSCAN USER1. The design copies all XADC results into a snapshot.
2. Read BSCAN USER2. This register holds the 160-bit snapshot.

The script also shows the on-chip power that Vivado calculated for the
design (report_power). The XADC measures only temperature and voltage. It
does not measure current. Thus the power value is an estimate.

References:
    UG480: 7 Series FPGAs and Zynq-7000 SoC XADC User Guide.
    UG907: Vivado Design Suite User Guide, Power Analysis and Optimization.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import statistics
import threading
import time
from collections.abc import Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO

from skraft import Bscan, Design, FpgaDevice, SkraftError, SkraftFpga

# Configuration. Set these values for your setup, or use the options.
SK_RAFT_SERVER_IP: str = "127.0.0.1"
SK_RAFT_SERVER_PORT: int = 50051
DEVICE: str = "210248781184"  # Serial number of the JTAG cable
SAMPLE_PERIOD_S: float = 1.0

HERE: Path = Path(__file__).resolve().parent
BITSTREAM: Path = HERE / "design_files" / "xadc_top.bit"
POWER_REPORT: Path = HERE / "design_files" / "xadc_top_power.rpt"
LOG_DIR: Path = HERE / "logs"

# BSCAN registers of xadc_top.vhd: (USER number, width in bits)
USER_REQUEST: tuple[int, int] = (1, 1)
USER_SNAPSHOT: tuple[int, int] = (2, 160)

# Snapshot layout. Bit 0 shifts out first. Refer to xadc_top.vhd.
# Each XADC result is a 16-bit status register value.
TEMPERATURE_LSB: int = 0
SUPPLIES: tuple[tuple[str, int, bool], ...] = (  # (name, LSB, Zynq-7000 only)
    ("VCCINT", 16, False),  # status register 01h
    ("VCCAUX", 32, False),  # 02h
    ("VCCBRAM", 48, False),  # 06h
    ("VCCPINT", 64, True),  # 0Dh
    ("VCCPAUX", 80, True),  # 0Eh
    ("VCCO_DDR", 96, True),  # 0Fh
)
SEQUENCE_COUNT_LSB: int = 112
ALARMS_LSB: int = 128
SNAPSHOT_COUNT_LSB: int = 136
DESIGN_ID_LSB: int = 144
FLAGS_LSB: int = 152
DESIGN_ID: int = 0x5A
FLAG_OT: int = 0x01
FLAG_ZYNQ: int = 0x02

# XADC transfer functions (UG480). The 12-bit ADC code is in bits 15:4.
#   Temperature (C) = code * 503.975 / 4096 - 273.15
#   Supply (V)      = code * 3 / 4096
ADC_SHIFT: int = 4
ADC_CODES: int = 4096
TEMP_GAIN_K: float = 503.975
KELVIN_OFFSET: float = 273.15
SUPPLY_FULL_SCALE_V: float = 3.0

# Time for the first averaged XADC results after configuration.
XADC_STARTUP_S: float = 0.1

# Vivado report_power text report (UG907)
REPORT_KEYS: tuple[str, ...] = (
    "Total On-Chip Power (W)",
    "Dynamic (W)",
    "Device Static (W)",
    "Junction Temperature (C)",
)
SUPPLY_SECTION: str = "Power Supply Summary"
NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
SECTION_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Za-z]")

log = logging.getLogger("xadc_monitor")


class XadcMonitorError(Exception):
    """An error of this script: the snapshot or the power report is not valid."""


@dataclass(frozen=True)
class XadcSnapshot:
    """One set of XADC results.

    Attributes:
        temperature_c: Die temperature in degrees Celsius.
        supplies_v: (name, volts) for each supply. The PS supplies are
            included only on Zynq-7000.
        alarms: XADC ALM[7:0]. ALM[7] is the OR of ALM[6:0].
        over_temperature: XADC OT output.
        sequence_count: End-of-sequence count (16 bits, wraps).
        snapshot_count: Number of snapshot requests (8 bits, wraps).
    """

    temperature_c: float
    supplies_v: tuple[tuple[str, float], ...]
    alarms: int
    over_temperature: bool
    sequence_count: int
    snapshot_count: int


@dataclass(frozen=True)
class PowerEstimate:
    """Summary of a Vivado report_power text report.

    Attributes:
        total_w: Total on-chip power, in watts.
        dynamic_w: Dynamic power, in watts.
        static_w: Device static power, in watts.
        junction_c: Junction temperature that Vivado used, in degrees Celsius.
        rails: (name, nominal volts, amperes) for each rail with a current.
    """

    total_w: float
    dynamic_w: float
    static_w: float
    junction_c: float
    rails: tuple[tuple[str, float, float], ...]


def _bits(value: int, lsb: int, width: int = 16) -> int:
    """Return ``width`` bits of ``value``, from bit ``lsb``."""
    return (value >> lsb) & ((1 << width) - 1)


def to_celsius(register: int) -> float:
    """Convert the temperature status register (00h) to degrees Celsius."""
    return (register >> ADC_SHIFT) * TEMP_GAIN_K / ADC_CODES - KELVIN_OFFSET


def to_volts(register: int) -> float:
    """Convert a supply status register to volts."""
    return (register >> ADC_SHIFT) * SUPPLY_FULL_SCALE_V / ADC_CODES


def decode_snapshot(value: int) -> XadcSnapshot:
    """Decode the 160-bit USER2 snapshot.

    Args:
        value: The snapshot. Bit 0 is the first bit that shifts out, as
            ``Bscan.read`` returns it.

    Raises:
        XadcMonitorError: The design ID is not correct. The FPGA does not
            hold xadc_top, or the JTAG read failed.
    """
    design_id = _bits(value, DESIGN_ID_LSB, 8)
    if design_id != DESIGN_ID:
        raise XadcMonitorError(
            f"design ID is {design_id:#04x}, expected {DESIGN_ID:#04x}. "
            "Make sure that the FPGA holds xadc_top.bit."
        )
    flags = _bits(value, FLAGS_LSB, 8)
    zynq = bool(flags & FLAG_ZYNQ)
    return XadcSnapshot(
        temperature_c=to_celsius(_bits(value, TEMPERATURE_LSB)),
        supplies_v=tuple(
            (name, to_volts(_bits(value, lsb)))
            for name, lsb, zynq_only in SUPPLIES
            if zynq or not zynq_only
        ),
        alarms=_bits(value, ALARMS_LSB, 8),
        over_temperature=bool(flags & FLAG_OT),
        sequence_count=_bits(value, SEQUENCE_COUNT_LSB),
        snapshot_count=_bits(value, SNAPSHOT_COUNT_LSB, 8),
    )


class XadcMonitor:
    """Read XADC snapshots from xadc_top through BSCAN."""

    def __init__(self, dev: FpgaDevice) -> None:
        """Create the monitor for a device that holds xadc_top.bit."""
        self._request = Bscan(dev, *USER_REQUEST)
        self._snapshot = Bscan(dev, *USER_SNAPSHOT)
        self._last_count: int | None = None

    def read(self) -> XadcSnapshot:
        """Request a new snapshot and read it.

        Raises:
            XadcMonitorError: The snapshot is not valid, or the design did
                not take a new snapshot.
            skraft.SkraftError: A BSCAN access failed.
        """
        self._request.write(1)
        value = self._snapshot.read()
        snapshot = decode_snapshot(value)
        log.debug(
            "USER2 %040x: snapshot %d, XADC sequence %d",
            value,
            snapshot.snapshot_count,
            snapshot.sequence_count,
        )
        if snapshot.snapshot_count == self._last_count:
            raise XadcMonitorError("the design did not take a new snapshot")
        self._last_count = snapshot.snapshot_count
        return snapshot


def parse_power_report(text: str) -> PowerEstimate:
    """Parse the text output of the Vivado report_power command.

    Raises:
        XadcMonitorError: A summary value is not in the report.
    """
    lines = text.splitlines()
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        is_row = len(stripped) > 1 and stripped[0] == stripped[-1] == "|"
        rows.append([c.strip() for c in stripped[1:-1].split("|")] if is_row else [])

    summary: dict[str, float] = {}
    for cells in rows:
        match = NUMBER.search(cells[1]) if len(cells) >= 2 else None
        if match and cells[0] in REPORT_KEYS and cells[0] not in summary:
            summary[cells[0]] = float(match.group())
    missing = [key for key in REPORT_KEYS if key not in summary]
    if missing:
        raise XadcMonitorError(f"not in the power report: {', '.join(missing)}")

    # The table of contents also names the supply section. The section
    # itself is the last occurrence. Columns: Source, Voltage (V), Total (A).
    starts = [i for i, line in enumerate(lines) if SUPPLY_SECTION in line]
    rails: list[tuple[str, float, float]] = []
    for i in range(starts[-1] + 1 if starts else len(lines), len(lines)):
        if SECTION_HEADING.match(lines[i]):
            break
        cells = rows[i]
        numbers = [NUMBER.fullmatch(c) for c in cells[1:3]]
        if len(numbers) == 2 and all(numbers) and float(cells[2]) > 0:
            rails.append((cells[0], float(cells[1]), float(cells[2])))

    total_w, dynamic_w, static_w, junction_c = (summary[k] for k in REPORT_KEYS)
    return PowerEstimate(total_w, dynamic_w, static_w, junction_c, tuple(rails))


def load_power_report(path: Path) -> PowerEstimate | None:
    """Read the power report of build.tcl. Return None if it is not usable."""
    try:
        return parse_power_report(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, XadcMonitorError) as error:
        log.warning("No Vivado power estimate (%s). Run hw/build.tcl.", error)
        return None


def print_power_estimate(estimate: PowerEstimate) -> None:
    """Print the Vivado power estimate and the power of each rail."""
    print("Vivado power estimate (report_power, not a measurement):")
    print(
        f"  On-chip power {estimate.total_w:.3f} W "
        f"(dynamic {estimate.dynamic_w:.3f} W, static {estimate.static_w:.3f} W) "
        f"at a junction temperature of {estimate.junction_c:.1f} C"
    )
    for name, volts, amps in estimate.rails:
        print(f"  {name:<10} {volts:6.3f} V {amps:7.3f} A {volts * amps:7.3f} W")


def _wait_for_enter(stop: threading.Event) -> None:
    """Set ``stop`` when the user presses Enter."""
    try:
        input()
    except EOFError:
        return  # No console input: use --duration or Ctrl+C.
    stop.set()


def run_monitor(
    monitor: XadcMonitor, period_s: float, duration_s: float, log_file: Path | None
) -> list[float]:
    """Read and print the XADC results until Enter, Ctrl+C or ``duration_s``.

    Args:
        monitor: The monitor of the programmed device.
        period_s: Time between two samples, in seconds.
        duration_s: Run time in seconds. 0 means no limit.
        log_file: New CSV file for the results, or None. The function does
            not overwrite a file.

    Returns:
        The measured die temperatures, in degrees Celsius.
    """
    stop = threading.Event()
    threading.Thread(target=_wait_for_enter, args=(stop,), daemon=True).start()
    end = time.monotonic() + duration_s if duration_s > 0 else float("inf")
    temperatures: list[float] = []
    print("Press Enter to stop.")
    last_sequence = None
    stalled = False
    with ExitStack() as stack:
        handle: TextIO | None = None
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context(
                log_file.open("x", newline="", encoding="utf-8")
            )
            log.info("Log file: %s", log_file)
        writer = csv.writer(handle) if handle else None
        try:
            while not stop.is_set() and time.monotonic() < end:
                started = time.monotonic()
                stamp = datetime.now().isoformat(sep=" ", timespec="seconds")
                snap = monitor.read()
                names = [name for name, _ in snap.supplies_v]
                volts = [v for _, v in snap.supplies_v]
                if not temperatures:
                    columns = "".join(f"{n + ' V':>11}" for n in names)
                    print(f"{'Time':<20}{'Temp C':>8}{columns}{'OT':>4}{'ALM':>6}")
                    if writer:
                        writer.writerow(
                            ["time", "temperature_c"]
                            + [f"{n.lower()}_v" for n in names]
                            + ["ot", "alarms"]
                        )
                ot = int(snap.over_temperature)
                print(
                    f"{stamp:<20}{snap.temperature_c:>8.1f}"
                    + "".join(f"{v:>11.3f}" for v in volts)
                    + f"{ot:>4}  {snap.alarms:#04x}",
                    flush=True,
                )
                if writer and handle:
                    writer.writerow(
                        [stamp, f"{snap.temperature_c:.2f}"]
                        + [f"{v:.4f}" for v in volts]
                        + [ot, f"{snap.alarms:#04x}"]
                    )
                    handle.flush()
                if snap.sequence_count == last_sequence and not stalled:
                    stalled = True
                    log.warning("The XADC sequence count did not change.")
                last_sequence = snap.sequence_count
                temperatures.append(snap.temperature_c)
                stop.wait(max(0.0, period_s - (time.monotonic() - started)))
        except KeyboardInterrupt:
            print()
    return temperatures


def print_summary(temperatures: list[float], estimate: PowerEstimate | None) -> None:
    """Print the temperature statistics and the UG907 junction temperature tip."""
    if not temperatures:
        return
    mean_c = statistics.fmean(temperatures)
    print(
        f"Die temperature, {len(temperatures)} samples: "
        f"min {min(temperatures):.1f} C, mean {mean_c:.1f} C, "
        f"max {max(temperatures):.1f} C"
    )
    if estimate is None:
        return
    print(
        f"Vivado used a junction temperature of {estimate.junction_c:.1f} C. "
        "Static power increases with temperature (UG907)."
    )
    print("For an estimate at the measured temperature, open the implemented")
    print("design in Vivado and enter these commands:")
    print(f"  set_operating_conditions -junction_temp {mean_c:.1f}")
    print("  report_power")


@dataclass(frozen=True)
class Config:
    """Settings from the command line."""

    ip: str
    port: int
    device: str
    period_s: float
    duration_s: float
    log_file: Path | None
    verbose: bool


def parse_args(argv: Sequence[str] | None) -> Config:
    """Parse the command line. The defaults are the constants above."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ip",
        type=str,
        default=SK_RAFT_SERVER_IP,
        help="IP address of the SK-RAFT server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SK_RAFT_SERVER_PORT,
        help="Port of the SK-RAFT server.",
    )
    parser.add_argument(
        "--device", type=str, default=DEVICE, help="Serial number of the JTAG cable."
    )
    parser.add_argument(
        "--period",
        type=float,
        default=SAMPLE_PERIOD_S,
        help="Time between two samples, in seconds.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Run time in seconds. 0: run until you press Enter.",
    )
    parser.add_argument(
        "--no-log", action="store_true", help="Do not write the CSV log."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show the raw USER2 value of each sample.",
    )
    ns = parser.parse_args(argv)
    if ns.period <= 0 or ns.duration < 0:
        parser.error("--period must be > 0 and --duration must be >= 0")
    log_name = f"xadc_log_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return Config(
        ip=str(ns.ip),
        port=int(ns.port),
        device=str(ns.device),
        period_s=float(ns.period),
        duration_s=float(ns.duration),
        log_file=None if ns.no_log else LOG_DIR / log_name,
        verbose=bool(ns.verbose),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Program the FPGA, show the power estimate and monitor the XADC.

    Side effects: programs the FPGA through the SK-RAFT server. Writes a new
    CSV file in logs/ (not with --no-log).

    Returns:
        0 on success, 1 on error, 130 on Ctrl+C before the monitor starts.
    """
    config = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    log.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    if not BITSTREAM.is_file():
        log.error("No bitstream at %s. Run hw/build.tcl first.", BITSTREAM)
        return 1
    estimate = load_power_report(POWER_REPORT)

    try:
        with SkraftFpga.connect(
            ip=config.ip, port=config.port
        ) as client, client.attach(config.device) as dev:
            dev.uploadDesignToServer(Design(bit=str(BITSTREAM)))
            dev.programFPGA()
            log.info("Programmed %s.", config.device)
            time.sleep(XADC_STARTUP_S)
            if estimate is not None:
                print_power_estimate(estimate)
            temperatures = run_monitor(
                XadcMonitor(dev), config.period_s, config.duration_s, config.log_file
            )
    except (OSError, SkraftError, XadcMonitorError) as error:
        log.error("XADC monitor failed: %s", error)
        return 1
    except KeyboardInterrupt:
        log.error("Interrupted.")
        return 130

    print_summary(temperatures, estimate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
