"""LUTRAM injection with a BSCAN memory self-test.

The design under test is a small memory built out of LUTRAM, reachable
through four BSCAN USER registers:

    USER1    1 bit     CLK_EN, clock enable    (read/write)
    USER2    4 bits    address select          (read/write)
    USER3   32 bits    data                    (read/write)
    USER4    8 bits    shift register          (read)

A known pattern is written into the ten memory words and the clock is
stopped, so nothing but an injected fault can change them. The LUTRAM bits
are then upset and the words are read back: every corrupted word is reported
with the value it should hold and the value it actually holds.

The upsets are not undone. A flipped LUTRAM bit is a corrupted memory cell,
so the corruption stays for the rest of the run and the memory ends it dirty.
Re-program the device before running anything else.

The LUTRAM bit locations come from the logic location (LL) file: the server
reads it and ``InjectionArea.LUTRAM`` narrows injection to those bits, so no
bit outside the memory is ever touched.

``MODE`` chooses how they are hit:

* ``random`` calls ``dev.inject_random()`` ``INJECTIONS`` times and reads the
  memory after each upset, so every corrupted word is tied to one bit.
* ``exhaustive`` calls ``dev.inject_exhaustive()`` once. That sweep happens in
  a single server-side pass, so the memory is read once afterwards and every
  word is reported.
"""

from __future__ import annotations

import time

from reporting import (
    close_log,
    configure,
    detail,
    elapsed_since,
    emit,
    open_log,
    stage,
    warn,
)
from skraft import InjectionArea
from skraft.datatypes import BscanPrimitive, DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM = ServerPath("/home/embeddedcat/Desktop/test_lut_ff.bit")
LL = ServerPath("/home/embeddedcat/Desktop/test_lut_ff.ll")

# "random" samples LUTRAM bits one at a time; "exhaustive" sweeps every one
# of them in a single call.
MODE = "random"

# How many upsets to inject in "random" mode.
INJECTIONS = 50

LOG_PATH = "lutram_injection.log"  # None disables the transcript
VERBOSE = False                    # True also prints the per-word detail

# The design's BSCAN USER registers, from the specification above.
USER_CLK_EN = BscanPrimitive(1, 1)
USER_ADDR = BscanPrimitive(2, 4)
USER_DATA = BscanPrimitive(3, 32)

MEMORY_DEPTH = 10  # words reachable through USER2
DATA_MASK = (1 << USER_DATA.size_in_bits) - 1

def set_clock(dev, enabled: bool) -> None:
    """Start or stop the design's clock through USER1."""
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)

def write_word(dev, address: int, value: int) -> None:
    """Write one 32-bit word, address on USER2 and data on USER3."""
    dev.write_bscan(USER_ADDR, address)
    dev.write_bscan(USER_DATA, value)


def read_word(dev, address: int) -> int:
    """Read the 32-bit word at ``address`` back out of USER3."""
    dev.write_bscan(USER_ADDR, address)
    return int.from_bytes(dev.read_bscan(USER_DATA), "big") & DATA_MASK

def pattern(address: int) -> int:
    """The word this run expects to find at ``address``.

    Alternating bits, so a single upset anywhere in the word shows up, and a
    different value per address, so a mis-addressed read is visible too.
    """
    return (0xA5A5A5A5 ^ (address * 0x01010101)) & DATA_MASK

def fill_memory(dev) -> None:
    """Write the pattern into every word, then stop the clock."""
    set_clock(dev, True)
    for address in range(MEMORY_DEPTH):
        write_word(dev, address, pattern(address))
    set_clock(dev, False)
    detail(f"wrote {MEMORY_DEPTH} words and stopped the clock")

def read_memory(dev) -> list[int]:
    """Read all ten words back through USER3."""
    return [read_word(dev, address) for address in range(MEMORY_DEPTH)]

def corrupted(state: list[int]) -> list[tuple[int, int, int]]:
    """The words of ``state`` that differ from the pattern.

    Each entry is ``(address, correct_word, erroneous_word)``.
    """
    return [(address, pattern(address), state[address])
            for address in range(MEMORY_DEPTH)
            if state[address] != pattern(address)]

TABLE_HEADER = ("   #  FAR         WORD  BIT  ADDR  CORRECT     "
                "ERRONEOUS   ELAPSED")

def row(index: int, upset, text: str, started: float) -> None:
    """One table row: where the upset went, and what it did to the memory."""
    emit(f"{index:>4}  {upset.far:#010x}  {upset.word_index:>4}  "
         f"{upset.bit_index:>3}  {text}  {elapsed_since(started):>7}")


def random_campaign(dev, started: float) -> None:
    """Upset ``INJECTIONS`` LUTRAM bits, reading the memory after each one."""
    stage(f"Random injection: {INJECTIONS} LUTRAM upsets, not corrected")
    emit(TABLE_HEADER)

    state = read_memory(dev)
    hits = 0
    for index in range(1, INJECTIONS + 1):
        upset = dev.inject_random(InjectionArea.LUTRAM)
        if upset.net_name:
            detail(f"injection {index}: net {upset.net_name}")

        after = read_memory(dev)
        changed = [address for address in range(MEMORY_DEPTH)
                   if after[address] != state[address]]
        state = after

        if not changed:
            row(index, upset, f"{'-':>4}  no change            ", started)
            continue

        hits += 1
        for address in changed:
            row(index, upset,
                f"{address:>4}  {pattern(address):#010x}  "
                f"{state[address]:#010x}", started)

    stage(f"{hits}/{INJECTIONS} upsets corrupted a memory word")
    report(state)


def exhaustive_campaign(dev) -> None:
    """Upset every LUTRAM bit of the design in one pass, then read back."""
    stage("Exhaustive injection over every LUTRAM bit, not corrected")
    upsets, injected = dev.inject_exhaustive(InjectionArea.LUTRAM)
    stage(f"{injected} bits injected at {len(upsets)} locations")
    report(read_memory(dev))


def report(state: list[int]) -> None:
    """List every word that no longer holds the value it was given."""
    bad = corrupted(state)
    stage(f"{len(bad)}/{MEMORY_DEPTH} words are corrupted")
    if not bad:
        return

    emit("  ADDR  CORRECT     ERRONEOUS   DIFFERING BITS")
    for address, correct, erroneous in bad:
        emit(f"  {address:>4}  {correct:#010x}  {erroneous:#010x}  "
             f"{correct ^ erroneous:#010x}")

def main() -> None:
    configure(verbose=VERBOSE, warning_noun="memory errors")
    open_log(LOG_PATH)
    started = time.perf_counter()
    try:
        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ll=LL))
                dev.program()
                stage(f"Programmed {DEVICE}, {dev.lutram_bits} LUTRAM bits "
                      f"in the design")

                fill_memory(dev)

                # A failure here is the USER register ids or widths, not an
                # injected upset.
                bad = corrupted(read_memory(dev))
                if bad:
                    for address, correct, erroneous in bad:
                        warn(f"baseline: [{address}] should be "
                             f"{correct:#010x}, reads {erroneous:#010x}")
                    stage("The memory reads back wrong before any injection: "
                          "check the USER register ids and widths.")
                    return
                stage("Baseline passed")

                if MODE == "exhaustive":
                    exhaustive_campaign(dev)
                else:
                    random_campaign(dev, started)

                stage("The memory is left corrupted; re-program the device "
                      "before running anything else")
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()

if __name__ == "__main__":
    main()
