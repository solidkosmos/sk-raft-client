# Safe clock generator (`clk_gen_wrapper`)

A PLL that makes the design clock from the board clock, for 7-series,
UltraScale and UltraScale+, and keeps the output off until the PLL is
locked and stable ("safe startup").

## What it does

- Instantiates the native PLL of the family: `PLLE2_BASE` (7-series),
  `PLLE3_BASE` (UltraScale) or `PLLE4_BASE` (UltraScale+).
- Calculates the PLL settings (DIVCLK_DIVIDE, CLKFBOUT_MULT,
  CLKOUT0_DIVIDE) at elaboration, inside the VCO and PFD ranges of the
  family, and picks the setting closest to the requested frequency. No
  Clocking Wizard IP is needed.
- Sends LOCKED through an 8-stage shift register, and enables the output
  BUFGCE only after that. The design never sees the clock before the PLL
  is stable (the same behaviour as SAFE_STARTUP in the Clocking Wizard).

## Interface

```vhdl
generic (
  g_family          : string := "7SERIES";  -- or "ULTRASCALE", "ULTRASCALEPLUS"
  g_clkin_period_ns : real   := 10.0;       -- input clock period
  g_clkout_freq_mhz : real   := 0.0         -- output frequency, 0.0 = same as input
);
port (
  clk_i    : in  std_ulogic;  -- board clock
  clk_o    : out std_ulogic;  -- design clock (on a BUFGCE)
  locked_o : out std_ulogic   -- 1 when clk_o runs
);
```

## Usage

```vhdl
safe_clk_gen : entity work.clk_gen_wrapper
  generic map (
    g_family          => "7SERIES",
    g_clkin_period_ns => 10.0,     -- 100 MHz board clock
    g_clkout_freq_mhz => 70.0      -- 70 MHz design clock
  )
  port map (clk_i => clk_i, clk_o => safe_clk, locked_o => open);
```

At elaboration the wrapper reports the setting it chose (a note that
starts with `clk_gen_wrapper: family=`; for 100 MHz in and 70 MHz out it
is D=1, M=14, O=20, exactly 70 MHz). If the
closest setting is more than 0.1 % from the request, it reports a warning
with the real frequency. Use the real frequency in the rest of the design
(for example a CPU clock frequency generic).

Constrain only the input clock in the XDC (`create_clock` on `clk_i`).
Vivado derives the output clock from the PLL.

## Using it with SK-RAFT

`safe_clk` is the clock that a BSCAN-controlled clock gate stops during an
injection: `safe_clk` into a BUFGCE whose CE is a USER register. The
[`bscan` README](../bscan/README.md#example-clock-gate-on-user1) has the
VHDL, the XDC and the Python calls.

## Notes

- The VCO and PFD limits in the wrapper are for the slowest speed grade of
  each family. Check the PLL switching characteristics in the data sheet
  of your part if you need a setting at the edge of the range.
- If no legal setting exists for the input clock, elaboration stops with
  an assertion that names the family and the input frequency.
- The PLL has no reset input (RST tied low). It locks after configuration.
