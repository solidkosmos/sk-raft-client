"""TEST 2 - Program the device, then inject cumulative random CRAM upsets.

Same injection loop as TEST 1, but the design is programmed first, so the
corrupted bits belong to a known configuration.

BITSTREAM is resolved on the SK-RAFT *server* filesystem, not on this machine
- that is what ``ServerPath`` marks.
"""

from skraft import InjectionArea
from skraft.datatypes import DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

NUMBER_OF_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "<SK_RAFT_SERVER_IP>"  # e.g. "192.168.1.50"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

DESIGN = "<DESIGN_PATH_ON_SERVER>"  # server-side folder holding this design's tester.* files
BITSTREAM = ServerPath(f"{DESIGN}/tester.bit")


def inject_random_cram(dev, injections: int) -> None:
    """Inject ``injections`` random single-bit upsets into the whole CRAM."""
    for i in range(1, injections + 1):
        report = dev.inject_random(InjectionArea.CRAM)

        print(f"----- INJECTION {i}/{injections} -----")
        print(f"FAR:        {report.far:#010x}")
        print(f"WORD_INDEX: {report.word_index}")
        print(f"BIT_INDEX:  {report.bit_index}")


def main() -> None:
    print("Example 2: Program the device, then inject cumulative random CRAM upsets")
    print("TEST 2: program the device, then random CRAM injection.")

    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM))
                dev.program()
                print(f"Programmed {DEVICE} with {BITSTREAM}.")

                inject_random_cram(dev, NUMBER_OF_INJECTIONS)
    except SkraftError as e:
        print(f"TEST 2 failed: {e}")
        return

    print(f"TEST 2 done: {NUMBER_OF_INJECTIONS} upsets injected.")


if __name__ == "__main__":
    main()
