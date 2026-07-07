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
)
from skraft.exceptions import SkraftError


def main() -> None:
    with SkraftFpga.connect(ip="127.0.0.1", port=50052) as client:
        with client.attach("xcku040") as dev:

            # Push design files (one FpgaSetDesignFilePath call per set path).
            dev.load(DesignFiles(
                bitstream=ServerPath("/home/embeddedcat/Documents/SolidKosmos/Products/SK_RAFT/Boards/Tests/7Series/Basys3/unittests/designs/flipflop/tester.bit"),
                ebd=ServerPath("/home/embeddedcat/Documents/SolidKosmos/Products/SK_RAFT/Boards/Tests/7Series/Basys3/unittests/designs/flipflop/tester.ebd"),
                msd=ServerPath("/home/embeddedcat/Documents/SolidKosmos/Products/SK_RAFT/Boards/Tests/7Series/Basys3/unittests/designs/flipflop/tester.msd"),
                ll=ServerPath("/home/embeddedcat/Documents/SolidKosmos/Products/SK_RAFT/Boards/Tests/7Series/Basys3/unittests/designs/flipflop/tester.ll"),
            ))
            dev.program()

            # Bit statistics — five per-category calls, or all at once.
            print("CRAM bits:", dev.cram_bits)
            print("essential:", dev.essential_cram_bits)
            print("all counts:", dev.all_bit_counts)

            everything = dev.readback()
            print("total frames read back:", len(everything))

            # One random upset into essential CRAM or flip-flops.
            report = dev.inject_random(
                InjectionArea.CRAM
            )
            print(f"hit FAR 0x{report.far:08x} "
                  f"word {report.word_index} bit {report.bit_index} "
                  f"net={report.net_name}")

            # Scrub for 5 s; the report is now nested per scrub cycle.
            scrub = dev.scrub(
                ScrubbingType.ESSENTIAL,
                scrub_cycle=1000,       # ms between cycles
                duration_ms=5000,
                session_id="demo-1",
            )
            for cycle in scrub.scrub_summaries:
                print(f"cycle {cycle.scrub_cycle}: "
                      f"{len(cycle.word_summaries)} upsets, "
                      f"correction {cycle.correction_time_ms} ms")

            # A short mixed fault-injection campaign on essential bits.
            """
            summary = dev.run_campaign(FpgaFiSession(
                fault_type=FaultType.MIXED,
                duration_ms=10_000,
                correction_time_ms=100,
                time_between_faults_ms=500,
                sbu_percent=80.0,
                mbu_percent=15.0,
                mcu_percent=5.0,
                target=InjectionArea.ESSENTIAL_CRAM,
                correct=True,
            ))
            print(f"campaign: {summary.faults_injected} injected, "
                  f"{summary.corrected} corrected")
            """


if __name__ == "__main__":
    try:
        main()
    except SkraftError as e:
        print("SK-RAFT error:", e)
