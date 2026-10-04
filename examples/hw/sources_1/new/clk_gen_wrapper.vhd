--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: clk_gen_wrapper
-- Description: Portable Safe-Startup PLL passthrough wrapper. A generic
--              selects the family (7-series, UltraScale or UltraScale+).
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

-- Portable Safe-Startup PLL passthrough wrapper. The PLL operates
-- continuously, and g_family selects the device family.
-- The wrapper calculates CLKFBOUT_MULT from g_clkin_period_ns only (with a
-- VCO range lookup for each family). A generate statement instantiates the
-- correct native PLL primitive. The output clock has the same frequency as
-- the input clock.


entity clk_gen_wrapper is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_family          : string := "7SERIES";
    g_clkin_period_ns : real    := 10.0       -- input clock period in ns
  );
  Port (
    clk_i  : in  std_ulogic;
    clk_o  : out std_ulogic;
    locked_o : out std_ulogic
  );
end clk_gen_wrapper;

architecture Structure of clk_gen_wrapper is

    constant c_mult_max : integer := 64;

    -- PLL VCO ranges for the -1 speed grade. Sources: DS189 Spartan-7/Artix-7
    -- Table 38 (also compared with the real Clocking Wizard behavior) and
    -- DS923 Virtex UltraScale+. Make sure that the ranges agree with the
    -- data sheet of your exact target part.
    function f_pll_mult(period_ns : real; family : string;
                         mult_max : integer) return integer is
        variable fin     : real := 1000.0 / period_ns;
        variable vco_min : real;
        variable vco_max : real;
        variable mult    : integer := 2;
    begin
        if family = "7SERIES" then
            vco_min := 800.0;  vco_max := 1600.0;
        else
            -- ULTRASCALE and ULTRASCALEPLUS use the same range. UG572 says
            -- that PLLE4_BASE is electrically the same primitive as PLLE3_BASE.
            vco_min := 750.0;  vco_max := 1500.0;
        end if;

        while (fin * real(mult) < vco_min) and (mult < mult_max) loop
            mult := mult + 1;
        end loop;

        assert (fin * real(mult) >= vco_min) and (fin * real(mult) <= vco_max)
          report "f_pll_mult: no integer CLKFBOUT_MULT keeps VCO in range " &
                 "for this g_clkin_period_ns"
          severity failure;

        return mult;
    end function;

    constant c_mult : integer :=
        f_pll_mult(g_clkin_period_ns, g_family, c_mult_max);

    signal pll_clk_o, clkfbout, locked_sig : std_ulogic;

    -- A shift register delays the propagation of the locked signal by
    -- 8 clock cycles. Together with the STARTUP_WAIT => FALSE declaration,
    -- the shift register gives the same behaviour as the SAFE_STARTUP
    -- setting of the Clocking Wizard MMCM/PLL IP.
    signal seq_reg : std_ulogic_vector(7 downto 0) := (others => '0');
    
    
begin

    assert false
      report "clk_gen_wrapper: family=" & g_family & " mult=" &
             integer'image(c_mult) & " VCO=" &
             real'image(1000.0/g_clkin_period_ns * real(c_mult)) &
             " MHz (passthrough)"
      severity note;

    gen_7series : if g_family = "7SERIES" generate
        pll_inst : PLLE2_BASE
          Generic map ( CLKFBOUT_MULT => c_mult,
                        CLKIN1_PERIOD => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_mult, DIVCLK_DIVIDE => 1,
                        STARTUP_WAIT => "FALSE" )
          Port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout,
                     CLKIN1 => clk_i, CLKOUT0 => pll_clk_o,
                     LOCKED => locked_sig, PWRDWN => '0', RST => '0' );
    end generate gen_7series;

    gen_ultrascale : if g_family = "ULTRASCALE" generate
        pll_inst : PLLE3_BASE
          Generic map ( CLKFBOUT_MULT => c_mult,
                        CLKIN_PERIOD => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_mult, DIVCLK_DIVIDE => 1,
                        STARTUP_WAIT => "FALSE" )
          Port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout,
                     CLKIN => clk_i, CLKOUT0 => pll_clk_o,
                     CLKOUTPHYEN => '0', LOCKED => locked_sig,
                     PWRDWN => '0', RST => '0' );
    end generate gen_ultrascale;

    gen_ultrascaleplus : if g_family = "ULTRASCALEPLUS" generate
        pll_inst : PLLE4_BASE
          Generic map ( CLKFBOUT_MULT => c_mult,
                        CLKIN_PERIOD => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_mult, DIVCLK_DIVIDE => 1,
                        STARTUP_WAIT => "FALSE" )
          Port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout,
                     CLKIN => clk_i, CLKOUT0 => pll_clk_o,
                     CLKOUTPHYEN => '0', LOCKED => locked_sig,
                     PWRDWN => '0', RST => '0' );
    end generate gen_ultrascaleplus;

    safe_startup_sr_reg:process(pll_clk_o)
        begin
            if rising_edge(pll_clk_o) then
                seq_reg(0) <= locked_sig;
                for i in 0 to 6 loop
                    seq_reg(i + 1) <= seq_reg(i);
                end loop;
            end if;
    end process safe_startup_sr_reg;

    locked_o <= seq_reg(7); -- Send the delayed locked signal to the output

    -- Gate the clock until the locked signal passes through the 8-stage
    -- delay shift register
    BUFGCE_inst_pll : BUFGCE
        Port map (
            O  => clk_o,       -- 1-bit output: Clock output
            CE => seq_reg(7),  -- 1-bit input: Clock enable input for I0
            I  => pll_clk_o    -- 1-bit input: Primary clock
        );

end Structure;
