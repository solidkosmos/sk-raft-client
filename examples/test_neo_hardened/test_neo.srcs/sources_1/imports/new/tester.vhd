----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- Engineer: Mario Bello
--
-- Module Name: tester - Behavioral
--
-- Description:
--   Top-level fault-injection test harness. Wires the two-channel BSCAN/JTAG
--   bridge (bscan_tester) to the cycle-stepping clock controller
--   (clk_cycles_ctrlr), and generates the gated clock that actually reaches
--   the NEORV32 instance under test via a BUFGCE.
--
--   JTAG channel map (see bscan_tester.vhd for the BSCANE2 USER register
--   assignment):
--     USER1 - write: 1-bit design reset (design_rstn), active low
--             read : 32-bit status/CRC word (crc_data)
--     USER2 - write: 32-bit step-count command, consumed by clk_cycles_ctrlr
--             read : live step-count / status readback
--
--   NOTE on entity ports: the port names on this entity (clk, clk_out,
--   rst_out, clk_en_out, crc_data, check_tx) are fixed by the parent design
--   (neorv32_test_setup_bootloader.vhd), which instantiates this entity by
--   name -- do not rename them without updating that instantiation too.
--
--   NOTE on hierarchy: the instance label "clk_cyc_ctrlr" below is
--   referenced by hierarchical path (clk_reset_ctrl/clk_cyc_ctrlr) from the
--   project's .xdc constraints (partial-reconfiguration pblock) -- keep
--   this label stable even if the entity it instantiates changes.
----------------------------------------------------------------------------------
-- SPDX-License-Identifier: BSD-3-Clause
-- Copyright (c) 2026, SolidKosmos S.A. All rights reserved.
-- Original SolidKosmos work (fault-injection test harness). Part of the
-- NEORV32 hardening example design published by SolidKosmos S.A.
-- See LICENSE and THIRD_PARTY_NOTICES.md at the project root.
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library unisim;
use unisim.vcomponents.all;

entity tester is
  Port (
    clk         : in  std_logic;

    -- Control signals to NEORV32
    clk_out     : out std_logic;
    rst_out     : out std_logic;

    -- Debug signals to LEDs
    clk_en_out  : out std_logic;
    crc_data    : in  std_logic_vector(31 downto 0);

    check_tx    : in  std_logic
  );
end tester;

architecture Behavioral of tester is

    -- Design-wide reset, active low. Written via JTAG channel 1 (USER1);
    -- see bscan_tester.vhd's rst_en port. Held low until the host
    -- explicitly releases it, so the design starts every run from a known
    -- state.
    signal design_rstn : std_logic;

    -- JTAG channel 2 (USER2) step-count write path, before/after CDC
    -- qualification into the clk domain.
    signal step_cmd_raw       : std_logic_vector(31 downto 0);
    signal step_cmd_qualified : std_logic_vector(31 downto 0);

    -- Step count / status word: written by clk_cycles_ctrlr, read out via
    -- JTAG channel 2 (USER2).
    signal step_status : std_logic_vector(31 downto 0);

    signal clk_en : std_logic;

    -- JTAG write-valid handshake: raw pulse from bscan_tester (TCK domain),
    -- double-flopped into the clk domain before it's trusted to latch
    -- step_cmd_raw into step_cmd_qualified.
    signal jtag_write_valid  : std_logic;
    signal write_valid_sync0 : std_logic;
    signal write_valid_sync1 : std_logic;

begin

    clk_en_bufg: BUFGCE
        port map (
            I  => clk,
            CE => clk_en,
            O  => clk_out
        );

    bscan: entity work.bscan_tester
        port map (
            rst_en   => design_rstn,      -- USER1 hex 02: design reset
            crc_data => crc_data,         -- USER1 hex 02: status/CRC word read via JTAG
            data_in  => step_cmd_raw,     -- USER2 hex 22: step-count word written via JTAG
            data_out => step_status,      -- USER2 hex 22: step-count/status read via JTAG
            valid_o  => jtag_write_valid  -- new JTAG write available
        );

    -- CDC: qualifies step_cmd_raw into step_cmd_qualified once
    -- jtag_write_valid has been double-flopped into the clk domain, i.e.
    -- once the TCK-domain write is known to have settled.
    cdc_valid_handshake: process(clk, design_rstn)
    begin
        if design_rstn = '0' then
            write_valid_sync0 <= '0';
            write_valid_sync1 <= '0';
        elsif rising_edge(clk) then
            write_valid_sync0 <= jtag_write_valid;
            write_valid_sync1 <= write_valid_sync0;
            if write_valid_sync1 = '1' then
                step_cmd_qualified <= step_cmd_raw;
            end if;
        end if;
    end process cdc_valid_handshake;

    clk_cyc_ctrlr: entity work.clk_cycles_ctrlr(Behavioral)
        port map (
            clk_i          => clk,
            rstn_i         => design_rstn,
            bscan_din_i    => step_cmd_qualified,
            step_cnt_out_o => step_status,
            clk_en_o       => clk_en,
            check_tx_i     => check_tx
        );

    clk_en_out <= clk_en;
    rst_out    <= design_rstn;

end Behavioral;
