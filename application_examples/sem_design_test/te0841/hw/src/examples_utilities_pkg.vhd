--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: examples_utilities_pkg
-- Description: Shared component declarations for the reusable blocks of
--              the getting-started examples (BSCAN interface and clock
--              generator).
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

package examples_utilities_pkg is

    -- Interface to BSCAN.
    -- Each bscan_interface instance contains:
    -- 1) A BSCAN User Register IO instance. It serializes and deserializes
    --    the data to and from the JTAG BSCAN registers.
    -- 2) A BSCAN Primitive Wrapper. It wraps the BSCAN USER register
    --    primitive.
    component bscan_interface is
      Generic (
        jtag_chain : integer range 1 to 4;
        data_len_r : positive;
        data_len_w : positive;
        sync       : boolean := true
      );
      Port (
        ----- CLK INPUT FOR CDC -----
        clk_i  : in  std_ulogic;
        ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o  : out std_ulogic;
        ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o : out std_ulogic;
        ----- DATA PATH -----
        data_to_jtag_i   : in  std_ulogic_vector(data_len_r - 1 downto 0);
        data_from_jtag_o : out std_ulogic_vector(data_len_w - 1 downto 0);
        ----- CONTROL SIGNALS -----
        ux_avail_o : out std_ulogic;
        ux_ack_o   : out std_ulogic
      );
    end component;

    -- Portable PLL passthrough wrapper that operates continuously. A generic
    -- selects the family (7-series, UltraScale or UltraScale+).
    component clk_gen_wrapper is
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
    end component;


end package examples_utilities_pkg;
