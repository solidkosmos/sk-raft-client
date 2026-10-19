# BSCAN USER registers

VHDL that gives a design up to four registers on the JTAG chain of the
FPGA (USER1 to USER4), through the BSCANE2 primitive. The SK-RAFT client
reads and writes them with `read_bscan` and `write_bscan`, over the same
JTAG cable it uses for fault injection.

Works on 7-series, UltraScale and UltraScale+ (BSCANE2 exists in all of
them).

## Files

| File | Contents |
| --- | --- |
| `bscan_interface.vhd` | The component to instantiate: one USER register with a write path (JTAG to design) and a read path (design to JTAG). Uses the two files below. |
| `bscan_primitive_wrapper.vhd` | The BSCANE2 instance for one USER chain. |
| `bscan_user_register_io.vhd` | The shift registers and the small FSM that tells a read from a write. |

Add all three files to the project. `bscan_interface` instantiates the
other two with `entity work.…`, so no package is needed.

## `bscan_interface`

```vhdl
generic (
  jtag_chain : integer range 1 to 4;  -- 1 = USER1 ... 4 = USER4
  data_len_r : positive;              -- bits read by JTAG (design to JTAG)
  data_len_w : positive;              -- bits written by JTAG (JTAG to design)
  sync       : boolean := true        -- synchronize avail/ack to clk_i
);
port (
  clk_i            : in  std_ulogic;  -- design clock (for sync = true)
  tck_o, drck_o    : out std_ulogic;  -- TCK and DRCK, if you need them
  data_to_jtag_i   : in  std_ulogic_vector(data_len_r - 1 downto 0);
  data_from_jtag_o : out std_ulogic_vector(data_len_w - 1 downto 0);
  ux_avail_o       : out std_ulogic;  -- 1 after a write, until the next shift
  ux_ack_o         : out std_ulogic   -- one-cycle strobe when a read captures
);
```

One instance per USER chain. Each chain (1 to 4) can be used once in a
design.

## How a read and a write work

JTAG shifts the register LSB first. What happens at the end of the shift
decides between a read and a write:

- **Write** (`write_bscan`): Shift-DR, Exit1-DR, Update-DR. At Update-DR
  the shifted value goes to `data_from_jtag_o` and `ux_avail_o` goes to 1.
  `ux_avail_o` goes back to 0 when the next shift starts.
- **Read** (`read_bscan`): at Capture-DR the register loads
  `data_to_jtag_i` (`ux_ack_o` pulses), then shifts it out on TDO. The
  path ends through Pause-DR, not Update-DR, so `data_from_jtag_o` does not
  change: a read never writes.

## Clock domain crossing

The register runs on TCK (about 15 MHz). The design runs on its own clock.

- `sync => true`: two flip-flops synchronize `ux_avail_o` and `ux_ack_o`
  to `clk_i` (with `ASYNC_REG`).
- The data path is not synchronized. `data_from_jtag_o` changes only at
  Update-DR, so take it on the rising edge of the synchronized
  `ux_avail_o`; it is stable by then:

```vhdl
process (clk)
begin
  if rising_edge(clk) then
    avail_prev <= avail;
    if avail = '1' and avail_prev = '0' then   -- one new write
      value <= data_from_jtag;
    end if;
  end if;
end process;
```

- `data_to_jtag_i` is captured on TCK at Capture-DR. Keep it stable while
  a read can happen (for example a register that changes only when the
  design writes it).
- `sync => false` with `clk_i => '0'`: for a register that is not tied to
  a design clock, for example the clock enable below.

## Example: clock gate on USER1

USER1 stops and starts the design clock. 1 = runs, 0 = stopped (0 after
programming). `safe_clk` comes from [`safe_clk_gen`](../safe_clk_gen/README.md).

```vhdl
signal gated_clk                    : std_ulogic;
signal clk_en_jtag, clk_en_rb       : std_ulogic_vector(0 downto 0);
signal clk_en_d0, clk_en_sync       : std_ulogic := '0';

bscan_u1_clk_en : entity work.bscan_interface
  generic map (jtag_chain => 1, data_len_r => 1, data_len_w => 1,
               sync => false)
  port map (clk_i => '0', tck_o => open, drck_o => open,
            data_to_jtag_i => clk_en_rb, data_from_jtag_o => clk_en_jtag,
            ux_avail_o => open, ux_ack_o => open);

process (safe_clk)                     -- two flip-flops: TCK to safe_clk
begin
  if rising_edge(safe_clk) then
    clk_en_d0   <= clk_en_jtag(0);
    clk_en_sync <= clk_en_d0;
  end if;
end process;
clk_en_rb(0) <= clk_en_sync;           -- USER1 reads back the enable

clk_gate : BUFGCE                      -- stops its output low
  port map (O => gated_clk, CE => clk_en_sync, I => safe_clk);
```

Clock all logic you want to freeze from `gated_clk`. Use a BUFGCE (stops
low), not a BUFGCE_1, when the design has block RAMs protected by
[`bram_shadow_pass`](../bram_shadow_pass/README.md).

## XDC: the TCK clock

`bscan_interface` puts TCK on a BUFG (`tck_BUFG_inst`). Declare it as a
clock and make it asynchronous to the design clock, once per instance:

```tcl
create_clock -period 66.667 -name bscan_clk_u1 -waveform {0.000 33.333} \
    [get_pins -filter REF_PIN_NAME==O -of_objects \
        [get_cells bscan_u1_clk_en/tck_BUFG_inst]]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks sys_clk_pin] \
    -group [get_clocks bscan_clk_u1]
```

`sys_clk_pin` is the board clock in your XDC; `bscan_u1_clk_en` is the
instance name.

## Python (SK-RAFT client)

```python
from skraft import BscanPrimitive

USER_CLK_EN = BscanPrimitive(1, 1)     # USER1, 1 bit
USER_DATA = BscanPrimitive(3, 32)      # USER3, 32 bits

dev.write_bscan(USER_CLK_EN, 1)        # start the clock
dev.write_bscan(USER_DATA, 0x1234)     # write
value = int.from_bytes(dev.read_bscan(USER_DATA), "big")   # read
```

`BscanPrimitive(chain, length)` takes one length. Give `data_len_r` and
`data_len_w` the same value for a register you both read and write.

## Notes

- Vivado debug cores (ILA, VIO) use a BSCANE2 for their debug hub, by
  default on USER1. Move the debug hub to a free chain (or do not use that
  chain here) if you use both.
- A write is complete only after Update-DR. A read never changes the
  design side of the register.
