let grpc = require('@grpc/grpc-js');
let protoLoader = require('@grpc/proto-loader');

let PROTO_PATH = __dirname + '/skraft_client.proto';
let packageDefinition = protoLoader.loadSync(
    PROTO_PATH,
    {keepCase: true,
        longs: String,
        enums: String,
        defaults: true,
        oneofs: true
    });

let skRaftApi = grpc.loadPackageDefinition(packageDefinition).proto;

class SkRaftFpga {
    conn: any; /* */
    grpcClient: any;
    ip: string;
    port: number;

    constructor(ip: string, port: number) {
        this.ip = ip;
        this.port = port;
    }

    establishConnection() {
        let target: string = `${this.ip}:${this.port}`;

        this.grpcClient = new skRaftApi.SKRaftFpga(target, grpc.credentials.createInsecure());

        this.grpcClient.waitForReady(Date.now() + 5000, (err: Error) => {
            if (err) {
                return new Error("Failed to connect to SK-RAFT server: " + err.message);
            }
        })
    }

    fpgaConnect(devicePartNumber: string, programmerPartNumber: string) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaConnect({devicePartNumber: devicePartNumber,
                                         programmerPartNumber: programmerPartNumber}, (err: Error, result: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(result);
                }
            })
        })
    }

    fpgaClose() {
        return new Promise((_, reject) => {
            this.grpcClient.fpgaClose({}, (err: Error) => {
                if (err) {
                    reject(err);
                }
            });
        })
    }

    fpgaSetRbdFilePath(rbdPath: string) {
        return new Promise((_, reject) => {
            this.grpcClient.fpgaSetRbdFilePath({path: rbdPath}, (err: Error) => {
                if (err) {
                    reject(err);
                }
            })
        })
    }

    fpgaSetMsdFilePath(msdPath: string) {
        return new Promise((_, reject) => {
            this.grpcClient.fpgaSetMsdFilePath({path: msdPath}, (err: Error) => {
                if (err) {
                    reject(err);
                }
            })
        })
    }

    fpgaSetEbdFilePath(ebdPath: string) {
        return new Promise((_, reject) => {
            this.grpcClient.fpgaSetEbdFilePath({path: ebdPath}, (err: Error) => {
                if (err) {
                    reject(err);
                }
            })
        })
    }

    fpgaSetBitFilePath(bitPath: string) {
        return new Promise((_, reject) => {
            this.grpcClient.fpgaSetBitFilePath({path: bitPath}, (err: Error) => {
                if (err) {
                    reject(err);
                }
            })
        })
    }

    fpgaWriteBscan(userRegisterId: number, value: Uint8Array, usefulBits: number) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaWriteBscan({
                userRegisterId: userRegisterId,
                value: value,
                usefulBits: usefulBits
            }, (err: Error, result: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(result);
                }
            })
        })
    }

    fpgaBitFlip(far: number, wordIndex: number, bitIndex: number,
                isFlipFlop: boolean, isLutRam: boolean, isBram: boolean) {
        return new Promise((resolve, reject) => {

        })
    }

    fpgaProgram() {}

}

let test: SkRaftFpga = new SkRaftFpga("127.0.0.1", 50052)

test.establishConnection()