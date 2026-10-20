# TLS: program the FPGA through a secure connection

This example connects to the SK-RAFT server through TLS, reserves one device, uploads a bitstream and programs the FPGA. It does nothing else.

The connection uses authentication in the two directions:

- The client verifies the server with the server certificate (`server.crt`).
- The server accepts only a client that holds the private key (`client.key`) of the public key that you give to the server (`client_public.pem`).

## The files

You make five files with OpenSSL. Each file has one location:

| File | Contents | Location | Used by |
| --- | --- | --- | --- |
| `server.key` | Private key of the server | Server only. Keep it secret. | Server: `-tls-key` |
| `server.crt` | Certificate of the server (public key of the server) | Server and client | Server: `-tls-cert`. Client: `tls_server_cert` |
| `client.key` | Private key of the client | Client only. Keep it secret. | Client: `tls_key` |
| `client.crt` | Certificate of the client (public key of the client) | Client | Client: `tls_cert` |
| `client_public.pem` | Public key of the client | Server | Server: `-tls-public-key` |

Make each private key on the computer that uses it. Then copy only the public files: `server.crt` to the client, and `client_public.pem` to the server.

## Make the TLS files with OpenSSL (Linux)

Use OpenSSL 1.1.1 or a later version (`openssl version`). The commands make EC P-256 keys.

### On the server computer

```bash
mkdir -p certs && cd certs

# 1. Private key of the server.
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out server.key
chmod 600 server.key

# 2. Self-signed certificate of the server, valid for 365 days.
#    Put in subjectAltName each address and host name that the clients use
#    to connect, for example the IP address of the server.
openssl req -new -x509 -key server.key -out server.crt -days 365 \
    -subj "/CN=sk-raft-server" \
    -addext "subjectAltName=IP:192.168.1.50,IP:127.0.0.1,DNS:localhost"

# 3. Examine the certificate: names and end date.
openssl x509 -in server.crt -noout -subject -ext subjectAltName -enddate
```

### On the client computer

```bash
mkdir -p certs && cd certs

# 1. Private key of the client.
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out client.key
chmod 600 client.key

# 2. Self-signed certificate of the client. The server checks only the
#    public key in it, not the name or the dates.
openssl req -new -x509 -key client.key -out client.crt -days 365 \
    -subj "/CN=sk-raft-client"

# 3. Public key of the client, for the server.
openssl pkey -in client.key -pubout -out client_public.pem

# 4. Make sure that client.crt and client_public.pem hold the same key.
openssl x509 -in client.crt -noout -pubkey | diff - client_public.pem \
    && echo "public keys match"
```

### Copy the public files

```bash
# From the client computer: the public key of the client to the server.
scp certs/client_public.pem user@192.168.1.50:sk-raft/certs/

# From the server computer: the certificate of the server to the client.
scp certs/server.crt user@client-host:sk-raft-client/application_examples/tls_program/certs/
```

To use RSA keys instead of EC keys, replace `-algorithm EC -pkeyopt ec_paramgen_curve:P-256` with `-algorithm RSA -pkeyopt rsa_keygen_bits:3072`. The other commands do not change.

## Start the server with TLS

```bash
./skraft-<version> -port 50051 \
    -tls-cert certs/server.crt -tls-key certs/server.key \
    -tls-public-key certs/client_public.pem
```

The server prints `tls=true client-key=true`. The server then refuses connections without TLS, and connections from clients that do not hold `client.key`. `-tls-public-key` also accepts `client.crt`, because the server uses only the public key in it.

## How Python uses the files

gRPC in Python cannot load a bare public key. It uses certificates, which hold the public keys. Thus the client gives:

- `server.crt` as the trusted root (`root_certificates`), to verify the server. The address in `connect()` must be in the `subjectAltName` of `server.crt`.
- `client.crt` (`certificate_chain`) and `client.key` (`private_key`), to prove to the server that the client holds the private key of `client_public.pem`.

With the `skraft` package:

```python
from skraft import SkraftFpga

client = SkraftFpga.connect(
    ip="192.168.1.50", port=50051,
    tls_server_cert="certs/server.crt",   # verify the server
    tls_cert="certs/client.crt",          # public key of the client
    tls_key="certs/client.key",           # private key of the client
)
```

`SkraftFpga.connect()` calls gRPC as shown below. Use this form only if you do not use the `skraft` package:

```python
import grpc

def read(path):
    with open(path, "rb") as f:
        return f.read()

credentials = grpc.ssl_channel_credentials(
    root_certificates=read("certs/server.crt"),
    private_key=read("certs/client.key"),
    certificate_chain=read("certs/client.crt"),
)
channel = grpc.secure_channel("192.168.1.50:50051", credentials)
```

## Requirements

- SK-RAFT server, with the FPGA board connected through JTAG.
- Python 3.9 or a later version, with the `skraft` package installed (`api/python`).
- The TLS files above, in `certs/` next to `src/`. The `.gitignore` of this folder keeps `certs/` out of Git.
- A bitstream. By default, the script uses the prebuilt `targeted_top` design of the getting-started examples. Extract `design_examples.zip` first (see [get_started/README.md](../../get_started/README.md#prebuilt-design-files)).

## Run the example

1. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP`, `SERIAL_NUMBER` and `BOARD` (or `BITSTREAM`).
2. Run the script from `src/`:

   ```bash
   cd src
   python main.py
   ```

The script prints `programmed <serial number> (<part number>) with <bitstream>`. Then it releases the device and closes the connection.

The server serves only one client. The first client that sends a request becomes the client of the server. While it is connected, the requests of all other clients fail with `the server serves only one client and another client is connected`.

When the client disconnects, the server closes the device and the session itself. This also occurs if the connection stops before the script releases the device, for example when you press Ctrl+C. The server waits until the running requests of the client end, for example a programming request. Then the next client can connect.

## Troubleshooting

If `connect()` raises `ConnectionFailedError`, do these checks:

1. The server runs, with `-tls-cert` and `-tls-key`, on the port that you set.
2. `SK_RAFT_SERVER_IP` is in the `subjectAltName` of `server.crt` (`openssl x509 -in server.crt -noout -ext subjectAltName`).
3. `server.crt` on the client is the file that the server uses, and it did not expire (`-enddate`).
4. `client.crt` holds the public key that the server got with `-tls-public-key` (step 4 on the client computer).
5. No other client is connected to the server. If one is, the error says `another client is connected`.

To test the TLS connection without Python, use `openssl s_client` from the client computer:

```bash
openssl s_client -connect 192.168.1.50:50051 -alpn h2 -tls1_2 \
    -CAfile certs/server.crt -verify_return_error -verify_ip 192.168.1.50 \
    -cert certs/client.crt -key certs/client.key -brief </dev/null
```

- Correct files: the output shows `CONNECTION ESTABLISHED` and `Verification: OK`.
- `certificate verify failed`: the client refuses the server (checks 2 and 3).
- `alert bad certificate`: the server refuses the client key (check 4).

The command uses TLS 1.2 (`-tls1_2`), because with TLS 1.3 the server refuses a client key only after `s_client` shows the connection.
