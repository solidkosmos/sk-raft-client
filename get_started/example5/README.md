# Component injection: the components of a design, and random flip-flop upsets in one component

This example shows the components of the design hierarchy as a tree, with the number of flip-flops in each component. Then it injects upsets only into the flip-flops of one of these components, and the LEDs show the effect. It uses the design of [example 1](../example1/README.md) (`targeted_top`): the two heartbeats, `slow_heartbeat` and `fast_heartbeat`, are components, and each heartbeat drives an LED.

A component is one or more whole levels of the net paths in the LL file. For example, the net `slow_heartbeat/heartbeat_count_reg[26]` is inside the component `slow_heartbeat`. The last level, `heartbeat_count_reg[26]`, is the net. It is not a component. A part of a name is not a component: `slow` does not select this net.

## Sequence

1. The script uploads the bitstream and the LL file, and programs the FPGA. The server reads the LL file when it programs the FPGA. Thus, `dev.components()` needs a programmed design.
2. **Part 1.** The script gets the components with `dev.components()`. The result is a list of the top-level components. Each component holds its sub components.
3. The script prints each top-level component with `print(component)`. This shows the component and all its sub components as a tree. Then the script prints the full path of each component, with its number of flip-flops.
4. **Part 2.** The script finds `COMPONENT` (`slow_heartbeat`) in the components. If the design has no such component, the script stops. If it has, the script prints the number of flip-flops in the component.
5. The script injects one upset each 0.5 s with `dev.inject_random(TargetMemory.FF, component=COMPONENT)`, until you press Enter. The server selects a random flip-flop of the component, also in its sub components.
6. The script programs the FPGA again, to clear the upsets.

For each upset, the script prints the location of the flip-flop (FAR, word and bit) and the net that the flip-flop drives. The net is always inside `COMPONENT`.

## The LEDs

The slow heartbeat toggles its LED every 1 s, the fast heartbeat every 0.25 s. On the Basys 3 and the ZedBoard, LD1 is the slow LED and LD0 is the fast LED.

During part 2, only the slow LED changes. The fast LED blinks as before, because the upsets stay inside `slow_heartbeat`. The net in each line tells you which flip-flop the upset hit:

- `slow_heartbeat/data_o_OBUF[0]`: the output flip-flop. The slow LED changes state at once.
- `slow_heartbeat/heartbeat_count_reg[N]` with a high `N`: a high bit of the counter. The slow LED toggles too early, or stays on or off for longer.
- `slow_heartbeat/heartbeat_count_reg[N]` with a low `N`: a low bit of the counter. The toggle moves by less than you can see.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.attach(SERIAL_NUMBER)` | Connect to the SK-RAFT server and attach to the device, in `with` statements that release the device and close the connection. |
| `Design(bit, ll)`, `dev.uploadDesignToServer(design)`, `dev.programFPGA(design)` | Give the design files, upload them to the server and program the FPGA. |
| `dev.configure_seed(0)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `dev.components()` | Part 1: get the components of the design as a tree, with the number of flip-flops in each component. |
| `dev.inject_random(TargetMemory.FF, component=COMPONENT)` | Part 2: inject one upset into a random flip-flop of one component. The report gives the net of the flip-flop (`net_name`). |

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/targeted_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`. The design files are `targeted_top.bit` and `targeted_top.ll`. The script uploads them to the server.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `COMPONENT` | `"slow_heartbeat"` | The full path of the component, as part 1 prints it. Set it to `"fast_heartbeat"` to inject into the fast heartbeat. |
| `INJECTION_PERIOD_S` | `0.5` | The time between two upsets, in seconds. |

## Result

The script prints the tree, the full paths, and then one line for each upset: the number of the upset, the FAR, the word, the bit and the net. In `targeted_top`, the top-level components are `clk_gen_inst` (the clock generator), `fast_heartbeat` and `slow_heartbeat`.

The number of flip-flops and the locations depend on the build of your design. The numbers come from the LL file. If you exclude pblocks or frames, `dev.inject_random()` can select fewer flip-flops of a component than the tree shows. The script sets the seed (`dev.configure_seed(0)`). Thus, with the same design, each run injects into the same sequence of flip-flops.

If no flip-flop of the LL file is inside a component, the script prints a message and stops.

The script does not correct the upsets, and it does not stop the clock of the design during the injection. If your design must not run during the injection, stop its clock first, as [example 3](../example3/README.md) does. At the end, the script programs the FPGA again to clear the upsets.

If you stop the script with Ctrl+C, the configuration of the device can stay incorrect. In that case, program the FPGA again before you do other work.
