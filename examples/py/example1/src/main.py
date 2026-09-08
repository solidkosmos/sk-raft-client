"""TEST 1 - Cumulative random CRAM injection on an unprogrammed device.

No design file is loaded and the device is never programmed.
"""

from skraft import InjectionArea
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

NUMBER_OF_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"


def inject_random_cram(dev, injections: int) -> None:
    """Inject ``injections`` random single-bit upsets into the whole CRAM."""
    for i in range(1, injections + 1):
        report = dev.inject_random(InjectionArea.CRAM)

        print(f"----- INJECTION {i}/{injections} -----")
        print(f"FAR:        {report.far:#010x}")
        print(f"WORD_INDEX: {report.word_index}")
        print(f"BIT_INDEX:  {report.bit_index}")


def main() -> None:
    print("TEST 1: cumulative random CRAM injection, device NOT programmed.")

    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(DEVICE) as dev:
                inject_random_cram(dev, NUMBER_OF_INJECTIONS)
    except SkraftError as e:
        print(f"TEST 1 failed: {e}")
        return

    print(f"TEST 1 done: {NUMBER_OF_INJECTIONS} upsets injected.")


if __name__ == "__main__":
    main()
