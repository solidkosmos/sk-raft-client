--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: clk_gen_wrapper
-- Description: Portable, family-selecting Safe-Startup PLL passthrough
--              wrapper (7-series / UltraScale / UltraScale+).
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

-- Portable, family-selecting, free-running Safe-Startup PLL passthrough
-- wrapper.
-- Auto-computes CLKFBOUT_MULT from g_clkin_period_ns alone (VCO range
-- lookup per family), instantiates the correct native PLL primitive via
-- generate, and outputs a clock at the same frequency as the input.


entity clk_gen_wrapper is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_family          : string := "7SERIES";
    g_clkin_period_ns : real    := 10.0       -- input clock period, ns
  );
  Port (
    clk_i  : in  std_ulogic;
    clk_o  : out std_ulogic;
    locked_o : out std_ulogic
  );
end clk_gen_wrapper;

architecture Structure of clk_gen_wrapper is

    constant c_mult_max : integer := 64;

    -- PLL VCO ranges, -1 speed grade (DS189 Spartan-7/Artix-7 Table 38,
    -- cross-checked against real Clocking Wizard behavior; DS923 Virtex
    -- UltraScale+) -- verify against your exact target part's datasheet
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
            -- ULTRASCALE and ULTRASCALEPLUS share one range: per UG572,
            -- PLLE4_BASE is electrically the same primitive as PLLE3_BASE
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

    -- A shift register that delays the propagation of the locked
    -- signal by 8 cycles, combined with the STARTUP_WAIT => FALSE
    -- declaration, we recreate the same Clocking Wizard MMCM/PLL
    -- SAFE_STARTUP setting behaviour available via the IP generation.
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

    locked_o <= seq_reg(7); -- Send out the delayed locked signal

    -- Gate until the locked signal has passed the 8 stage delay SR
    BUFGCE_inst_pll : BUFGCE
        Port map (
            O  => clk_o,       -- 1-bit output: Clock output
            CE => seq_reg(7),  -- 1-bit input: Clock enable input for I0
            I  => pll_clk_o    -- 1-bit input: Primary clock
        );

end Structure;
