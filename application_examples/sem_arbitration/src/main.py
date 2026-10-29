# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
SEM arbitration test: how does the SEM react to the upsets that SK-RAFT
injects while the SEM is idle?

The SEM controller and SK-RAFT both use the configuration logic. In idle,
the SEM does not use the ICAP, so SK-RAFT can inject without a conflict.
Each experiment does these steps:

  1. Program the design, start the clock (USER1 = 1) and set the ICAP
     grant to 1 (USER2 = 1). The SEM initializes and goes to observation.
  2. Put the SEM in idle (I command).
  3. Stop the clock (USER1 = 0), inject the upsets of the experiment, and
     start the clock again (USER1 = 1).
  4. Send O (observation). The SEM scans the configuration memory again,
     without a new initialization.
  5. Show the injected bits, which of them the SEM reported, and the SEM
     status.

Note: R 00 (reset) has no effect while the SEM is in observation. A reset
from idle works, but the SEM then initializes with the upsets present and
does not report them.

The experiments (set EXPERIMENTS to run only some of them):
  Anywhere in the CRAM of the device, outside pblock_sem:
    1  One single bit upset (SBU).
    2  Two adjacent bits in one word of a frame.
    3  Three bits in one frame, in different words.
  Targeted at the SEM (essential bits of pblock_sem):
    4  One SBU.
    5  NUM_SEM_UPSETS SBUs, one at a time: steps 2 to 5 for each SBU, so
       the SEM can correct each one before the next.

The script works with the two boards of this example. Set BOARD below.
  basys3  Digilent Basys 3, Artix-7 (basys3/)
  te0841  Trenz TE0841-02, Kintex UltraScale XCKU040 (te0841/)
Build the design of the board with its create_project.tcl (see README.md).

BSCAN registers of both designs:
  USER1  write: clock enable (1 = the clock operates, 0 after programming)
  USER2  write: the ICAP grant of the SEM (0 after programming)
  USER3  read : the SEM status signals (see Board.status_names)

The SEM sends its reports and gets its commands on the UART of the board
(9600 8-N-1). sem_monitor.py holds the UART reader and the parsing of the
SEM reports.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import serial

from skraft import (
    BscanPrimitive,
    Design,
    FpgaDevice,
    SkraftError,
    SkraftFpga,
    TargetMemory,
)

from sem_monitor import (
    SemUart,
    Upset,
    print_reports,
    repeated_report,
    status_text,
)


@dataclass(frozen=True)
class Board:
    """The settings that are different for each board."""

    # The folder of the board design, relative to this script
    folder: str
    # The top of the design: the name of the .bit and .ebd files
    top: str
    # The XDC file in <folder>/hw/xdc/
    xdc: str
    # The serial number of the device (see get_devices())
    serial_number: str
    # The COM port of the USB-UART of the board (see Device Manager)
    uart_port: str
    # The width of USER2 in bits
    grant_bits: int
    # The names of the SEM status bits in USER3, bit 0 first
    status_names: tuple[str, ...]
    # The number of 32-bit words in a frame
    frame_words: int
    # The words of a frame that hold the frame ECC
    ecc_words: tuple[int, ...]


BOARDS = {
    "basys3": Board(
        folder="basys3",
        top="sem_arbitration_7series",
        xdc="basys3.xdc",
        serial_number="210183BFD452A",
        uart_port="COM5",
        # USER2 bit 0 = icap_grant
        grant_bits=1,
        # PG036
        status_names=(
            "heartbeat", "initialization", "observation", "correction",
            "classification", "injection", "essential", "uncorrectable",
        ),
        frame_words=101,
        ecc_words=(50,),
    ),
    "te0841": Board(
        folder="te0841",
        top="sem_arbitration_us",
        xdc="te0841_ku040.xdc",
        serial_number="251633000000A",
        uart_port="COM7",
        # USER2 bit 0 = cap_gnt, bit 1 = cap_rel (the script keeps it 0)
        grant_bits=2,
        # PG187
        status_names=(
            "heartbeat", "initialization", "observation", "correction",
            "classification", "injection", "diagnostic_scan",
            "detect_only", "essential", "uncorrectable",
        ),
        frame_words=123,
        ecc_words=(60, 61),
    ),
}

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
BOARD = BOARDS["basys3"]
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051

