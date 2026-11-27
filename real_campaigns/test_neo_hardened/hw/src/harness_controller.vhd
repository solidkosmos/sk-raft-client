--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: harness_controller
-- Description: Two-channel JTAG/BSCAN bridge for the fault-injection test
--              harness. The control signals and the written data are
--              synchronized to clk_i.
--              USER1: JTAG reads crc_data and writes the 1-bit design
--                     reset (rst_en).
--              USER2: JTAG reads data_out and writes the 32-bit step
--                     command (data_in). valid_o gives a one-cycle pulse
--                     when a new command arrives.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

use work.examples_utilities_pkg.all;

entity harness_controller is
  Port (
    -- Clock that does not stop with the design clock (in tester: root_clk,
    -- which USER3 can stop). Do not connect the gated design clock here:
    -- the CDC logic must keep running while the design clock is stopped.
    clk_i    : in  std_ulogic;
    -- 1-bit design reset, written via JTAG (USER1). Starts at 0, so the
    -- design stays in reset until JTAG releases it.
    rst_en   : out std_ulogic;
    -- Data read out via JTAG (USER1)
    crc_data : in  std_ulogic_vector(31 downto 0);
    -- Step command written via JTAG (USER2), synchronized to clk_i
    data_in  : out std_ulogic_vector(31 downto 0);
    -- Data read out via JTAG (USER2)
    data_out : in  std_ulogic_vector(31 downto 0);
    -- One clk_i cycle high when data_in has a new JTAG write
    valid_o  : out std_ulogic := '0'
  );
end harness_controller;

architecture Behavioral of harness_controller is

    constant jtag_data_len : integer := 32;
    constant jtag_rst_len  : integer := 1;

    -- Interface signals of the BSCAN registers

    -- BSCAN USER 1 : CRC READ / DESIGN RESET WRITE ----
    type bscan_rst_interfacing is record
        data_to_jtag   : std_ulogic_vector(jtag_data_len - 1 downto 0);
        data_from_jtag, data_from_jtag_sync :
            std_ulogic_vector(jtag_rst_len - 1 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_rst_interfacing;

    -- BSCAN USER 2 : STATUS READ / STEP COMMAND WRITE --
    type bscan_step_interfacing is record
        data_to_jtag   : std_ulogic_vector(jtag_data_len - 1 downto 0);
        data_from_jtag, data_from_jtag_sync :
            std_ulogic_vector(jtag_data_len - 1 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_step_interfacing;

    -- The reset bit starts at 0 (design in reset) after configuration.
    signal bscan_rst_user : bscan_rst_interfacing := (
        data_to_jtag        => (others => '0'),
        data_from_jtag      => (others => '0'),
        data_from_jtag_sync => (others => '0'),
        avail               => '0',
        avail_prev          => '0',
        ack                 => '0'
    );
    signal bscan_step_user : bscan_step_interfacing;

    -- The examples_utilities_pkg package declares bscan_interface (see the
    -- use clause above).

begin

    -- BSCAN U1 : CRC read and design reset write
    bscan_u1_crc_rst:bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => jtag_data_len,
        data_len_w => jtag_rst_len,
        sync       => true
      )
      Port map (
      ----- CLK INPUT FOR CONTROL SIGNAL CDC -----
        clk_i => clk_i,
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => bscan_rst_user.data_to_jtag,
        data_from_jtag_o => bscan_rst_user.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o => bscan_rst_user.avail,
        ux_ack_o   => open
      );

    -- The read data path is not synchronized (see bscan_interface). The
    -- host must read when the value is stable, for example while the
    -- design clock is stopped.
    bscan_rst_user.data_to_jtag <= crc_data;

    -- Generate the CDC control for the reset interface
    cdc_rst:process(clk_i)
        begin
            if rising_edge(clk_i) then
                bscan_rst_user.avail_prev <= bscan_rst_user.avail;
                if bscan_rst_user.avail = '1'
                   and bscan_rst_user.avail_prev = '0' then
                    bscan_rst_user.data_from_jtag_sync <=
                        bscan_rst_user.data_from_jtag;
                end if;
            end if;
    end process cdc_rst;

    rst_en <= bscan_rst_user.data_from_jtag_sync(0);


    -- BSCAN U2 : status read and step command write
    bscan_u2_step:bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => jtag_data_len,
        data_len_w => jtag_data_len,
        sync       => true
      )
      Port map (
      ----- CLK INPUT FOR CONTROL SIGNAL CDC -----
        clk_i => clk_i,
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => bscan_step_user.data_to_jtag,
        data_from_jtag_o => bscan_step_user.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o => bscan_step_user.avail,
        ux_ack_o   => open
      );

    -- The read data path is not synchronized (see bscan_interface).
    bscan_step_user.data_to_jtag <= data_out;

    -- Generate the CDC control for the step command interface
    cdc_step:process(clk_i)
        begin
            if rising_edge(clk_i) then
                bscan_step_user.avail_prev <= bscan_step_user.avail;
                if bscan_step_user.avail = '1'
                   and bscan_step_user.avail_prev = '0' then
                    bscan_step_user.data_from_jtag_sync <=
                        bscan_step_user.data_from_jtag;
                    valid_o <= '1';
                else
                    valid_o <= '0';
                end if;
            end if;
    end process cdc_step;

    data_in <= bscan_step_user.data_from_jtag_sync;

end Behavioral;