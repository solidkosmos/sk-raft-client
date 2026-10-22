# Component tree: the components of a design

This example shows the components of the design hierarchy as a tree, with the number of flip-flops in each component. It uses the BRAM design of [example 4](../example4/README.md) (`brams_top`), which has several components.

Use this example to find the components of your design before you inject into one of them. The [component injection example](../example7/README.md) shows the injection.

## Sequence

1. The script uploads the bitstream and the LL file, and programs the FPGA. The server reads the LL file when it programs the FPGA. Thus, `dev.components()` needs a programmed design.
2. The script gets the components with `dev.components()`. The result is a list of the top-level components. Each component holds its sub components.
3. The script prints each top-level component with `print(component)`. This shows the component and all its sub components as a tree.
4. The script prints the full path of each component, with its number of flip-flops.

The script does not inject upsets.

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/brams_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`. The design files are `brams_top.bit` and `brams_top.ll`. The script uploads them to the server.
3. Run the script:

```bash
cd src
python main.py
```

## Result

The script prints the tree, and then the full paths. For example:

```
5 top-level components:

bscan_u1_clk_en (7 flip-flops)
`-- bscan_interface_read_write_uX (7 flip-flops)
bscan_u2_addr_uri (55 flip-flops)
`-- bscan_interface_read_write_uX (53 flip-flops)
bscan_u3_data_uri (79 flip-flops)
`-- bscan_interface_read_write_uX (77 flip-flops)
bscan_u4_ecc_read_en (10 flip-flops)
`-- bscan_interface_read_write_uX (8 flip-flops)
safe_pll (1 flip-flop)

Component paths for inject_random(TargetMemory.FF, component=<path>):

  bscan_u1_clk_en                                          7 flip-flops
  bscan_u1_clk_en/bscan_interface_read_write_uX            7 flip-flops
  bscan_u2_addr_uri                                       55 flip-flops
  bscan_u2_addr_uri/bscan_interface_read_write_uX         53 flip-flops
  bscan_u3_data_uri                                       79 flip-flops
  bscan_u3_data_uri/bscan_interface_read_write_uX         77 flip-flops
  bscan_u4_ecc_read_en                                    10 flip-flops
  bscan_u4_ecc_read_en/bscan_interface_read_write_uX       8 flip-flops
  safe_pll                                                 1 flip-flop
```

In `brams_top`, the four BSCAN components are the interfaces of the registers USER1 to USER4 (clock enable, address, data and ECC enable). `safe_pll` is the clock generator. The number of flip-flops depends on the build of your design.

If no flip-flop of the LL file is inside a component, the script prints a message and stops.

The numbers come from the LL file. If you exclude pblocks or frames, `dev.inject_random()` can select fewer flip-flops of a component than the tree shows.