# The experiments to run, in this order (see the docstring at the top)
EXPERIMENTS = (1, 2, 3 ,4 , 5)
# The pblock of the SEM in the XDC files
SEM_PBLOCK = "pblock_sem"
# The seed of the SK-RAFT random generator. Each experiment sets it before
# its injections, so the same experiment hits the same bits in every run.
SEED = 12
# The number of SBUs (rounds) in experiment 5
NUM_SEM_UPSETS = 1000

# The SEM report is complete when the UART is silent for this time.
QUIET_S = 1.0
# The maximum time for the SEM to initialize or to report.
WAIT_S = 10.0
# After the reply to O: the time to wait for more SEM reports.
REPORT_WAIT_S = 0.5
# The same SEM report this many times in one round is a correction loop.
LOOP_LIMIT = 3

# --------------------------------------------------------------------------- #
# Derived values. Do not change.
# --------------------------------------------------------------------------- #
# The example folder: the parent of src/
ROOT = Path(__file__).resolve().parent.parent
IMPL_DIR = (ROOT / BOARD.folder / "sem_arbitration"
            / "sem_arbitration.runs" / "impl_1")
design = Design(
    bit=str(IMPL_DIR / f"{BOARD.top}.bit"),
    ebd=str(IMPL_DIR / f"{BOARD.top}.ebd"),
    xdc=str(ROOT / BOARD.folder / "hw" / "xdc" / BOARD.xdc),
)

USER_CLK_EN = BscanPrimitive(1, 1)
USER_GRANT = BscanPrimitive(2, BOARD.grant_bits)
USER_SEM_STATUS = BscanPrimitive(3, len(BOARD.status_names))

# The block type field of the FAR (bits 25:23, the same on both families).
# Block type 0 is the configuration frames (logic and routing). The SEM
# does not correct block type 1 (BRAM content).
BLOCK_TYPE_SHIFT = 23
BLOCK_TYPE_MASK = 0b111

# The status bits of the SEM states. All of them 1 is the fatal error state.
STATES = ("initialization", "observation", "correction", "classification",
          "injection")
FATAL = sum(1 << BOARD.status_names.index(name) for name in STATES)
UNCORRECTABLE = 1 << BOARD.status_names.index("uncorrectable")


def read_status(dev: FpgaDevice) -> int:
    """
    Read the SEM status signals (USER3).

    Parameters:
        dev (FpgaDevice): The attached device.

    Returns:
        int: The status bits. Bit 0 is status_heartbeat.
    """
    data = dev.read_bscan(USER_SEM_STATUS)
    return int.from_bytes(data, "big") & ((1 << len(BOARD.status_names)) - 1)


# --------------------------------------------------------------------------- #
# Injections
# --------------------------------------------------------------------------- #
def pick_bit(dev: FpgaDevice, target: TargetMemory,
             pblock: str | None = None,
             exclude: set[str] | None = None) -> Upset:
    """
    Inject one upset at a random location.

    If the location is in a BRAM content frame (block type 1), the function
    prints it. The essential bits also include BRAM content bits.

    Parameters:
        dev (FpgaDevice): The attached device.
        target (TargetMemory): The memory for the random pick.
        pblock (str | None): The pblock for the random pick, or None for
            the whole device.
        exclude (set[str] | None): The pblocks that the random pick must
            not hit, or None.

    Returns:
        Upset: The location of the upset.
    """
    hit = dev.inject_random(target, pblock=pblock, exclude_pblock=exclude)
    block_type = (hit.far >> BLOCK_TYPE_SHIFT) & BLOCK_TYPE_MASK
    if block_type == 1:
        print(f"BRAM content bit: far {hit.far:08x} (block type 1) word "
              f"{hit.word_index:>3} bit {hit.bit_index:>2}")
    return Upset(hit.far, hit.word_index, hit.bit_index)


