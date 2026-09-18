----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: clk_gen_wrapper
-- Description: Portable, family-selecting PLL passthrough wrapper (7-series / UltraScale / UltraScale+).
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Portable, family-selecting, free-running PLL passthrough wrapper.
-- Auto-computes CLKFBOUT_MULT from g_clkin_period_ns alone (VCO range
-- lookup per family), instantiates the correct native PLL primitive via
-- generate, and outputs a clock at the same frequency as the input.
-- No reset port, no locked output -- intentionally minimal.
--
-- For real synthesis: replace the three `component ... end component;`
-- declarations below with:
--   library UNISIM;
--   use UNISIM.VComponents.all;
-- (the component stubs exist only so this elaborates without UNISIM,
-- e.g. under GHDL for simulation/verification).

entity clk_gen_wrapper is
  Generic (
    g_family          : string := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_clkin_period_ns : real    := 10.0       -- input clock period, ns
  );
  Port (
    clk_i  : in  std_ulogic;
    clk_o  : out std_ulogic;
    locked_o : out std_ulogic
  );
end clk_gen_wrapper;

architecture Structure of clk_gen_wrapper is

    component PLLE2_BASE is
      generic ( CLKFBOUT_MULT : integer := 8; CLKIN1_PERIOD : real := 10.0;
                CLKOUT0_DIVIDE : integer := 8; DIVCLK_DIVIDE : integer := 1;
                STARTUP_WAIT : string := "FALSE" );
      port ( CLKFBIN : in std_ulogic; CLKFBOUT : out std_ulogic; CLKIN1 : in std_ulogic;
             CLKOUT0 : out std_ulogic; LOCKED : out std_ulogic; PWRDWN : in std_ulogic; RST : in std_ulogic );
    end component;

    component PLLE3_BASE is
      generic ( CLKFBOUT_MULT : integer := 8; CLKIN_PERIOD : real := 10.0;
                CLKOUT0_DIVIDE : integer := 8; DIVCLK_DIVIDE : integer := 1;
                STARTUP_WAIT : string := "FALSE" );
      port ( CLKFBIN : in std_ulogic; CLKFBOUT : out std_ulogic; CLKIN : in std_ulogic;
             CLKOUT0 : out std_ulogic; CLKOUTPHYEN : in std_ulogic;
             LOCKED : out std_ulogic; PWRDWN : in std_ulogic; RST : in std_ulogic );
    end component;

    -- UG572: "PLLE4_BASE is the same as PLLE3_BASE" -- identical generic/port
    -- list, separate primitive name for UltraScale+ parts
    component PLLE4_BASE is
      generic ( CLKFBOUT_MULT : integer := 8; CLKIN_PERIOD : real := 10.0;
                CLKOUT0_DIVIDE : integer := 8; DIVCLK_DIVIDE : integer := 1;
                STARTUP_WAIT : string := "FALSE" );
      port ( CLKFBIN : in std_ulogic; CLKFBOUT : out std_ulogic; CLKIN : in std_ulogic;
             CLKOUT0 : out std_ulogic; CLKOUTPHYEN : in std_ulogic;
             LOCKED : out std_ulogic; PWRDWN : in std_ulogic; RST : in std_ulogic );
    end component;

    constant c_mult_max : integer := 64;

    -- PLL VCO ranges, -1 speed grade (DS189 Spartan-7/Artix-7 Table 38,
    -- cross-checked against real Clocking Wizard behavior; DS923 Virtex
    -- UltraScale+) -- verify against your exact target part's datasheet
    function f_pll_mult(period_ns : real; family : string; mult_max : integer) return integer is
        variable fin     : real := 1000.0 / period_ns;
        variable vco_min : real;
        variable vco_max : real;
        variable mult    : integer := 2;
    begin
        if family = "7SERIES" then
            vco_min := 800.0;  vco_max := 1600.0;
        else
            -- ULTRASCALE and ULTRASCALEPLUS share one range: per UG572,
            -- PLLE4_BASE is electrically the same primitive as PLLE3_BASE
            vco_min := 750.0;  vco_max := 1500.0;
        end if;

        while (fin * real(mult) < vco_min) and (mult < mult_max) loop
            mult := mult + 1;
        end loop;

        assert (fin * real(mult) >= vco_min) and (fin * real(mult) <= vco_max)
          report "f_pll_mult: no integer CLKFBOUT_MULT keeps VCO in range for this g_clkin_period_ns"
          severity failure;

        return mult;
    end function;

    constant c_mult : integer := f_pll_mult(g_clkin_period_ns, g_family, c_mult_max);

    signal clkfbout : std_ulogic;

begin

    assert false
      report "clk_gen_wrapper: family=" & g_family & " mult=" & integer'image(c_mult) &
             " VCO=" & real'image(1000.0/g_clkin_period_ns * real(c_mult)) & " MHz (passthrough)"
      severity note;

    gen_7series : if g_family = "7SERIES" generate
        pll_inst : PLLE2_BASE
          generic map ( CLKFBOUT_MULT => c_mult, CLKIN1_PERIOD => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_mult, DIVCLK_DIVIDE => 1, STARTUP_WAIT => "TRUE" )
          port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout, CLKIN1 => clk_i,
                     CLKOUT0 => clk_o, LOCKED => locked_o, PWRDWN => '0', RST => '0' );
    end generate gen_7series;

    gen_ultrascale : if g_family = "ULTRASCALE" generate
        pll_inst : PLLE3_BASE
          generic map ( CLKFBOUT_MULT => c_mult, CLKIN_PERIOD => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_mult, DIVCLK_DIVIDE => 1, STARTUP_WAIT => "TRUE" )
          port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout, CLKIN => clk_i,
                     CLKOUT0 => clk_o, CLKOUTPHYEN => '0',
                     LOCKED => locked_o, PWRDWN => '0', RST => '0' );
    end generate gen_ultrascale;

    gen_ultrascaleplus : if g_family = "ULTRASCALEPLUS" generate
        pll_inst : PLLE4_BASE
          generic map ( CLKFBOUT_MULT => c_mult, CLKIN_PERIOD => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_mult, DIVCLK_DIVIDE => 1, STARTUP_WAIT => "TRUE" )
          port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout, CLKIN => clk_i,
                     CLKOUT0 => clk_o, CLKOUTPHYEN => '0',
                     LOCKED => locked_o, PWRDWN => '0', RST => '0' );
    end generate gen_ultrascaleplus;

end Structure;
