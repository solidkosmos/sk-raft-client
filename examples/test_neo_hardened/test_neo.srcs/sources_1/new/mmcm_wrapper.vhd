----------------------------------------------------------------------------------
-- mmcm_wrapper.vhd
-- Direct MMCME2_BASE instantiation, replacing the Clocking Wizard IP (clk_wiz_0).
-- UNISIM primitive -- ships identically with every Vivado release for 7-series
-- parts, so this is version-agnostic where the IP wasn't.
----------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity mmcm_wrapper is
  generic (
    CLKIN1_PERIOD    : real := 10.0;   -- 100MHz input (board clock)
    CLKFBOUT_MULT_F  : real := 10.0;   -- VCO = CLKIN1 * MULT_F = 1000MHz
    CLKOUT0_DIVIDE_F : real := 10.0    -- CLKOUT0 = VCO / DIVIDE_F = 100MHz
  );
  port (
    clk_in1  : in  std_ulogic;
    clk_out1 : out std_ulogic
  );
end entity mmcm_wrapper;

architecture Structural of mmcm_wrapper is
  signal clkfb, clkfb_buf     : std_ulogic;
  signal clkout0, clkout0_buf : std_ulogic;
  signal locked_int           : std_ulogic;
begin

  MMCME2_BASE_inst : MMCME2_BASE
    generic map (
      BANDWIDTH          => "OPTIMIZED",
      CLKFBOUT_MULT_F    => CLKFBOUT_MULT_F,
      CLKFBOUT_PHASE     => 0.0,
      CLKIN1_PERIOD      => CLKIN1_PERIOD,
      CLKOUT0_DIVIDE_F   => CLKOUT0_DIVIDE_F,
      CLKOUT0_DUTY_CYCLE => 0.5,
      CLKOUT0_PHASE      => 0.0,
      CLKOUT4_CASCADE    => FALSE,
      DIVCLK_DIVIDE      => 1,
      REF_JITTER1        => 0.0,
      STARTUP_WAIT       => FALSE
    )
    port map (
      CLKIN1   => clk_in1,
      CLKFBIN  => clkfb_buf,
      CLKFBOUT => clkfb,
      CLKOUT0  => clkout0,
      LOCKED   => locked_int,
      PWRDWN   => '0',
      RST      => '0'
    );

  -- Feedback path must be buffered through a BUFG before returning to CLKFBIN
  BUFG_fb : BUFG
    port map ( I => clkfb, O => clkfb_buf );

  -- Every MMCM output must be buffered through a BUFG before use in fabric
  BUFG_out0 : BUFG
    port map ( I => clkout0, O => clkout0_buf );

  clk_out1 <= clkout0_buf;

end architecture Structural;
