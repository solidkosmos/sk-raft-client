# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""TLS example: program the FPGA through a secure connection.

This example connects to the SK-RAFT server through TLS, with
authentication in the two directions:

  - The client verifies the server with the server certificate
    (server.crt).
  - The server accepts only a client that holds the private key
    (client.key) of the public key that the server got with
    -tls-public-key (client_public.pem).

Then the example reserves one device, uploads a bitstream and programs
the FPGA. It does nothing else.

Start the server with the TLS files first:

    ./skraft-<version> -port 50051 -tls-cert server.crt \\
        -tls-key server.key -tls-public-key client_public.pem

README.md shows how to make the TLS files with OpenSSL.
"""

from skraft import Design, SkraftError, SkraftFpga

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
# The address of the server. It must be one of the subjectAltName entries
# of server.crt, else the client refuses the server.
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BFD452A"

# The TLS files of the client. The paths are relative to src/. Run the
# script from that folder.
CERTS_DIR = "../certs"
# The certificate of the server. It holds the public key of the server.
# The client uses it to verify the server.
SERVER_CERT = f"{CERTS_DIR}/server.crt"
# The certificate of this client. It holds the public key of the client,
# the same public key as client_public.pem on the server.
CLIENT_CERT = f"{CERTS_DIR}/client.crt"
# The private key of this client. Keep it secret. Do not copy it to the
# server.
CLIENT_KEY = f"{CERTS_DIR}/client.key"

# The bitstream to program: the prebuilt design of the getting-started
# examples. BOARD is "basys3" or "zedboard". Extract design_examples.zip
# first (see get_started/README.md), or set your own bitstream.
BOARD = "basys3"
BITSTREAM = (f"../../../get_started/hw/design_examples/{BOARD}/"
             "targeted_top/targeted_top.bit")


def main() -> int:
    """
    Program the FPGA through a TLS connection.

    Returns:
        int: 0 if the FPGA is programmed, else 1.
    """
    design = Design(bit=BITSTREAM)
    try:
        # The TLS files make the connection secure. Without them,
        # connect() opens a connection without TLS, and the server
        # refuses it.
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT,
                                tls_server_cert=SERVER_CERT,
                                tls_cert=CLIENT_CERT,
                                tls_key=CLIENT_KEY) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"programmed {SERIAL_NUMBER} ({dev.part_number}) "
                      f"with {design.bit}")
    except (SkraftError, OSError) as e:
        print(f"error: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
