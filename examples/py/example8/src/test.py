"""Walk every address through USER1 and read it back.

USER1 is the address register of the design, ten bits wide and readable as
well as writable. That makes it testable on its own: write a value, shift it
straight back out, and it should be the value that went in.

    USER1   10 bits   address register   (read/write)

The run writes every address from 0 to 1023 into it, so each of the 1024
values a ten-bit register can hold is exercised once, and each of the ten bits
is driven both high and low many times over. Anything wrong with the register
or with the path to it shows up here rather than later, when it would look
like a memory fault instead.

Ten bits do not fit in a byte, so this also exercises the two-byte shift.
A register that comes back with its top bits missing usually means the width
is wrong somewhere, in the design or in the client.

Nothing is injected and nothing is corrupted, so the run is safe to repeat.
"""

from __future__ import annotations

from skraft.datatypes import BscanPrimitive, DesignFiles, ServerPath
from skraft.exceptions import SkraftError
from skraft.skraft_fpga import SkraftFpga

SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
DEVICE = "xc7a35t"

DESIGN = "/home/embeddedcat/Documents/SolidKosmos/Products/SK_RAFT/Boards/Tests/7Series/Basys3/unittests/designs/bscan/basys3_register_odd"
BITSTREAM = ServerPath(f"{DESIGN}/tester.bit")

# The address register under test.
USER_ADDRESS = BscanPrimitive(1, 10)

# How many bad values to list before the rest are summarised.
MAX_LISTED = 16

ADDRESS_BITS = USER_ADDRESS.size_in_bits
DEPTH = 1 << ADDRESS_BITS          # 1024 values
ADDRESS_MASK = DEPTH - 1


def write_read(dev, address: int) -> int:
    """Write one address into USER1 and shift it back out."""
    dev.write_bscan(USER_ADDRESS, address)
    addr_bytes = dev.read_bscan(USER_ADDRESS) 

    print("EXCPECTED: ", address.to_bytes(2, "little").hex() , "READ BYTES: ", addr_bytes.hex())# (int.from_bytes(addr_bytes, "little") & 0x3).to_bytes(2, "big"))
    return int.from_bytes(addr_bytes, "big") & ADDRESS_MASK


def walk(dev) -> list[tuple[int, int]]:
    """Write every address in turn and return the ones that read back wrong.

    Each entry is ``(written, read)``.
    """
    print(f"Writing and reading all {DEPTH} addresses")
    bad = []
    for address in range(DEPTH):
        value = write_read(dev, address)
        if value != address:
            bad.append((address, value))
    return bad


def bit_report(bad: list[tuple[int, int]]) -> None:
    """Say which bits of the register are involved in the failures.

    A single bit failing on every value points at that bit of the register or
    its path. All of the top bits failing points at a width mismatch.
    """
    counts = [0] * ADDRESS_BITS
    for written, read in bad:
        difference = written ^ read
        for bit in range(ADDRESS_BITS):
            if (difference >> bit) & 1:
                counts[bit] += 1

    # A bit should be high in half of the values, so failing exactly that
    # often means it never comes back at all.
    print("\n  BIT  WRONG IN")
    for bit in range(ADDRESS_BITS):
        note = "   <- never survives" if counts[bit] == DEPTH // 2 else ""
        print(f"  {bit:>3}  {counts[bit]} of {DEPTH} values{note}")


def report(bad: list[tuple[int, int]]) -> None:
    """Print what came back wrong."""
    if not bad:
        print(f"All {DEPTH} addresses read back correctly.")
        return

    print(f"{len(bad)} of {DEPTH} addresses read back wrong")
    print("  WRITTEN  READ    DIFFERING BITS")
    for written, read in bad[:MAX_LISTED]:
        print(f"  {written:>7}  {read:>4}    {written ^ read:#06x}")
    if len(bad) > MAX_LISTED:
        print(f"  ... and {len(bad) - MAX_LISTED} more")

    bit_report(bad)


def main() -> None:
    print(f"USER1 address register check, {ADDRESS_BITS} bits, "
          f"{DEPTH} values")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            print(f"Connected, server version {client.version()}")
            with client.attach(DEVICE) as dev:
                dev.load(DesignFiles(bitstream=BITSTREAM))
                dev.program()
                print(f"Programmed {DEVICE}")

                bad = walk(dev)

        report(bad)
    except SkraftError as e:
        print(f"Failed: {e}")
    except KeyboardInterrupt:
        print("Interrupted")


if __name__ == "__main__":
    main()
