# Component injection: the components of a design, and random flip-flop upsets in one component

This example shows the components of the design hierarchy as a tree, with the number of flip-flops in each component. Then it injects upsets only into the flip-flops of one of these components, and the LEDs show the effect. It uses the design of [example 2](../example2/README.md) (`bscan_adder_top`)

A component is one or more whole levels of the net paths in the LL file. For example, the net `bscan_u1_operands/bscan_interface_read_write_uX/data_user_reg_data_in[2]` is inside the component `bscan_u1_operands`. The last level, `data_user_reg_data_in[2]`, is the net. It is not a component. A part of a name is not a component: `bscan_u1` does not select this net.

### Example of the hierarchy

Using `bscan_adder_top` as an example.

```
3 top-level components:

bscan_u1_operands (20 flip-flops)
`-- bscan_interface_read_write_uX (20 flip-flops)
bscan_u2_simplex_adder_res (5 flip-flops)
`-- bscan_interface_read_write_uX (5 flip-flops)
bscan_u3_tmr_adder_res (5 flip-flops)
`-- bscan_interface_read_write_uX (5 flip-flops)
```

## Sequence

1. The script uploads the bitstream and the LL file, and programs the FPGA. The server reads the LL file when it programs the FPGA. Thus, `dev.components()` needs a programmed design.
2. **Part 1.** The script gets the components with `dev.components()`. The result is a list of the top-level components. Each component holds its sub components.
3. The script prints each top-level component with `print(component)`. This shows the component and all its sub components as a tree. Then the script prints the full path of each component, with its number of flip-flops.
4. **Part 2.** The script finds `COMPONENT` (`bscan_u1_operands`) in the components. If the design has no such component, the script stops. If it has, the script prints the number of flip-flops in the component.
5. The script injects one upset each 0.5 s with `dev.inject_random(TargetMemory.FF, component=COMPONENT)`, until you press Enter. The server selects a random flip-flop of the component, also in its sub components.
6. The script programs the FPGA again, to clear the upsets.

For each upset, the script prints the location of the flip-flop (FAR, word and bit) and the net that the flip-flop drives. The net is always inside `COMPONENT`.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.attach(SERIAL_NUMBER)` | Connect to the SK-RAFT server and attach to the device, in `with` statements that release the device and close the connection. |
| `Design(bit, ll)`, `dev.uploadDesignToServer(design)`, `dev.programFPGA(design)` | Give the design files, upload them to the server and program the FPGA. |
| `dev.configure_seed(0)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `dev.components()` | Part 1: get the components of the design as a tree, with the number of flip-flops in each component. |
| `dev.inject_random(TargetMemory.FF, component=COMPONENT)` | Part 2: inject one upset into a random flip-flop of one component. The report gives the net of the flip-flop (`net_name`). |

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/bscan_adder_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`. The design files are `bscan_adder_top.bit` and `bscan_adder_top.ll`. The script uploads them to the server.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `COMPONENT` | `"bscan_u1_operands"` | The full path of the component, as part 1 prints it. |
| `INJECTION_PERIOD_S` | `0.5` | The time between two upsets, in seconds. |

## Result

The script prints the tree, the full paths, and then one line for each upset: the number of the upset, the FAR, the word, the bit and the net. In `targeted_top`, the top-level components are `clk_gen_inst` (the clock generator), `fast_heartbeat` and `slow_heartbeat`.

The number of flip-flops and the locations depend on the build of your design. The numbers come from the LL file. If you exclude pblocks or frames, `dev.inject_random()` can select fewer flip-flops of a component than the tree shows. The script sets the seed (`dev.configure_seed(0)`). Thus, with the same design, each run injects into the same sequence of flip-flops.

If no flip-flop of the LL file is inside a component, the script prints a message and stops.

The script does not correct the upsets, and it does not stop the clock of the design during the injection. If your design must not run during the injection, stop its clock first, as [example 3](../example3/README.md) does. At the end, the script programs the FPGA again to clear the upsets.

If you stop the script with Ctrl+C, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.