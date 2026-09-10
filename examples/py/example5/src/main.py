"""Fault injection confined to a pblock.

``targeted.xdc`` puts each heartbeat generator of the Basys3 design in its own
pblock:

    pblock_fast_heartbeat   SLICE_X54Y91:SLICE_X57Y99
    pblock_slow_heartbeat   SLICE_X62Y56:SLICE_X65Y65

``dev.pblocks()`` lists them from the loaded XDC, and ``dev.pblock_by_clause()``
turns a clause into the frames it covers, together with the words and bits of
each frame that belong to the pblock. Injecting only into those bits keeps
every upset inside one heartbeat generator, leaving the other one and the rest
of the device alone.
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
)
from skraft import InjectionArea
from skraft.datatypes import DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM = ServerPath("/home/embeddedcat/Desktop/targeted.bit")
EBD = ServerPath("/home/embeddedcat/Desktop/targeted.ebd")
XDC = ServerPath("/home/embeddedcat/Desktop/targeted.xdc")

# The pblock to attack, as named in the XDC.
PBLOCK = "pblock_fast_heartbeat"

# How many upsets to inject at random positions inside it.
INJECTIONS = 300

# Seconds to wait after each upset, so the heartbeat LED can be watched.
# Set to 0 to run at full speed.
PAUSE_S = 0.1

# True narrows the target to the essential bits of the pblock, so every upset
# lands on a bit the design depends on. False uses the whole footprint, most
# of which is unused CRAM.
ESSENTIAL_ONLY = True

LOG_PATH = "pblock_injection.log"  # None disables the transcript
VERBOSE = False                    # True also prints the per-bit detail

WORD_BITS = 32
WORDS_PER_FRAME = 101  # a 7-series configuration frame
AREA = InjectionArea.ESSENTIAL_CRAM if ESSENTIAL_ONLY else InjectionArea.CRAM


def find_pblock(dev, name: str):
    """Return the named pblock of the loaded XDC."""
    available = dev.pblocks()
    stage(f"Pblocks in the XDC: {', '.join(p.name for p in available)}")
    for pblock in available:
        if pblock.name == name:
            return pblock
    raise SkraftError(f"{name} is not declared in {XDC}")


def area_bits(area):
    """Yield the ``(word_index, bit_index)`` pairs an occupied area covers.

    A frame is a flat sequence of 32-bit words, and ``bit_range`` counts
    bits along it from the start of the frame: bits 0 to 31 are word 0, bits
    32 to 63 are word 1, and so on. Dividing by 32 therefore gives the word
    and the remainder gives the bit inside it, which is the coordinate pair
    ``essential_frames()`` and ``inject_at()`` work in.
    """
    for position in range(area.bit_range.start, area.bit_range.end + 1):
        yield position // WORD_BITS, position % WORD_BITS


def pblock_bits(dev, pblock):
    """Yield ``(far, word_index, bit_index)`` for every CRAM bit of a pblock.

    Each clause resolves to a list of frames, and each frame reports the
    areas of it the pblock occupies.
    """
    for clause in pblock.clauses:
        frames = dev.pblock_by_clause(clause)
        detail(f"clause {clause} covers {len(frames)} frames")
        for frame in frames:
            for area in frame.occupied_area:
                for word, bit in area_bits(area):
                    yield frame.far, word, bit


def essential_bits(dev, fars: set[int]) -> set[tuple[int, int, int]]:
    """The essential bits of the given frames, from the EBD file.

    Returned as ``(far, word_index, bit_index)`` with ``bit_index`` counted
    inside its own 32-bit word, so the set can be intersected with the
    pblock bits produced by :func:`area_bits`.
    """
    bits = set()
    for frame in dev.essential_frames():
        if frame.far not in fars:
            continue
        for word_index, word in enumerate(frame.words):
            for bit in range(WORD_BITS):
                if (word.value >> bit) & 1:
                    bits.add((frame.far, word_index, bit))
    return bits


def target_bits(dev, pblock) -> list[tuple[int, int, int]]:
    """The bits inside the pblock that this run may inject into."""
    sites = sorted(set(pblock_bits(dev, pblock)))
    stage(f"{pblock.name}: {len(sites)} CRAM bits in the footprint")

    if not ESSENTIAL_ONLY:
        return sites

    essential = essential_bits(dev, {far for far, _, _ in sites})
    sites = [site for site in sites if site in essential]
    stage(f"{pblock.name}: {len(sites)} of them are essential")
    return sites

def campaign(dev, sites: list[tuple[int, int, int]], started: float) -> None:
    """Inject ``INJECTIONS`` upsets at random sites inside the pblock."""
    stage(f"Injecting {INJECTIONS} upsets into {PBLOCK}")
    emit("   #  FAR         WORD  BIT  ELAPSED")

    for index in range(1, INJECTIONS + 1):
        far, word_index, bit_index = random.choice(sites)
        dev.inject_at(far, word_index, bit_index, AREA)
        emit(f"{index:>4}  {far:#010x}  {word_index:>4}  {bit_index:>3}  "
             f"{elapsed_since(started):>7}")
        if PAUSE_S:
            time.sleep(PAUSE_S)

def main() -> None:
    configure(verbose=VERBOSE)
    open_log(LOG_PATH)
    started = time.perf_counter()
    try:
        stage(f"Connecting to the SK-RAFT server at "
              f"{SK_RAFT_SERVER_IP}:{SK_RAFT_SERVER_PORT}")
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            stage(f"Connected, server version {client.version()}")

            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM, ebd=EBD, xdc=XDC))
                dev.program()
                stage(f"Programmed {DEVICE}")

                sites = target_bits(dev, find_pblock(dev, PBLOCK))
                if not sites:
                    stage("Nothing to inject: check that the XDC and the EBD "
                          "belong to the programmed bitstream.")
                    return

                campaign(dev, sites, started)

                stage(f"{INJECTIONS} upsets injected into {PBLOCK}; "
                      f"re-programming to clear them")
                dev.program()
                stage(f"Done in {elapsed_since(started)}")
    except SkraftError as e:
        stage(f"Failed: {e}")
    except KeyboardInterrupt:
        stage(f"Interrupted after {elapsed_since(started)}")
    finally:
        close_log()


if __name__ == "__main__":
    main()
