# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""List the FPGA boards that are connected to the SK-RAFT server.

The script prints the serial number and the part number of each board.
Set SERIAL_NUMBER in the main.py of an example to the serial number of
your board.

Usage: python list_devices.py
"""

from skraft import SkraftError, SkraftFpga

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051


def main() -> int:
    try:
        # SK-RAFT: open the connection. Then list the connected boards.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            devices = client.get_devices()
    except SkraftError as e:
        print(f"Cannot list the boards: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130

    if not devices:
        print("No board is connected to the SK-RAFT server.")
        return 1
    print(f"{'SERIAL NUMBER':16s} PART NUMBER")
    for device in devices:
        print(f"{device.serial_number:16s} {device.part_number}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
