"""Flip-flop injection confined to the shift-register pblock.

The design under test is reachable through four BSCAN USER registers:

    USER1    1 bit     CLK_EN, clock enable    (read/write)
    USER2    4 bits    address select          (read/write)
    USER3   32 bits    data                    (read/write)
    USER4    8 bits    shift register          (read)

Only the shift register matters here. Its eight bits are read out of USER4,
and the upsets are aimed at the flip-flops that hold them, so a change in
USER4 is direct evidence that the injected bit was one of them.

The pblock is what makes this safe to observe. USER1 to USER4 are the only
way into the design, so the BSCAN interface and the logic around it are the
source of truth for every measurement: upset a flip-flop in there and the
readings stop meaning anything, since a wrong value in USER4 could equally be
a corrupted shift register or a corrupted path to it. Confining the pblock to
the shift register keeps injection away from that interface, so anything seen
on USER4 is the fault under test and not the instrument reporting it.

Two sources decide where an upset may land, and only their overlap is used:

* the logic location (LL) file names every flip-flop bit of the design.
  ``dev.inject_exhaustive(InjectionArea.FLIP_FLOP)`` reports each one with
  its net name, which is how this example reads that list back through the
  API. The sweep does upset them, so the device is re-programmed immediately
  afterwards and the run starts from a clean design.
* the XDC declares a pblock around the shift register. ``dev.pblocks()`` and
  ``dev.pblock_by_clause()`` turn it into the frames and bits it occupies.

The clock is briefly enabled so the shift register holds live data, then
stopped, so its contents are stable and every later change is down to an
injected fault rather than the design running on.
"""

from __future__ import annotations

import random
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

# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM = ServerPath("/home/embeddedcat/Desktop/test_lut_ff.bit")
LL = ServerPath("/home/embeddedcat/Desktop/test_lut_ff.ll")
XDC = ServerPath("/home/embeddedcat/Desktop/test_lut_ff.xdc")

# The pblock around the shift register, as named in the XDC.
PBLOCK = "pblock_ff_sr_inst"

# "random" samples the flip-flops of the pblock; "exhaustive" upsets every
# one of them, in order.
MODE = "random"

# How many upsets to inject in "random" mode.
INJECTIONS = 50

LOG_PATH = "sr_flipflop_injection.log"  # None disables the transcript
VERBOSE = False                         # True also prints the per-bit detail

# The design's BSCAN USER registers, from the specification above.
USER_CLK_EN = BscanPrimitive(1, 1)
USER_SR = BscanPrimitive(4, 8)

WORD_BITS = 32
SR_MASK = (1 << USER_SR.size_in_bits) - 1

# Seconds the clock runs before it is stopped, so the shift register holds
# something other than its reset value.
SETTLE_S = 0.1


# --------------------------------------------------------------------------- #
# Talking to the shift register over BSCAN
# --------------------------------------------------------------------------- #
def set_clock(dev, enabled: bool) -> None:
    """Start or stop the design's clock through USER1."""
    dev.write_bscan(USER_CLK_EN, 1 if enabled else 0)


def read_sr(dev) -> int:
    """Read the eight shift-register bits out of USER4."""
    return int.from_bytes(dev.read_bscan(USER_SR), "big") & SR_MASK


def freeze(dev) -> int:
    """Let the design run briefly, stop the clock, and snapshot USER4."""
    set_clock(dev, True)
    time.sleep(SETTLE_S)
    set_clock(dev, False)
    snapshot = read_sr(dev)
    stage(f"Clock stopped, shift register holds {snapshot:#04x}")
    return snapshot


# --------------------------------------------------------------------------- #
# Choosing the target bits
# --------------------------------------------------------------------------- #
def area_bits(area):
    """Yield the ``(word_index, bit_index)`` pairs an occupied area covers.

    ``bit_range`` counts bits along the frame from its start, so bits 0 to 31
    are word 0, bits 32 to 63 are word 1, and so on.
    """
    for position in range(area.bit_range.start, area.bit_range.end + 1):
        yield position // WORD_BITS, position % WORD_BITS


