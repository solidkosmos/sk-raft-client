# SK-RAFT Protocol Buffers definition

The `sk_raft.proto` file in this folder defines the full SK-RAFT gRPC API: its services, methods and messages.

You can use it to generate a client for SK-RAFT in any language that gRPC supports, such as C++, C#, Go, Java, Node.js or Python. For example, in Python:

```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. sk_raft.proto
```

For setup instructions and guides for other languages, see the gRPC documentation: https://grpc.io/docs/
