# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""Component injection: random flip-flop upsets in one design component.

This example injects upsets only into the flip-flops of one component of
the design hierarchy, with
``dev.inject_random(TargetMemory.FF, component=COMPONENT)``.

A component is one or more whole levels of the net paths in the LL file,
for example ``top_component/sub_component``. The server selects a random
flip-flop of that component, in all its sub components too. To find the
components of your design, run the component tree example first.

Before the injection, the script makes sure that the component exists,
with ``dev.components()``, and shows its number of flip-flops. Then the
script injects one upset every 0.5 s until you press Enter. For each
upset, the script shows the location (FAR, word, bit) and the net of the
flip-flop that the upset hit. At the end, the script programs the FPGA
again to remove all the upsets.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from skraft import (Design, FpgaComponent, SkraftError, SkraftFpga,
                    TargetMemory)

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

# The component to test: the full path of a component, as the component
# tree example shows it. This one is the BSCAN interface of the data
# register.
COMPONENT = "bscan_u3_data_uri/bscan_interface_read_write_uX"

# The time between two upsets, in seconds.
INJECTION_PERIOD_S = 0.5

# A background thread monitors the Enter key. Thus, the injection loop
# below does not wait for input. Press Enter at any time to stop.
stop = threading.Event()


def watch_for_enter() -> None:
    stop.clear()
    threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()


# Find a component by its full path in the tree of the components.
def find_component(components: list[FpgaComponent],
                   path: str) -> Optional[FpgaComponent]:
    for component in components:
        if component.path == path:
            return component
        found = find_component(component.children, path)
        if found is not None:
            return found
    return None


def main() -> None:
    print("Component injection: random flip-flop upsets in one component")
    try:
        with SkraftFpga.connect(ip=SK_RAFT_SERVER_IP,
                                port=SK_RAFT_SERVER_PORT) as client:
            with client.attach(SERIAL_NUMBER) as dev:
                # Setup the SEED for deterministic behaviour.
                dev.configure_seed(0)

                dev.uploadDesignToServer(design)
                dev.programFPGA(design)
                print(f"Programmed {SERIAL_NUMBER}.")

                # Make sure that the component exists and holds
                # flip-flops. The server reads the components from the LL
                # file when it programs the FPGA.
                component = find_component(dev.components(), COMPONENT)
                if component is None:
                    print(f"No component {COMPONENT!r} in the LL file. Run "
                          f"the component tree example to see the "
                          f"components of the design.")
                    return
                print(f"{component.path}: {component.flip_flop_count} "
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
                dev.programFPGA(design)
    except SkraftError as e:
        print(f"Component injection failed: {e}")
    except KeyboardInterrupt:
        print("Interrupted.")

    print("Component injection done.")


if __name__ == "__main__":
    main()
