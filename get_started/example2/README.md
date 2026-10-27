# Example 2: BSCAN-controlled adders, simplex against TMR, single-bit upsets

This example programs a bitstream. Then it compares a simplex adder with a triplicated (TMR) adder. Each adder is in its own pblock.

The two adders use one operand register (USER1). Each adder has its own result register: USER2 for the simplex adder and USER3 for the TMR adder.

![Block diagram of bscan_adder_top. BSCAN USER1 sends the operands to a simplex adder and to three adders with a voter (TMR). Each group is in its own pblock. USER2 and USER3 return the results over JTAG.](images/example2_bscan_adder_top_abstract.svg)

Each trial does these steps:

1. It injects one random essential bit into each pblock.
2. It sends 100 random operand pairs through the two adders.
3. It marks an adder as failed if one or more of its results are wrong.
4. It flips the two bits again to correct the upsets.

The trials continue until you press Enter.

## The calls of the example

| Call | Use in the example |
| --- | --- |
| `SkraftFpga.connect(ip=..., port=...)`, `client.attach(SERIAL_NUMBER)` | Connect to the SK-RAFT server and attach to the device, in `with` statements that release the device and close the connection. |
| `Design(bit, ebd, xdc)`, `dev.uploadDesignToServer(design)`, `dev.programFPGA(design)` | Give the design files, upload them to the server and program the FPGA. |
| `dev.configure_seed(0)` | Set the seed of the random injections. The same seed gives the same upsets in each run. |
| `BscanPrimitive(user, length)`, `dev.write_bscan(primitive, value)`, `dev.read_bscan(primitive)` | Write the operands through USER1, and read the results of the simplex adder (USER2) and of the TMR adder (USER3). |
| `dev.bit_count(TargetMemory.ESSENTIAL_CRAM, pblock=...)` | Get the number of essential bits of each adder pblock. |
| `dev.inject_random(TargetMemory.ESSENTIAL_CRAM, pblock=...)` | Inject one upset into a random essential bit of each adder pblock. |
| `dev.inject_at(far, word, bit, TargetMemory.CRAM)` | Flip the two bits again after the trial, to correct the upsets. |

## Run the example

1. Make sure that the design files are in `hw/design_examples/<board>/bscan_adder_top/`, and set `BOARD` in `src/main.py` to your board. Refer to [Build a design](../README.md#build-a-design) or [Prebuilt design files](../README.md#prebuilt-design-files).
2. At the top of `src/main.py`, set `SK_RAFT_SERVER_IP` and `SERIAL_NUMBER`.
3. Run the script:

```bash
cd src
python main.py
```

| Constant | Default | Description |
| --- | --- | --- |
| `design` | `bscan_adder_top.{bit,ebd}` + XDC | The design files. The script uploads them to the server. |
| `PBLOCK_SIMPLEX` / `PBLOCK_TMR` | `"pblock_sngl_add"` / `"pblock_tmr_add"` | The two pblocks for the test, as the XDC file names them. |
| `OP_LEN` | `4` | The operand width. It must be equal to the `op_len` generic of the design. |

## Result

Sample output of a run on a Basys 3 (shortened). The frame addresses, the bit counts and the error counts depend on the board, the build and the seed.

```
Programmed 210183BFD452A.
Number of Essential Bits in:
Simplex Adder = 595 | TMR Adder = 3374
Press Enter to move on.
--------------------------------------------------------------------------------
Vulnerability Factor (VF) = observable errors / injected faults
# of trials = 156  ||  Simplex Correct VF = 66/156 (42.31%)  |  TMR Correct VF = 5/156 (3.21%)
66 simplex, 5 tmr errors in 156 trials.
Final Simplex Adder VF = 66/156 (42.31%)
Final TMR Adder VF     = 5/156 (3.21%)
Example 2 done.
```

First, the script prints the number of essential bits in each pblock. Then it updates one status line during the trials. The status line shows:

- The number of trials.
- The result of each adder for the last trial: green "Correct" or red "Wrong".
- The vulnerability factor (VF) of each adder: the fraction of trials in which the adder failed.

When you stop the script, it prints the final error counts and the VFs.

Each trial corrects its bits immediately after the check. Thus the configuration of the device is clean at the end. If you stop the script with Ctrl+C during a trial, a bit can stay flipped. In that case, program the FPGA again before you do other work.
