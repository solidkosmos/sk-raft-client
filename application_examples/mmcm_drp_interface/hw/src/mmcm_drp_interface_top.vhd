--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: mmcm_drp_interface_top
-- Description: MMCM dynamic reconfiguration over BSCAN. The safe clock
--              (clk_gen_wrapper) clocks the BSCAN logic, the DRP control
--              FSM and the DRP of the MMCM, and it is the MMCM input clock.
--
--              BSCAN USER1
--                write (32 bits; bits 31:25 are padding, so that the
--                length is a whole number of bytes): the DRP control packet
--                  (24)    MMCM RST
--                  (23)    R/W flag (1 = write, 0 = read)
--                  (22:16) DRP address
--                  (15:0)  DRP write data
--                read (24 bits):
--                  (23:17) current DRP address
--                  (16:1)  MMCM DO
--                  (0)     DRP error (watchdog timeout)
--
--              MMCM CLKOUT0 and CLKOUT1 each drive a heartbeat that toggles
--              every 100 ms at 100 MHz (led_o). A change of the output
--              frequency shows as a change of the LED blink rate.
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity mmcm_drp_interface_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_family : string := "7SERIES"
  );
  Port (
    clk_i : in  std_ulogic;                    -- 100 MHz board clock
    led_o : out std_ulogic_vector(1 downto 0)  -- CLKOUT0, CLKOUT1 heartbeats
  );
end mmcm_drp_interface_top;

architecture Behavioral of mmcm_drp_interface_top is

    -- Safe clock
    signal safe_clk    : std_ulogic;
    signal safe_locked : std_ulogic;

    -- BSCAN USER1
    signal data_from_jtag : std_ulogic_vector(31 downto 0);
    signal data_to_jtag   : std_ulogic_vector(23 downto 0);
    signal avail          : std_ulogic;
    signal avail_prev     : std_ulogic := '0';

    -- BSCAN data in the safe clock domain, and the new command pulse
    signal pckt    : std_ulogic_vector(24 downto 0) := (others => '0');
    signal new_cmd : std_ulogic := '0';

    -- DRP control FSM <-> MMCM
    signal mmcm_rst : std_ulogic;
    signal drp_addr : std_ulogic_vector(6 downto 0);
    signal drp_di   : std_ulogic_vector(15 downto 0);
    signal drp_do   : std_ulogic_vector(15 downto 0);
    signal drp_den  : std_ulogic;
    signal drp_dwe  : std_ulogic;
    signal drp_drdy : std_ulogic;
    signal drp_err  : std_ulogic;
    signal clkfb    : std_ulogic;

    -- MMCM output clocks (before and after the global buffers)
    signal clkout0, clkout0_buf : std_ulogic;
    signal clkout1, clkout1_buf : std_ulogic;

    -- Heartbeat interval: 100 ms at 100 MHz (the MMCM start-up setting)
    constant c_hb_interval : integer := 10**7;

begin

    -- Safe clock: the board clock through the PLL (same frequency), gated
    -- until the PLL locks.
    safe_clk_gen : entity work.clk_gen_wrapper
      generic map (
        g_family          => g_family,
        g_clkin_period_ns => 10.0,
        g_clkout_freq_mhz => 0.0
      )
      port map (
        clk_i    => clk_i,
        clk_o    => safe_clk,
        locked_o => safe_locked
      );

    -- BSCAN USER1: DRP control packets in, status out. avail is
    -- synchronized to the safe clock.
    bscan_u1_drp : entity work.bscan_interface
      generic map (
        jtag_chain => 1,
        data_len_r => 24,
        data_len_w => 32,
        sync       => true
      )
      port map (
        clk_i            => safe_clk,
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => data_to_jtag,
        data_from_jtag_o => data_from_jtag,
        ux_avail_o       => avail,
        ux_ack_o         => open
      );

    -- Move the BSCAN data to the safe clock domain on the rising edge of
    -- avail, and give the FSM a one-cycle command pulse.
    bscan_cdc : process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            avail_prev <= avail;
            new_cmd    <= '0';
            if avail = '1' and avail_prev = '0' then
                pckt    <= data_from_jtag(24 downto 0);
                new_cmd <= '1';
            end if;
        end if;
    end process bscan_cdc;

    -- Status to BSCAN: current address, MMCM DO, error
    data_to_jtag <= drp_addr & drp_do & drp_err;

    -- DRP control FSM
    drp_ctrl : entity work.DRP_control
      port map (
        clk_i      => safe_clk,
        rstn_i     => safe_locked,
        new_cmd_i  => new_cmd,
        pckt_i     => pckt,
        drdy_i     => drp_drdy,
        mmcm_rst_o => mmcm_rst,
        addr_o     => drp_addr,
        data_o     => drp_di,
        den_o      => drp_den,
        dwe_o      => drp_dwe,
        drp_err_o  => drp_err
      );

    -- MMCM: CLKIN1 and DCLK from the safe clock, feedback connected
    -- directly. CLKOUT0 and CLKOUT1 drive the heartbeats.
    mmcm : entity work.mmcm_wrapper
      generic map (
        g_family        => g_family,
        g_clkin1_period => 10.0
      )
      port map (
        clkin1_i       => safe_clk,
        clkin2_i       => '0',
        clkinsel_i     => '1',
        clkfbin_i      => clkfb,
        clkfbout_o     => clkfb,
        clkfboutb_o    => open,
        clkout0_o      => clkout0,
        clkout0b_o     => open,
        clkout1_o      => clkout1,
        clkout1b_o     => open,
        clkout2_o      => open,
        clkout2b_o     => open,
        clkout3_o      => open,
        clkout3b_o     => open,
        clkout4_o      => open,
        clkout5_o      => open,
        clkout6_o      => open,
        dclk_i         => safe_clk,
        den_i          => drp_den,
        dwe_i          => drp_dwe,
        daddr_i        => drp_addr,
        di_i           => drp_di,
        do_o           => drp_do,
        drdy_o         => drp_drdy,
        psclk_i        => '0',
        psen_i         => '0',
        psincdec_i     => '0',
        psdone_o       => open,
        cddcreq_i      => '0',
        cddcdone_o     => open,
        rst_i          => mmcm_rst,
        pwrdwn_i       => '0',
        locked_o       => open,
        clkinstopped_o => open,
        clkfbstopped_o => open
      );

    -- Global buffers for the two MMCM output clocks
    clkout0_bufg : BUFG port map (I => clkout0, O => clkout0_buf);
    clkout1_bufg : BUFG port map (I => clkout1, O => clkout1_buf);

    -- Heartbeats: one LED for each MMCM output clock
    hb_clkout0 : entity work.heartbeat
      generic map (
        hb_interval => c_hb_interval
      )
      port map (
        clk_i => clkout0_buf, 
        heartbeat_o => led_o(0)
      );

    hb_clkout1 : entity work.heartbeat
      generic map (
        hb_interval => c_hb_interval
      )
      port map (
        clk_i => clkout1_buf, 
        heartbeat_o => led_o(1)
      );

end Behavioral;
