# Component injection: random flip-flop upsets in one component

This example injects upsets only into the flip-flops of one component of the design hierarchy. It uses the BRAM design of [example 4](../example4/README.md) (`brams_top`), which has several components.

A component is one or more whole levels of the net paths in the LL file. For example, the net `bscan_u3_data_uri/bscan_interface_read_write_uX/Q[12]` is inside the components `bscan_u3_data_uri` and `bscan_u3_data_uri/bscan_interface_read_write_uX`. The last level, `Q[12]`, is the net. It is not a component. A part of a name is not a component: `u3` does not select this net.

To see the components of your design, run the [component tree example](../example6/README.md) first.

## Sequence

1. The script uploads the bitstream and the LL file, and programs the FPGA. The server reads the components from the LL file when it programs the FPGA.
2. The script gets the components with `dev.components()` and finds `COMPONENT`. If the design has no such component, the script stops. If it has, the script prints the number of flip-flops in the component.
3. The script injects one upset each 0.5 s with `dev.inject_random(TargetMemory.FF, component=COMPONENT)`, until you press Enter. The server selects a random flip-flop of the component, also in its sub components.
4. The script programs the FPGA again, to clear the upsets.

For each upset, the script prints the location of the flip-flop (FAR, word and bit) and the net that the flip-flop drives. The net is always inside `COMPONENT`.

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/brams_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`. The design files are `brams_top.bit` and `brams_top.ll`. The script uploads them to the server.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `COMPONENT` | `"bscan_u3_data_uri/bscan_interface_read_write_uX"` | The full path of the component, as the component tree example prints it. The default is the BSCAN interface of the data register (USER3). |
| `INJECTION_PERIOD_S` | `0.5` | The time between two upsets, in seconds. |

## Result

The script prints one line for each upset. For example:

```
bscan_u3_data_uri/bscan_interface_read_write_uX: 77 flip-flops.
Injecting random upsets, not corrected. Press Enter to stop.
     #  FAR       WORD  BIT  NET
     1  0040041f    65   28  bscan_u3_data_uri/bscan_interface_read_write_uX/updated_data_user_reg_reg[23]_0[2]
     2  0040029f    65    3  bscan_u3_data_uri/bscan_interface_read_write_uX/Q[12]
     3  0040039f    72    2  bscan_u3_data_uri/bscan_interface_read_write_uX/Q[2]
3 upsets injected into bscan_u3_data_uri/bscan_interface_read_write_uX.
```

The number of flip-flops and the locations depend on the build of your design. The script sets the seed (`dev.configure_seed(0)`). Thus, with the same design, each run injects into the same sequence of flip-flops.

The script does not correct the upsets, and it does not stop the clock of the design during the injection. If your design runs during the injection, stop its clock first, as [example 3](../example3/README.md) does. At the end, the script programs the FPGA again to clear the upsets.

If you stop the script with Ctrl+C, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.

