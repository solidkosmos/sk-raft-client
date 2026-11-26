# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Component injection: the components of a design, and random flip-flop
upsets in one component.

This example has two parts:

1. It shows the components of the design hierarchy, with
   ``dev.components()``. The server finds the components in the nets of
   the flip-flops in the LL file. The server reads the LL file when it
   programs the FPGA. Thus, the script uploads the design and programs
   the FPGA first. The script prints each top-level component as a tree,
   with its sub components and the number of flip-flops in each
   component. Then the script prints the full path of each component.
2. It injects upsets only into the flip-flops of one of these components,
   with ``dev.inject_random(TargetMemory.FF, component=COMPONENT)``. The
   server selects a random flip-flop of that component, in all its sub
   components too. The script injects one upset every 0.5 s until you
   press Enter. For each upset, the script shows the location (FAR, word,
   bit) and the net of the flip-flop that the upset hit. At the end, the
   script programs the FPGA again to remove all the upsets.

The design is bscan_adder_top, the design of example 2. Its top-level
components are its three BSCAN registers. The script injects into
bscan_u1_operands, the register (USER1) with the operands of the two
adders.

A component is one or more whole levels of the net paths in the LL file,
for example ``top_component/sub_component``.
"""

from __future__ import annotations

import threading
import time
from typing import Iterator, Optional

from skraft import (Design, FpgaComponent, SkraftError, SkraftFpga,
                    TargetMemory)

# --------------------------------------------------------------------------- #
# Configuration. Set these values for your setup.
# --------------------------------------------------------------------------- #
SK_RAFT_SERVER_IP = "127.0.0.1"
SK_RAFT_SERVER_PORT = 50051

# The design: bscan_adder_top, the design of example 2.
# The script gives two files:
#   The bitstream (.bit): to program the device.
#   The LL file (.ll): to find the flip-flops and the nets that they drive.
# dev.upload_design_to_server() sends the files to the server. The client sends
# only the file name of each path, not the directory.
#
# BOARD is the board of your target device: "basys3" or "zedboard", or
# the name of your own board (see hw/README.md). The script reads the
# design files from hw/design_examples/<BOARD>/bscan_adder_top/. Extract
# design_examples.zip there, or build the design with create_project.tcl.
# The paths are relative to src/. Run the script from that folder.
BOARD = "basys3"
DESIGN_DIR = f"../../hw/design_examples/{BOARD}/bscan_adder_top"

design = Design(
    bit=f"{DESIGN_DIR}/bscan_adder_top.bit",
    ll=f"{DESIGN_DIR}/bscan_adder_top.ll",
)

# The component to test: the full path of a component, as part 1 shows
# it. This one is the BSCAN register USER1, the operands of the two adders.
COMPONENT = "bscan_u1_operands"

# The time between two upsets, in seconds.
INJECTION_PERIOD_S = 0.5

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# Go through all the components of the tree, each component before its
# sub components.
def all_components(
        components: list[FpgaComponent]) -> Iterator[FpgaComponent]:
    for component in components:
        yield component
        yield from all_components(component.children)


# Find a component by its full path in the tree of the components.
def find_component(components: list[FpgaComponent],
                   path: str) -> Optional[FpgaComponent]:
    for component in all_components(components):
        if component.path == path:
            return component
    return None


def main() -> int:
    print("Example 5: the components of the design, and random flip-flop "
          "upsets in one component")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            # Select the first detected device.
            serial_number = client.get_devices()[0].serial_number

            with client.attach(serial_number) as dev:
                # Setup the SEED for deterministic behaviour.
                dev.configure_seed(0)

                dev.upload_design_to_server(design)
                dev.program_fpga(design)
                print(f"Programmed {serial_number}.")

                # Part 1. SK-RAFT: get the tree of the components.
                components = dev.components()
                if not components:
                    print("No flip-flop of the LL file is inside a "
                          "component. The design has its flip-flops at "
                          "the top level only.")
                    return 1

                # print() shows a component and all its sub components.
                print(f"\n{len(components)} top-level components:\n")
                for component in components:
                    print(component)

                # The full paths, to copy into COMPONENT.
                print("\nComponent paths for "
                      "inject_random(TargetMemory.FF, component=<path>):\n")
                width = max(len(component.path)
                            for component in all_components(components))
                for component in all_components(components):
                    count = component.flip_flop_count
                    unit = "flip-flop" if count == 1 else "flip-flops"
                    print(f"  {component.path:<{width}}  {count:>6} {unit}")

                # Part 2. Make sure that the component exists and holds
                # flip-flops.
                component = find_component(components, COMPONENT)
                if component is None:
                    print(f"\nNo component {COMPONENT!r} in the LL file. "
                          f"Set COMPONENT to one of the paths above.")
                    return 1
                print(f"\n{component.path}: {component.flip_flop_count} "
                      f"flip-flops.")

                print("Injecting random upsets, not corrected. Press Enter "
                      "to stop.")
                print("     #  FAR       WORD  BIT  NET")
                watch_for_enter()

                n = 0
                while not stop.is_set():
                    # Injection guideline (application memory): each upset
                    # is a readback-modify-writeback of full frames. If your
                    # design runs, stop its clock during the injection, as
                    # example 3 does.
                    # SK-RAFT: flip one flip-flop bit of the component.
                    report = dev.inject_random(TargetMemory.FF,
                                               component=COMPONENT)
                    # net_name is the net that the flip-flop drives, from
                    # the LL file. It is always inside COMPONENT.
                    print(f"{n + 1:>6}  {report.far:08x}  "
                          f"{report.word_index:>4}  {report.bit_index:>3}  "
                          f"{report.net_name}")
                    n += 1
                    # Wait to control the number of injections.
                    time.sleep(INJECTION_PERIOD_S)

                print(f"{n} upsets injected into {COMPONENT}.")

                print("Re-programming to clear the device.")
                dev.program_fpga(design)
    except SkraftError as e:
        print(f"Example 5 failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130

    print("\nExample 5 done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