def adjacent_bits(dev: FpgaDevice) -> list[Upset]:
    """Experiment 2: two adjacent bits in one word of a frame."""
    first = pick_bit(dev, TargetMemory.CRAM, exclude={SEM_PBLOCK})
    bit = first.bit + 1 if first.bit < 31 else first.bit - 1
    dev.inject_at(first.far, first.word, bit, TargetMemory.CRAM)
    return [first, Upset(first.far, first.word, bit)]


def three_bits(dev: FpgaDevice) -> list[Upset]:
    """Experiment 3: three bits in one frame, in different words."""
    first = pick_bit(dev, TargetMemory.CRAM, exclude={SEM_PBLOCK})
    words = [w for w in range(BOARD.frame_words)
             if w != first.word and w not in BOARD.ecc_words]
    upsets = [first]
    for word in random.sample(words, 2):
        bit = random.randrange(32)
        dev.inject_at(first.far, word, bit, TargetMemory.CRAM)
        upsets.append(Upset(first.far, word, bit))
    return upsets


@dataclass(frozen=True)
class Experiment:
    """One experiment: a title, the injection and the expected result."""

    title: str
    inject: Callable[[FpgaDevice], list[Upset]]
    expected: str
    # The number of rounds (idle, inject, observation)
    rounds: int = 1


EXPERIMENT_LIST = {
    1: Experiment("One SBU anywhere",
                  lambda dev: [pick_bit(dev, TargetMemory.CRAM,
                                        exclude={SEM_PBLOCK})],
                  "The SEM corrects the bit and reports it."),
    2: Experiment("Two adjacent bits in one word", adjacent_bits,
                  "7 series: the SEM detects a double error (DED) and "
                  "stops as uncorrectable. UltraScale: the SEM corrects "
                  "both bits and reports them."),
    3: Experiment("Three bits in one frame", three_bits,
                  "The SEM cannot correct the frame and stops as "
                  "uncorrectable (7 series: SED NG, or a wrong correction "
                  "and then CRC)."),
    4: Experiment("One SBU in an essential bit of the SEM",
                  lambda dev: [pick_bit(dev, TargetMemory.ESSENTIAL_CRAM,
                                        SEM_PBLOCK)],
                  "The SEM corrects the bit and reports it."),
    5: Experiment(f"{NUM_SEM_UPSETS} SBUs in essential bits of the SEM, "
                  f"one at a time",
                  lambda dev: [pick_bit(dev, TargetMemory.ESSENTIAL_CRAM,
                                        SEM_PBLOCK)],
                  "The SEM corrects SBUs in its own logic until one breaks "
                  "it: it stops answering, or it loops on a wrong "
                  "correction.", rounds=NUM_SEM_UPSETS),
}


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
def inject_round(dev: FpgaDevice, sem: SemUart,
                 experiment: Experiment) -> tuple[list[Upset], str]:
    """
    Do one round: idle, inject with the clock off, observation.

    Parameters:
        dev (FpgaDevice): The attached device.
        sem (SemUart): The UART of the SEM.
        experiment (Experiment): The experiment.

    Returns:
        tuple[list[Upset], str]: The injected upsets, and the UART text of
            the SEM after O.

    Raises:
        RuntimeError: If the SEM does not go to idle.
    """
    # Put the SEM in idle: it stops scanning and does not use the ICAP.
    sem.send("I")
    status = read_status(dev)
    state = status_text(status, BOARD.status_names, FATAL)
    print(f"SEM status after I: {state}")
    # FATAL holds all the state bits: any of them set means not idle
    if status & FATAL:
        raise RuntimeError("the SEM did not go to idle")

    # Stop the clock during the injections. SK-RAFT reads a frame, flips a
    # bit and writes the frame back.
    dev.write_bscan(USER_CLK_EN, 0)
    print("clock off")
    upsets = experiment.inject(dev)
    for upset in upsets:
        block_type = (upset.far >> BLOCK_TYPE_SHIFT) & BLOCK_TYPE_MASK
        print(f"injected far {upset.far:08x} (block type {block_type})"
              f" word {upset.word:>3} bit {upset.bit:>2}")

    # Start the clock again, send the SEM back to observation (without a
    # new initialization) and read its reports.
    dev.write_bscan(USER_CLK_EN, 1)
    print("clock on")
    return upsets, sem.send("O") + sem.read(REPORT_WAIT_S)


