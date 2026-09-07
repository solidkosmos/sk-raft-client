from skraft import InjectionArea
from skraft.skraft_fpga import SkraftFpga

NUMBER_OF_INJECTIONS = 1000
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

def main():
    print("Example 1: Inject occumulative, random, faults into the CRAM ONLY.")

    with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP, port=SK_RAFT_SERVER_PORT) as client:
        with client.attach(DEVICE) as dev:
            for _ in range(NUMBER_OF_INJECTIONS):
                report = dev.inject_random(InjectionArea.CRAM)
            
                print("----- INJECTION REPORT -----")
                print(f"FAR: {report.far:#010x}")
                print("WORD_INDEX: ", report.word_index)
                print("BIT_INDEX: ", report.bit_index)

if __name__ == "__main__":
    main()
