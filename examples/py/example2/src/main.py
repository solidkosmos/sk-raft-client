from skraft import InjectionArea
from skraft import FaultType, FpgaFiSession
from skraft.skraft_fpga import SkraftFpga
from skraft.datatypes import (
    DesignFiles,
    ServerPath
)

NUMBER_OF_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

BITSTREAM_PATH = "/home/embeddedcat/Desktop/tester.bit"


def main():
    with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP, port=SK_RAFT_SERVER_PORT) as client:
        with client.attach(DEVICE) as dev:
            dev.load(DesignFiles(
                bitstream=ServerPath(BITSTREAM_PATH),
            ))
            dev.program()

            session = FpgaFiSession(
                    fault_type=FaultType.RANDOM,
                    duration_ms=5000,
                    correction_time_ms=0,
                    time_between_faults_ms=20,
                    sbu_percent=100,
                    mbu_percent=0,
                    mcu_percent=0,
                    target=InjectionArea.CRAM,
                    correct=False 
            )

            report = dev.run_campaign(session)
            
            print("----- INJECTION REPORT -----")
            print("Total Injections: ", report.faults_injected)
            for word in report.affected_words:
                print(f"FAR: {word.far:#010x}")
                print("WORD INDEX: ", word.word_index)
                print("BIT INDEX: ", word.bit_index)
                print("GOLDEN WORD VALUE: ", word.golden_word_value)
                print("WORD VALUE AFTER FAULT INJECTION: ", word.injected_word_value)
                print("---------------------------------")

if __name__ == "__main__":
    main()