def pblock_footprint(dev, name: str) -> set[tuple[int, int, int]]:
    """Every bit the named pblock of the XDC occupies."""
    for pblock in dev.pblocks():
        if pblock.name != name:
            continue
        footprint = {
            (frame.far, word, bit)
            for clause in pblock.clauses
            for frame in dev.pblock_by_clause(clause)
            for area in frame.occupied_area
            for word, bit in area_bits(area)
        }
        stage(f"{name}: {len(footprint)} bits in the footprint")
        return footprint
    raise SkraftError(f"{name} is not declared in {XDC}")


def flipflop_bits(dev) -> dict[tuple[int, int, int], str]:
    """Every flip-flop bit of the design, mapped to its net name.

    Read out of the LL file by way of an exhaustive flip-flop sweep, which
    reports each location it hits. The sweep leaves the design upset, so the
    caller must re-program before testing anything.
    """
    stage("Reading the flip-flop locations (LL) with an exhaustive sweep")
    upsets, injected = dev.inject_exhaustive(InjectionArea.FLIP_FLOP)
    stage(f"{injected} flip-flop bits reported at {len(upsets)} locations")
    return {(upset.far, upset.word_index, upset.bit_index):
            upset.net_name or "" for upset in upsets}


def target_bits(dev) -> list[tuple[int, int, int]]:
    """The flip-flop bits that lie inside the shift-register pblock."""
    footprint = pblock_footprint(dev, PBLOCK)
    flipflops = flipflop_bits(dev)

    stage("Re-programming to clear the sweep")
    dev.program()

    sites = sorted(footprint & set(flipflops))
    stage(f"{len(sites)} flip-flop bits are inside {PBLOCK}")
    for site in sites:
        detail(f"FAR={site[0]:#010x} word {site[1]} bit {site[2]} "
               f"{flipflops[site]}")
    return sites


# --------------------------------------------------------------------------- #
# Injecting
# --------------------------------------------------------------------------- #
def chosen_bits(sites: list[tuple[int, int, int]]
                ) -> list[tuple[int, int, int]]:
    """The bits this run will upset, in the order they will be upset."""
    if MODE == "exhaustive":
        return sites
    return [random.choice(sites) for _ in range(INJECTIONS)]


def campaign(dev, sites: list[tuple[int, int, int]], frozen: int,
             started: float) -> None:
    """Upset one flip-flop at a time, reading USER4 after each one.

    The upsets are left in place, so each row compares USER4 against the
    read taken before that upset rather than against the frozen snapshot.
    """
    targets = chosen_bits(sites)
    stage(f"{MODE.capitalize()} injection: {len(targets)} upsets, "
          f"not corrected")
    emit("   #  FAR         WORD  BIT  BEFORE  AFTER  CHANGED   ELAPSED")

    state = frozen
    seen = 0
    for index, (far, word_index, bit_index) in enumerate(targets, start=1):
        dev.inject_at(far, word_index, bit_index, InjectionArea.FLIP_FLOP)

        after = read_sr(dev)
        changed = state ^ after
        if changed:
            seen += 1
        else:
            warn(f"injection {index}: FAR={far:#010x} word {word_index} bit "
                 f"{bit_index} left USER4 at {after:#04x}")

        emit(f"{index:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{state:#04x}    {after:#04x}   {changed:#04x}      "
             f"{elapsed_since(started):>7}")
        state = after

    stage(f"{seen}/{len(targets)} upsets changed the shift register")
    stage(f"USER4 started at {frozen:#04x} and ended at {state:#04x}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    configure(verbose=VERBOSE, warning_noun="silent upsets",
              warning_hint="the CHANGED column reports them all")
    open_log(LOG_PATH)
    started = time.perf_counter()
    try:
        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ll=LL, xdc=XDC))
                dev.program()
                stage(f"Programmed {DEVICE}, {dev.ff_bits} flip-flop bits "
                      f"in the design")

                sites = target_bits(dev)
                if not sites:
                    stage("Nothing to inject: no flip-flop of the LL file "
                          "falls inside the pblock. Check that the XDC, the "
                          "LL and the bitstream belong together.")
                    return

                campaign(dev, sites, freeze(dev), started)

                stage("The design is left with the injected upsets; "
                      "re-program the device before running anything else")
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
