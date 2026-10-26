--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: mmcm_wrapper
-- Description: MMCM with all ports exposed, including the dynamic
--              reconfiguration port (DRP). A generic selects the family:
--              MMCME2_ADV (7-series), MMCME3_ADV (UltraScale) or
--              MMCME4_ADV (UltraScale+).
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

-- The DRP is the same on the three families: 7-bit address, 16-bit data
-- (XAPP888 for 7-series). The register addresses and the legal ranges
-- (VCO, PFD, M, D, O) are different for each family; check the data sheet
-- of the part. The wrapper does not connect the feedback: connect
-- clkfbout_o to clkfbin_i outside (directly, or through a BUFG).

entity mmcm_wrapper is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_family              : string  := "7SERIES";
    -- Start-up MMCM attributes. The same values are legal on the three
    -- families with the defaults: 100 MHz in, VCO 1000 MHz, 100 MHz out.
    -- The DRP can change the dividers and phases at run time.
    g_bandwidth           : string  := "OPTIMIZED";
    g_clkin1_period       : real    := 10.0;   -- CLKIN1 period in ns
    g_clkin2_period       : real    := 0.0;    -- CLKIN2 period in ns (0.0 = not used)
    g_divclk_divide       : integer := 1;      -- D
    g_clkfbout_mult_f     : real    := 10.0;   -- M
    g_clkfbout_phase      : real    := 0.0;
    g_clkout0_divide_f    : real    := 10.0;   -- O0 (fractional)
    g_clkout1_divide      : integer := 10;     -- O1
    g_clkout2_divide      : integer := 10;     -- O2
    g_clkout3_divide      : integer := 10;     -- O3
    g_clkout4_divide      : integer := 10;     -- O4
    g_clkout5_divide      : integer := 10;     -- O5
    g_clkout6_divide      : integer := 10;     -- O6
    g_clkout0_phase       : real    := 0.0;
    g_clkout1_phase       : real    := 0.0;
    g_clkout2_phase       : real    := 0.0;
    g_clkout3_phase       : real    := 0.0;
    g_clkout4_phase       : real    := 0.0;
    g_clkout5_phase       : real    := 0.0;
    g_clkout6_phase       : real    := 0.0;
    g_clkout0_duty_cycle  : real    := 0.5;
    g_clkout1_duty_cycle  : real    := 0.5;
    g_clkout2_duty_cycle  : real    := 0.5;
    g_clkout3_duty_cycle  : real    := 0.5;
    g_clkout4_duty_cycle  : real    := 0.5;
    g_clkout5_duty_cycle  : real    := 0.5;
    g_clkout6_duty_cycle  : real    := 0.5
  );
  Port (
    -- Clock inputs and feedback
    clkin1_i       : in  std_ulogic;
    clkin2_i       : in  std_ulogic;
    clkinsel_i     : in  std_ulogic;   -- 1 = CLKIN1, 0 = CLKIN2
    clkfbin_i      : in  std_ulogic;
    clkfbout_o     : out std_ulogic;
    clkfboutb_o    : out std_ulogic;
    -- Clock outputs
    clkout0_o      : out std_ulogic;
    clkout0b_o     : out std_ulogic;
    clkout1_o      : out std_ulogic;
    clkout1b_o     : out std_ulogic;
    clkout2_o      : out std_ulogic;
    clkout2b_o     : out std_ulogic;
    clkout3_o      : out std_ulogic;
    clkout3b_o     : out std_ulogic;
    clkout4_o      : out std_ulogic;
    clkout5_o      : out std_ulogic;
    clkout6_o      : out std_ulogic;
    -- Dynamic reconfiguration port (DRP)
    dclk_i         : in  std_ulogic;
    den_i          : in  std_ulogic;
    dwe_i          : in  std_ulogic;
    daddr_i        : in  std_ulogic_vector(6 downto 0);
    di_i           : in  std_ulogic_vector(15 downto 0);
    do_o           : out std_ulogic_vector(15 downto 0);
    drdy_o         : out std_ulogic;
    -- Dynamic phase shift
    psclk_i        : in  std_ulogic;
    psen_i         : in  std_ulogic;
    psincdec_i     : in  std_ulogic;
    psdone_o       : out std_ulogic;
    -- Clock divide change request (UltraScale and UltraScale+ only). On
    -- 7-series, cddcreq_i is not used and cddcdone_o is 0.
    cddcreq_i      : in  std_ulogic;
    cddcdone_o     : out std_ulogic;
    -- Control and status
    rst_i          : in  std_ulogic;
    pwrdwn_i       : in  std_ulogic;
    locked_o       : out std_ulogic;
    clkinstopped_o : out std_ulogic;
    clkfbstopped_o : out std_ulogic
  );
