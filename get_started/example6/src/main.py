# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Component tree: show the components of a design.

This example shows the components of the design hierarchy, with
``dev.components()``. The server finds the components in the nets of
the flip-flops in the LL file. The server reads the LL file when it
programs the FPGA. Thus, the script uploads the design and programs the
FPGA first.

The script prints each top-level component as a tree, with its sub
components and the number of flip-flops in each component. Then the
script prints the full path of each component. Give one of these paths
to ``dev.inject_random(TargetMemory.FF, component=<path>)`` to inject
upsets only into the flip-flops of that component. The script does not
inject upsets.
"""

from __future__ import annotations

from typing import Iterator

from skraft import Design, FpgaComponent, SkraftError, SkraftFpga

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051
# If you do not know the serial number of your target device,
# use the get_devices() call to find it.
SERIAL_NUMBER = "210183BFD452A"

# The design: the BRAM design of example 4, which has several components.
# The script gives two files:
#   The bitstream (.bit): to program the device.
#   The LL file (.ll): to find the flip-flops and the nets that they drive.
# uploadDesignToServer() sends the files to the server. The client sends
# only the file name of each path, not the directory.
#
# BOARD is the board of your target device: "basys3" or "zedboard", or
# the name of your own board (see hw/README.md). The script reads the
# design files from hw/design_examples/<BOARD>/brams_top/. Extract
# design_examples.zip there, or build the design with create_project.tcl.
# The paths are relative to src/. Run the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/brams_top"

design = Design(
    bit=f"{DESIGN_DIR}/brams_top.bit",
    ll=f"{DESIGN_DIR}/brams_top.ll",
)


# Go through all the components of the tree, each component before its
# sub components.
def all_components(
        components: list[FpgaComponent]) -> Iterator[FpgaComponent]:
    for component in components:
        yield component
        yield from all_components(component.children)


def main() -> None:
    print("Component tree: the components of the design")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"Programmed {SERIAL_NUMBER}.")

                # SK-RAFT: get the tree of the components.
                components = dev.components()
                if not components:
                    print("No flip-flop of the LL file is inside a "
                          "component. The design has its flip-flops at "
                          "the top level only.")
                    return

                # print() shows a component and all its sub components.
                print(f"\n{len(components)} top-level components:\n")
                for component in components:
                    print(component)

                # The full paths, to copy into component=<path>.
                print("\nComponent paths for "
                      "inject_random(TargetMemory.FF, component=<path>):\n")
                width = max(len(component.path)
                            for component in all_components(components))
                for component in all_components(components):
                    count = component.flip_flop_count
                    unit = "flip-flop" if count == 1 else "flip-flops"
                    print(f"  {component.path:<{width}}  {count:>6} {unit}")
    except SkraftError as e:
        print(f"Component tree failed: {e}")
    except KeyboardInterrupt:
        print("Interrupted.")

    print("\nComponent tree done.")


if __name__ == "__main__":
    main()