def run(dev: FpgaDevice, sem: SemUart, number: int) -> None:
    """
    Run one experiment.

    Parameters:
        dev (FpgaDevice): The attached device.
        sem (SemUart): The UART of the SEM.
        number (int): The number of the experiment (EXPERIMENT_LIST).
    """
    experiment = EXPERIMENT_LIST[number]
    print(f"\n=== Experiment {number}: {experiment.title} ===")

    # Program the design, so that the experiment starts from a clean
    # configuration. Start the clock and give the grant: the SEM
    # initializes and goes to observation.
    sem.muted = True
    dev.programFPGA(design)
    sem.flush()
    dev.write_bscan(USER_CLK_EN, 1)
    dev.write_bscan(USER_GRANT, 1)
    print("grant = 1")
    # Wait for the observation prompt: inject only after the SEM has
    # initialized.
    if "O>" not in sem.wait_for("O>"):
        raise RuntimeError(f"the SEM did not start in {WAIT_S} s")

    dev.configure_seed(SEED)
    injected = caught = 0
    for n in range(1, experiment.rounds + 1):
        if experiment.rounds > 1:
            print(f"\n--- Round {n} of {experiment.rounds} ---")
        upsets, text = inject_round(dev, sem, experiment)
        injected += len(upsets)
        # With many rounds, only the total at the end
        caught += print_reports(upsets, text, True,
                                total=experiment.rounds == 1)
        status = read_status(dev)
        state = status_text(status, BOARD.status_names, FATAL)
        print(f"SEM status: {state}{', HLT' if 'HLT' in text else ''}")
        if status & UNCORRECTABLE:
            print("The SEM reported an uncorrectable error.")
        loop = repeated_report(text, LOOP_LIMIT)
        if loop:
            print(f"The SEM is stuck in a correction loop: {loop}")
        # Stop the rounds if the SEM failed, loops or does not answer
        if (status & UNCORRECTABLE or "HLT" in text or "O>" not in text
                or loop):
            if n < experiment.rounds:
                print(f"Stopped after round {n}: the SEM failed, loops or "
                      f"does not answer.")
            break

    if experiment.rounds > 1:
        print(f"\nIn total, the SEM reported {caught} of {injected} "
              f"injected bits.")
    print(f"Expected: {experiment.expected}")


def main() -> int:
    """Run the experiments."""
    print(f"SEM arbitration experiments ({BOARD.folder})")
    try:
        with SkraftFpga.connect(
            ip=SK_RAFT_SERVER_IP, port=SK_RAFT_SERVER_PORT
        ) as client, client.attach(BOARD.serial_number) as dev:
            # Setup the SEED for deterministic behaviour. 
            dev.configure_seed(0)

            sem = SemUart(BOARD.uart_port, QUIET_S)
            dev.uploadDesignToServer(design)
            for number in EXPERIMENTS:
                run(dev, sem, number)

            # Program the design again: the experiments leave upsets in the
            # CRAM
            dev.programFPGA(design)
            print("\nProgrammed the design again: the CRAM is clean.")
    except (SkraftError, RuntimeError, serial.SerialException) as e:
        print(f"\nStopped: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
