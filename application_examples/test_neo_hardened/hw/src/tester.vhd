--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: tester
-- Description:
--   Top-level fault-injection test harness. Wires the two-channel BSCAN/JTAG
--   bridge (harness_controller) to the cycle-stepping clock controller
--   (clk_cycles_ctrlr), and generates the gated clock that actually reaches
--   the NEORV32 instance under test via a BUFGCE.
--
--   Clock tree: the safe clock (clk_i, from the safe-startup PLL) goes first
--   through the root clock enable (BUFGCE, controlled by USER3). All logic
--   downstream -- harness_controller, clk_cycles_ctrlr and the NEORV32 clock
--   gate -- runs on this root clock. Only the USER3 synchronizer runs on the
--   ungated clk_i, so that the root clock can be enabled again.
--
--   JTAG channel map (see harness_controller.vhd for the BSCANE2 USER
--   register assignment of USER1 and USER2):
--     USER1 - write: 1-bit design reset (design_rstn), active low
--             read : 32-bit status/CRC word (crc_data)
--     USER2 - write: 32-bit step-count command, consumed by clk_cycles_ctrlr
--             read : live step-count / status readback
--     USER3 - write: 1-bit root clock enable (1 = clock on), starts at 0
--             read : the synchronized root clock enable
--
--   NOTE on entity ports: the port names on this entity (clk_i, clk_out,
--   rst_out, clk_en_out, crc_data, check_tx) are fixed by the parent design
--   (neorv32_test_setup_bootloader.vhd), which instantiates this entity by
--   name -- do not rename them without updating that instantiation too.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library unisim;
use unisim.vcomponents.all;

entity tester is
  Port (
    clk_i       : in  std_ulogic;

    -- Control signals to NEORV32
    clk_out     : out std_ulogic;
    rst_out     : out std_ulogic;

    -- Debug signals to LEDs
    clk_en_out  : out std_ulogic;
    crc_data    : in  std_ulogic_vector(31 downto 0);

    check_tx    : in  std_ulogic
  );
end tester;

architecture Behavioral of tester is

    -- Design-wide reset, active low. Written via JTAG channel 1 (USER1);
    -- see harness_controller.vhd's rst_en port. Held low until the host
    -- explicitly releases it, so the design starts every run from a known
    -- state.
    signal design_rstn : std_ulogic;

    -- JTAG channel 2 (USER2) step-count write path. The word is already
    -- synchronized to clk_i, and step_valid is high for one clk_i cycle
    -- when it holds a new JTAG write.
    signal step_cmd   : std_ulogic_vector(31 downto 0);
    signal step_valid : std_ulogic;

    -- Step count / status word: written by clk_cycles_ctrlr, read out via
    -- JTAG channel 2 (USER2).
    signal step_status : std_ulogic_vector(31 downto 0);

    signal clk_en : std_ulogic;

    -- Root clock enable (USER3): the JTAG bit, its two-stage synchronizer
    -- on the ungated clk_i, and the gated root clock
    signal root_en_jtag  : std_ulogic_vector(0 downto 0);
    signal root_en_rb    : std_ulogic_vector(0 downto 0);
    signal root_en_d0    : std_ulogic := '0';
    signal root_en_sync  : std_ulogic := '0';
    signal root_clk      : std_ulogic;

    attribute ASYNC_REG : string;
    attribute ASYNC_REG of root_en_d0   : signal is "TRUE";
    attribute ASYNC_REG of root_en_sync : signal is "TRUE";

begin

    -- Root clock enable -------------------------------------------------------
    -- USER3 writes the enable bit. The register is not synchronized inside
    -- bscan_interface (sync => false); the two flip-flops below synchronize it
    -- to clk_i, as in the getting-started examples.
    bscan_u3_root_clk_en: entity work.bscan_interface
        generic map (
            jtag_chain => 3,
            data_len_r => 1,
            data_len_w => 1, -- 1 bit for the root clock enable
            sync       => false
        )
        port map (
            clk_i            => '0',
            tck_o            => open,
            drck_o           => open,
            data_to_jtag_i   => root_en_rb,
            data_from_jtag_o => root_en_jtag,
            ux_avail_o       => open,
            ux_ack_o         => open
        );

    sync_root_en: process(clk_i)
    begin
        if rising_edge(clk_i) then
            root_en_d0   <= root_en_jtag(0);
            root_en_sync <= root_en_d0;
        end if;
    end process sync_root_en;

    -- read back the synchronized enable --
    root_en_rb(0) <= root_en_sync;

    -- root of the downstream clock tree --
    root_clk_bufg: BUFGCE
        port map (
            I  => clk_i,
            CE => root_en_sync,
            O  => root_clk
        );

    bscan: entity work.harness_controller
        port map (
            -- root clock (USER3), not the gated clk_out
            clk_i    => root_clk,
            rst_en   => design_rstn,   -- USER1 hex 02: design reset
            -- USER1 hex 02: status/CRC word read via JTAG
            crc_data => crc_data,
            -- USER2 hex 03: step-count word written via JTAG
            data_in  => step_cmd,
            -- USER2 hex 03: step-count/status read via JTAG
            data_out => step_status,
            valid_o  => step_valid     -- new JTAG write available
        );

    clk_cyc_ctrlr: entity work.clk_cycles_ctrlr(Behavioral)
        port map (
            clk_i          => root_clk,
            rstn_i         => design_rstn,
            bscan_din_i    => step_cmd,
            valid_i        => step_valid,
            step_cnt_out_o => step_status,
            clk_en_o       => clk_en,
            check_tx_i     => check_tx
        );

    neorv_clk_en_bufg: BUFGCE
        port map (
            I  => root_clk,
            CE => clk_en,
            O  => clk_out
        );

    clk_en_out <= clk_en;
    rst_out    <= design_rstn;

end Behavioral;