end mmcm_wrapper;

architecture Structure of mmcm_wrapper is

    -- The UNISIM DRP buses are std_logic_vector.
    signal daddr_s : std_logic_vector(6 downto 0);
    signal di_s    : std_logic_vector(15 downto 0);
    signal do_s    : std_logic_vector(15 downto 0);

begin

    daddr_s <= std_logic_vector(daddr_i);
    di_s    <= std_logic_vector(di_i);
    do_o    <= std_ulogic_vector(do_s);

    gen_7series : if g_family = "7SERIES" generate
        mmcm_inst : MMCME2_ADV
          Generic map (
            BANDWIDTH          => g_bandwidth,
            CLKFBOUT_MULT_F    => g_clkfbout_mult_f,
            CLKFBOUT_PHASE     => g_clkfbout_phase,
            CLKIN1_PERIOD      => g_clkin1_period,
            CLKIN2_PERIOD      => g_clkin2_period,
            DIVCLK_DIVIDE      => g_divclk_divide,
            CLKOUT0_DIVIDE_F   => g_clkout0_divide_f,
            CLKOUT1_DIVIDE     => g_clkout1_divide,
            CLKOUT2_DIVIDE     => g_clkout2_divide,
            CLKOUT3_DIVIDE     => g_clkout3_divide,
            CLKOUT4_DIVIDE     => g_clkout4_divide,
            CLKOUT5_DIVIDE     => g_clkout5_divide,
            CLKOUT6_DIVIDE     => g_clkout6_divide,
            CLKOUT0_PHASE      => g_clkout0_phase,
            CLKOUT1_PHASE      => g_clkout1_phase,
            CLKOUT2_PHASE      => g_clkout2_phase,
            CLKOUT3_PHASE      => g_clkout3_phase,
            CLKOUT4_PHASE      => g_clkout4_phase,
            CLKOUT5_PHASE      => g_clkout5_phase,
            CLKOUT6_PHASE      => g_clkout6_phase,
            CLKOUT0_DUTY_CYCLE => g_clkout0_duty_cycle,
            CLKOUT1_DUTY_CYCLE => g_clkout1_duty_cycle,
            CLKOUT2_DUTY_CYCLE => g_clkout2_duty_cycle,
            CLKOUT3_DUTY_CYCLE => g_clkout3_duty_cycle,
            CLKOUT4_DUTY_CYCLE => g_clkout4_duty_cycle,
            CLKOUT5_DUTY_CYCLE => g_clkout5_duty_cycle,
            CLKOUT6_DUTY_CYCLE => g_clkout6_duty_cycle
          )
          Port map (
            -- Clock inputs and feedback
            CLKIN1       => clkin1_i,
            CLKIN2       => clkin2_i,
            CLKINSEL     => clkinsel_i,
            CLKFBIN      => clkfbin_i,
            CLKFBOUT     => clkfbout_o,
            CLKFBOUTB    => clkfboutb_o,
            -- Clock outputs
            CLKOUT0      => clkout0_o,
            CLKOUT0B     => clkout0b_o,
            CLKOUT1      => clkout1_o,
            CLKOUT1B     => clkout1b_o,
            CLKOUT2      => clkout2_o,
            CLKOUT2B     => clkout2b_o,
            CLKOUT3      => clkout3_o,
            CLKOUT3B     => clkout3b_o,
            CLKOUT4      => clkout4_o,
            CLKOUT5      => clkout5_o,
            CLKOUT6      => clkout6_o,
            -- Dynamic reconfiguration port (DRP)
            DCLK         => dclk_i,
            DEN          => den_i,
            DWE          => dwe_i,
            DADDR        => daddr_s,
            DI           => di_s,
            DO           => do_s,
            DRDY         => drdy_o,
            -- Dynamic phase shift
            PSCLK        => psclk_i,
            PSEN         => psen_i,
            PSINCDEC     => psincdec_i,
            PSDONE       => psdone_o,
            -- Control and status
            RST          => rst_i,
            PWRDWN       => pwrdwn_i,
            LOCKED       => locked_o,
            CLKINSTOPPED => clkinstopped_o,
            CLKFBSTOPPED => clkfbstopped_o
          );

        -- No clock divide change request on 7-series
        cddcdone_o <= '0';
    end generate gen_7series;

    gen_ultrascale : if g_family = "ULTRASCALE" generate
        mmcm_inst : MMCME3_ADV
          Generic map (
            BANDWIDTH          => g_bandwidth,
            CLKFBOUT_MULT_F    => g_clkfbout_mult_f,
            CLKFBOUT_PHASE     => g_clkfbout_phase,
            CLKIN1_PERIOD      => g_clkin1_period,
            CLKIN2_PERIOD      => g_clkin2_period,
            DIVCLK_DIVIDE      => g_divclk_divide,
            CLKOUT0_DIVIDE_F   => g_clkout0_divide_f,
            CLKOUT1_DIVIDE     => g_clkout1_divide,
            CLKOUT2_DIVIDE     => g_clkout2_divide,
            CLKOUT3_DIVIDE     => g_clkout3_divide,
            CLKOUT4_DIVIDE     => g_clkout4_divide,
            CLKOUT5_DIVIDE     => g_clkout5_divide,
            CLKOUT6_DIVIDE     => g_clkout6_divide,
            CLKOUT0_PHASE      => g_clkout0_phase,
            CLKOUT1_PHASE      => g_clkout1_phase,
            CLKOUT2_PHASE      => g_clkout2_phase,
            CLKOUT3_PHASE      => g_clkout3_phase,
            CLKOUT4_PHASE      => g_clkout4_phase,
            CLKOUT5_PHASE      => g_clkout5_phase,
            CLKOUT6_PHASE      => g_clkout6_phase,
            CLKOUT0_DUTY_CYCLE => g_clkout0_duty_cycle,
            CLKOUT1_DUTY_CYCLE => g_clkout1_duty_cycle,
            CLKOUT2_DUTY_CYCLE => g_clkout2_duty_cycle,
            CLKOUT3_DUTY_CYCLE => g_clkout3_duty_cycle,
            CLKOUT4_DUTY_CYCLE => g_clkout4_duty_cycle,
            CLKOUT5_DUTY_CYCLE => g_clkout5_duty_cycle,
            CLKOUT6_DUTY_CYCLE => g_clkout6_duty_cycle
          )
          Port map (
            -- Clock inputs and feedback
            CLKIN1       => clkin1_i,
            CLKIN2       => clkin2_i,
            CLKINSEL     => clkinsel_i,
            CLKFBIN      => clkfbin_i,
            CLKFBOUT     => clkfbout_o,
            CLKFBOUTB    => clkfboutb_o,
            -- Clock outputs
            CLKOUT0      => clkout0_o,
            CLKOUT0B     => clkout0b_o,
            CLKOUT1      => clkout1_o,
            CLKOUT1B     => clkout1b_o,
            CLKOUT2      => clkout2_o,
            CLKOUT2B     => clkout2b_o,
            CLKOUT3      => clkout3_o,
            CLKOUT3B     => clkout3b_o,
            CLKOUT4      => clkout4_o,
            CLKOUT5      => clkout5_o,
            CLKOUT6      => clkout6_o,
            -- Dynamic reconfiguration port (DRP)
            DCLK         => dclk_i,
            DEN          => den_i,
            DWE          => dwe_i,
            DADDR        => daddr_s,
            DI           => di_s,
            DO           => do_s,
            DRDY         => drdy_o,
            -- Dynamic phase shift
            PSCLK        => psclk_i,
            PSEN         => psen_i,
            PSINCDEC     => psincdec_i,
            PSDONE       => psdone_o,
            -- Clock divide change request (UltraScale and UltraScale+)
            CDDCREQ      => cddcreq_i,
            CDDCDONE     => cddcdone_o,
            -- Control and status
            RST          => rst_i,
            PWRDWN       => pwrdwn_i,
            LOCKED       => locked_o,
            CLKINSTOPPED => clkinstopped_o,
            CLKFBSTOPPED => clkfbstopped_o
          );
    end generate gen_ultrascale;

    gen_ultrascaleplus : if g_family = "ULTRASCALEPLUS" generate
        mmcm_inst : MMCME4_ADV
          Generic map (
            BANDWIDTH          => g_bandwidth,
            CLKFBOUT_MULT_F    => g_clkfbout_mult_f,
            CLKFBOUT_PHASE     => g_clkfbout_phase,
            CLKIN1_PERIOD      => g_clkin1_period,
            CLKIN2_PERIOD      => g_clkin2_period,
            DIVCLK_DIVIDE      => g_divclk_divide,
            CLKOUT0_DIVIDE_F   => g_clkout0_divide_f,
            CLKOUT1_DIVIDE     => g_clkout1_divide,
            CLKOUT2_DIVIDE     => g_clkout2_divide,
            CLKOUT3_DIVIDE     => g_clkout3_divide,
            CLKOUT4_DIVIDE     => g_clkout4_divide,
            CLKOUT5_DIVIDE     => g_clkout5_divide,
            CLKOUT6_DIVIDE     => g_clkout6_divide,
            CLKOUT0_PHASE      => g_clkout0_phase,
            CLKOUT1_PHASE      => g_clkout1_phase,
            CLKOUT2_PHASE      => g_clkout2_phase,
            CLKOUT3_PHASE      => g_clkout3_phase,
            CLKOUT4_PHASE      => g_clkout4_phase,
            CLKOUT5_PHASE      => g_clkout5_phase,
            CLKOUT6_PHASE      => g_clkout6_phase,
            CLKOUT0_DUTY_CYCLE => g_clkout0_duty_cycle,
            CLKOUT1_DUTY_CYCLE => g_clkout1_duty_cycle,
            CLKOUT2_DUTY_CYCLE => g_clkout2_duty_cycle,
            CLKOUT3_DUTY_CYCLE => g_clkout3_duty_cycle,
            CLKOUT4_DUTY_CYCLE => g_clkout4_duty_cycle,
            CLKOUT5_DUTY_CYCLE => g_clkout5_duty_cycle,
            CLKOUT6_DUTY_CYCLE => g_clkout6_duty_cycle
          )
          Port map (
            -- Clock inputs and feedback
            CLKIN1       => clkin1_i,
            CLKIN2       => clkin2_i,
            CLKINSEL     => clkinsel_i,
            CLKFBIN      => clkfbin_i,
            CLKFBOUT     => clkfbout_o,
            CLKFBOUTB    => clkfboutb_o,
            -- Clock outputs
            CLKOUT0      => clkout0_o,
            CLKOUT0B     => clkout0b_o,
            CLKOUT1      => clkout1_o,
            CLKOUT1B     => clkout1b_o,
            CLKOUT2      => clkout2_o,
            CLKOUT2B     => clkout2b_o,
            CLKOUT3      => clkout3_o,
            CLKOUT3B     => clkout3b_o,
            CLKOUT4      => clkout4_o,
            CLKOUT5      => clkout5_o,
            CLKOUT6      => clkout6_o,
            -- Dynamic reconfiguration port (DRP)
            DCLK         => dclk_i,
            DEN          => den_i,
            DWE          => dwe_i,
            DADDR        => daddr_s,
            DI           => di_s,
            DO           => do_s,
            DRDY         => drdy_o,
            -- Dynamic phase shift
            PSCLK        => psclk_i,
            PSEN         => psen_i,
            PSINCDEC     => psincdec_i,
            PSDONE       => psdone_o,
            -- Clock divide change request (UltraScale and UltraScale+)
            CDDCREQ      => cddcreq_i,
            CDDCDONE     => cddcdone_o,
            -- Control and status
            RST          => rst_i,
            PWRDWN       => pwrdwn_i,
            LOCKED       => locked_o,
            CLKINSTOPPED => clkinstopped_o,
            CLKFBSTOPPED => clkfbstopped_o
          );
    end generate gen_ultrascaleplus;

    assert g_family = "7SERIES" or g_family = "ULTRASCALE" or
           g_family = "ULTRASCALEPLUS"
      report "mmcm_wrapper: unknown g_family " & g_family
      severity failure;

end Structure;
