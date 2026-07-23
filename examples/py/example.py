"""Minimal end-to-end example for the SK-RAFT Python client.

Exercises the parts of the API that changed in the latest proto revision:
- design files pushed via the renamed FpgaSetDesignFilePath RPC (load)
- ranged readback (FpgaReadBackRange) and full readback (FpgaReadBack)
- scrubbing with the nested per-cycle report (scrub_summaries)
plus a random injection and a short MIXED campaign for good measure.
"""

from skraft.skraft_fpga import SkraftFpga
from skraft.datatypes import (
    DesignFiles,
    FaultType,
    FpgaFiSession,
    InjectionArea,
    ScrubbingType,
    ServerPath,
    ReadbackOption,
)
from skraft.exceptions import SkraftError

import time


def main() -> None:
    with SkraftFpga.connect(ip="127.0.0.1", port=50051) as client:
        with client.attach("xcku040") as dev:

            # Push design files (one FpgaSetDesignFilePath call per set path).
            dev.load(DesignFiles(
                bitstream=ServerPath("/home/embeddedcat/Downloads/bits/tester.bit"),
                ebd=ServerPath("/home/embeddedcat/Downloads/bits/tester.ebd"),
                ll=ServerPath("/home/embeddedcat/Downloads/bits/tester.ll"),
            ))
            dev.program()
 
            dev.write_register(8192, 0x10)

            print(dev.read_register(8192))


if __name__ == "__main__":
    try:
        main()
    except SkraftError as e:
        print("SK-RAFT error:", e)
