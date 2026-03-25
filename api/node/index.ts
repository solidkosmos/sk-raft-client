import path = require("node:path");
let grpc = require('@grpc/grpc-js');
let protoLoader = require('@grpc/proto-loader');

let PROTO_PATH = path.resolve(
    __dirname,
    "../../",
    "global",
    "proto",
    "skraft_client.proto"
)

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
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaClose({}, (err: Error, response: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(response);
                }
            });
        })
    }

    fpgaSetRbdFilePath(rbdPath: string) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaSetRbdFilePath({path: rbdPath}, (err: Error, response: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(response);
                }
            })
        })
    }

    fpgaSetMsdFilePath(msdPath: string) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaSetMsdFilePath({path: msdPath}, (err: Error, response: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(response);
                }
            })
        })
    }

    fpgaSetEbdFilePath(ebdPath: string) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaSetEbdFilePath({path: ebdPath}, (err: Error, response: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(response);
                }
            })
        })
    }

    fpgaSetBitFilePath(bitPath: string) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaSetBitFilePath({path: bitPath}, (err: Error, response: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(response);
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
                    resolve(result.value);
                }
            })
        })
    }

    fpgaBitFlip(far: number, wordIndex: number, bitIndex: number,
                isFlipFlop: boolean, isLutRam: boolean, isBram: boolean) {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaBitFlip({
                frameAddress: far,
                wordIndex: wordIndex,
                bitIndex: bitIndex,
                isFlipFlop: isFlipFlop,
                isLutRam: isLutRam,
                isBram: isBram
            }, (err: Error, result: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(result);
                }
            })
        })
    }

    fpgaProgram() {
        return new Promise((resolve, reject) => {
            this.grpcClient.fpgaProgram({}, (err: Error, response: any) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(response);
                }
            })
        })
    }
}

module.exports = { SkRaftFpga };
