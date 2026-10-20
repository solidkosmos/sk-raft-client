--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: clk_gen_wrapper
-- Description: Portable Safe-Startup PLL wrapper. A generic selects the
--              family (7-series, UltraScale or UltraScale+).
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

-- The PLL operates continuously. The wrapper calculates DIVCLK_DIVIDE,
-- CLKFBOUT_MULT and CLKOUT0_DIVIDE from g_clkin_period_ns and
-- g_clkout_freq_mhz, inside the VCO and PFD ranges of each family, and
-- picks the setting closest to the requested output frequency.
-- g_clkout_freq_mhz = 0.0 gives an output clock with the same frequency
-- as the input clock (passthrough).
-- The output clock is gated until LOCKED has passed an 8-stage shift
-- register (safe startup).

entity clk_gen_wrapper is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_family          : string := "7SERIES";
    g_clkin_period_ns : real    := 10.0;  -- input clock period in ns
    -- requested output frequency in MHz (0.0 = same as input)
    g_clkout_freq_mhz : real    := 0.0
  );
  Port (
    clk_i    : in  std_ulogic;
    clk_o    : out std_ulogic;
    locked_o : out std_ulogic
  );
end clk_gen_wrapper;

architecture Structure of clk_gen_wrapper is

    type pll_cfg_t is record
        d    : integer;  -- DIVCLK_DIVIDE
        m    : integer;  -- CLKFBOUT_MULT
        o    : integer;  -- CLKOUT0_DIVIDE
        fout : real;     -- output frequency in MHz
    end record;

    -- PLL limits for each family (PLLE2 for 7-series, PLLE3 / PLLE4 for
    -- UltraScale / UltraScale+, slowest speed grade).
    function f_pll_cfg(period_ns : real; fout_req_mhz : real;
                       family : string) return pll_cfg_t is
        constant fin     : real := 1000.0 / period_ns;
        variable fout_r  : real;
        variable vco_min, vco_max, pfd_min, pfd_max : real;
        variable m_max, d_max : integer;
        variable vco, pfd, f, err : real;
        variable o       : integer;
        variable best    : pll_cfg_t := (0, 0, 0, 0.0);
        variable best_err : real := 1.0e9;
    begin
        if fout_req_mhz > 0.0 then
            fout_r := fout_req_mhz;
        else
            fout_r := fin;
        end if;
        if family = "7SERIES" then
            vco_min := 800.0;  vco_max := 1600.0;
            pfd_min := 19.0;   pfd_max := 450.0;
            m_max := 64;       d_max := 56;
        elsif family = "ULTRASCALE" then
            vco_min := 750.0;  vco_max := 1500.0;
            pfd_min := 70.0;   pfd_max := 667.5;
            m_max := 19;       d_max := 15;
        else
            vco_min := 750.0;  vco_max := 1500.0;
            pfd_min := 70.0;   pfd_max := 667.5;
            m_max := 21;       d_max := 15;
        end if;
        for d in 1 to d_max loop
            pfd := fin / real(d);
            if pfd >= pfd_min and pfd <= pfd_max then
                for m in 2 to m_max loop
                    vco := pfd * real(m);
                    if vco >= vco_min and vco <= vco_max then
                        o := integer(vco / fout_r);  -- rounds to nearest
                        if o < 1 then
                            o := 1;
                        elsif o > 128 then
                            o := 128;
                        end if;
                        f   := vco / real(o);
                        err := abs(f - fout_r);
                        if err < best_err then
                            best_err := err;
                            best     := (d, m, o, f);
                        end if;
                    end if;
                end loop;
            end if;
        end loop;
        assert best.m /= 0
          report "clk_gen_wrapper: no legal PLL setting for family " & family &
                 " with fin = " & real'image(fin) & " MHz"
          severity failure;
        return best;
    end function;

    constant c_req : real := g_clkout_freq_mhz;
    constant c_cfg : pll_cfg_t :=
        f_pll_cfg(g_clkin_period_ns, c_req, g_family);

    signal pll_clk_o, clkfbout, locked_sig : std_ulogic;
    signal seq_reg : std_ulogic_vector(7 downto 0) := (others => '0');

begin

    assert false
      report "clk_gen_wrapper: family=" & g_family &
             " D=" & integer'image(c_cfg.d) &
             " M=" & integer'image(c_cfg.m) &
             " O=" & integer'image(c_cfg.o) &
             " fout=" & real'image(c_cfg.fout) & " MHz"
      severity note;

    -- The core logic (for example the NEORV32 CLOCK_FREQUENCY generic) must
    -- use the real output frequency. Warn when it is more than 0.1 % off.
    assert (c_req = 0.0) or (abs(c_cfg.fout - c_req) <= 0.001 * c_req)
        report "clk_gen_wrapper: requested " & real'image(c_req)
        & " MHz, the closest PLL output is " & real'image(c_cfg.fout) & " MHz"
        severity warning;

    gen_7series : if g_family = "7SERIES" generate
        pll_inst : PLLE2_BASE
          Generic map ( CLKFBOUT_MULT  => c_cfg.m,
                        CLKIN1_PERIOD  => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_cfg.o,
                        DIVCLK_DIVIDE  => c_cfg.d,
                        STARTUP_WAIT   => "FALSE" )
          Port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout,
                     CLKIN1 => clk_i, CLKOUT0 => pll_clk_o,
                     LOCKED => locked_sig, PWRDWN => '0', RST => '0' );
    end generate gen_7series;

    gen_ultrascale : if g_family = "ULTRASCALE" generate
        pll_inst : PLLE3_BASE
          Generic map ( CLKFBOUT_MULT  => c_cfg.m,
                        CLKIN_PERIOD   => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_cfg.o,
                        DIVCLK_DIVIDE  => c_cfg.d,
                        STARTUP_WAIT   => "FALSE" )
          Port map ( CLKFBIN => clkfbout, CLKFBOUT => clkfbout,
                     CLKIN => clk_i, CLKOUT0 => pll_clk_o,
                     CLKOUTPHYEN => '0', LOCKED => locked_sig,
                     PWRDWN => '0', RST => '0' );
    end generate gen_ultrascale;

    gen_ultrascaleplus : if g_family = "ULTRASCALEPLUS" generate
        pll_inst : PLLE4_BASE
          Generic map ( CLKFBOUT_MULT  => c_cfg.m,
                        CLKIN_PERIOD   => g_clkin_period_ns,
                        CLKOUT0_DIVIDE => c_cfg.o,
                        DIVCLK_DIVIDE  => c_cfg.d,
                        STARTUP_WAIT   => "FALSE" )
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
