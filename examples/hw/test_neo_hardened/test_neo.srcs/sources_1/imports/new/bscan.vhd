----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- Engineer: Mario Bello
--
-- Module Name: bscan_tester - Behavioral
-- Description: Two-channel BSCAN bridge:
--   Channel 1 (USER1): reads crc_data out via JTAG, receives a 1-bit
--                       reset control back from JTAG (rst_en).
--   Channel 2 (USER2): reads data_out (e.g. BRAM contents) out via JTAG,
--                       receives a 32-bit write back from JTAG (data_in).
--
-- Uses the validated BSCANE2 primitive and bscan_user_register_io
-- (shift/capture/update register logic) for both channels, instead of
-- re-implementing shift-register logic here.
--
-- Each BSCANE2's RESET/RUNTEST outputs (JTAG TAP state indicators) aren't
-- needed by this design and are left unconnected (open).
----------------------------------------------------------------------------------
-- SPDX-License-Identifier: BSD-3-Clause
-- Copyright (c) 2026, SolidKosmos S.A. All rights reserved.
-- Original SolidKosmos work (fault-injection test harness). Part of the
-- NEORV32 hardening example design published by SolidKosmos S.A.
-- See LICENSE and THIRD_PARTY_NOTICES.md at the project root.
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity bscan_tester is
  Port (
    rst_en   : out std_logic;                      -- 1-bit reset control, written via JTAG (USER1)
    crc_data : in  std_logic_vector(31 downto 0);  -- data read out via JTAG (USER1)
    data_in  : out std_logic_vector(31 downto 0);  -- data written via JTAG, driven out to design (USER2)
    data_out : in  std_logic_vector(31 downto 0);  -- data read out via JTAG, e.g. BRAM contents (USER2)
    valid_o  : out std_logic                       -- handshake: new data_in available (USER2 channel)
  );
end bscan_tester;

architecture Behavioral of bscan_tester is

    constant DATA_LEN    : integer := 32;
    constant RST_LEN     : integer := 1;

    -----------------------------------------------------------------
    -- Channel 1 (USER1): CRC/status read / reset write
    -----------------------------------------------------------------
    signal tck_1     : std_ulogic;
    signal tck_buf_1 : std_ulogic;
    signal tms_1     : std_ulogic;
    signal tdi_1     : std_ulogic;
    signal tdo_1     : std_ulogic;
    signal sel_1     : std_ulogic;
    signal shift_1   : std_ulogic;
    signal update_1  : std_ulogic;
    signal capture_1 : std_ulogic;

    signal rst_en_u  : std_ulogic_vector(RST_LEN - 1 downto 0);

    -----------------------------------------------------------------
    -- Channel 2 (USER2): step-count read and write
    -----------------------------------------------------------------
    signal tck_2     : std_ulogic;
    signal tck_buf_2 : std_ulogic;
    signal tms_2     : std_ulogic;
    signal tdi_2     : std_ulogic;
    signal tdo_2     : std_ulogic;
    signal sel_2     : std_ulogic;
    signal shift_2   : std_ulogic;
    signal update_2  : std_ulogic;
    signal capture_2 : std_ulogic;

    signal avail_2   : std_ulogic;
    signal avail_2_q : std_ulogic := '0';
    signal data_in_u : std_ulogic_vector(DATA_LEN - 1 downto 0);

begin

    -----------------------------------------------------------------
    -- Channel 1: BSCANE2 (USER1) + register bridge
    -----------------------------------------------------------------
    BSCAN_U1_CRC_RST : BSCANE2
        generic map (
            JTAG_CHAIN => 1
        )
        port map (
            CAPTURE => capture_1,
            DRCK    => open,
            RESET   => open,   -- JTAG TAP reset indicator, unused
            RUNTEST => open,   -- JTAG TAP run-test indicator, unused
            SEL     => sel_1,
            SHIFT   => shift_1,
            TCK     => tck_1,
            TDI     => tdi_1,
            TMS     => tms_1,
            UPDATE  => update_1,
            TDO     => tdo_1
        );

    BUFG_tck_1 : BUFG
        port map (
            O => tck_buf_1,
            I => tck_1
        );

    -- NOTE: avail_o for this channel is left open. This entity currently
    -- exposes only one valid_o output at the bscan_tester level (see
    -- channel 2 below); add a second top-level output here if a
    -- write-valid handshake for the reset channel is ever needed.
    bscan_reg_1 : entity work.bscan_user_register_io
        generic map (
            data_to_jtag_len   => DATA_LEN,  -- crc_data out
            data_from_jtag_len => RST_LEN    -- rst_en in
        )
        port map (
            tck              => tck_buf_1,
            tms              => tms_1,
            tdi              => tdi_1,
            tdo              => tdo_1,
            sel              => sel_1,
            shift            => shift_1,
            update           => update_1,
            capture          => capture_1,
            avail_o          => open,
            ack_o            => open,
            data_to_jtag_i   => std_ulogic_vector(crc_data),
            data_from_jtag_o => rst_en_u
        );

    rst_en <= std_logic(rst_en_u(0)); -- active-low async reset control to our design

    -----------------------------------------------------------------
    -- Channel 2: BSCANE2 (USER2) + register bridge
    -----------------------------------------------------------------
    BSCAN_U2_STEP_COUNT : BSCANE2
        generic map (
            JTAG_CHAIN => 2
        )
        port map (
            CAPTURE => capture_2,
            DRCK    => open,
            RESET   => open,   -- JTAG TAP reset indicator, unused
            RUNTEST => open,   -- JTAG TAP run-test indicator, unused
            SEL     => sel_2,
            SHIFT   => shift_2,
            TCK     => tck_2,
            TDI     => tdi_2,
            TMS     => tms_2,
            UPDATE  => update_2,
            TDO     => tdo_2
        );

    BUFG_tck_2 : BUFG
        port map (
            O => tck_buf_2,
            I => tck_2
        );

    bscan_reg_2 : entity work.bscan_user_register_io
        generic map (
            data_to_jtag_len   => DATA_LEN, -- data_out (e.g. BRAM contents) read via JTAG
            data_from_jtag_len => DATA_LEN  -- data_in written via JTAG
        )
        port map (
            tck              => tck_buf_2,
            tms              => tms_2,
            tdi              => tdi_2,
            tdo              => tdo_2,
            sel              => sel_2,
            shift            => shift_2,
            update           => update_2,
            capture          => capture_2,
            avail_o          => avail_2,
            ack_o            => open,
            data_to_jtag_i   => std_ulogic_vector(data_out),
            data_from_jtag_o => data_in_u
        );

    data_in <= std_logic_vector(data_in_u);

    -----------------------------------------------------------------
    -- valid_o: pulses for one tck_buf_2 cycle when a new write via USER2
    -- lands on data_in. avail_2 is already TCK-domain and level-held from
    -- update until the next shift; this rising-edge detect turns that
    -- level into a single-cycle strobe.
    -----------------------------------------------------------------
    ASSERT_AVAIL_WORD: process(tck_buf_2)
    begin
        if rising_edge(tck_buf_2) then
            avail_2_q <= avail_2;
            if avail_2 = '1' and avail_2_q = '0' then
                valid_o <= '1';
            else
                valid_o <= '0';
            end if;
        end if;
    end process ASSERT_AVAIL_WORD;

end Behavioral;
