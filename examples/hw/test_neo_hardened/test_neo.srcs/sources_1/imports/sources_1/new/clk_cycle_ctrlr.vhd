----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- Engineer: Mario Bello
--
-- Module Name: clk_cycles_ctrlr - Behavioral
--
-- Description:
--   Single-step / burst clock-cycle controller used by the fault-injection
--   test harness. A host tool loads a 32-bit cycle count over JTAG (via the
--   "tester" wrapper's BSCAN bridge), this FSM gates an external BUFGCE to
--   let exactly that many clock cycles reach the design under test (NEORV32),
--   then re-gates the clock off automatically.
--
--   One safety extension sits on top of the raw countdown:
--
--     check_tx_i - if the UART is still shifting or has bytes queued when
--     the countdown would otherwise expire, the FSM parks in DRAIN_TX and
--     keeps the clock alive until the UART genuinely goes idle, so an
--     in-flight print is never cut off mid-transmission.
--
--   Step-count command word, written via JTAG onto bscan_din_i:
--     0x00000000            - no new command (one-shot pulse already consumed)
--     any other 32-bit value - load as the new cycle countdown value
--     CMD_START_C (0x1)      - release the countdown (WAIT_FOR_START -> COUNTING)
--     CMD_CANCEL_C (0x2)     - abort back to IDLE without running
--
--   step_cnt_out_o reports the live countdown value while COUNTING, and
--   reports TX_DRAIN_SENTINEL_C while parked in DRAIN_TX, so the host tool
--   can tell "still draining the UART" apart from "genuinely idle" (0x0).
----------------------------------------------------------------------------------
-- SPDX-License-Identifier: BSD-3-Clause
-- Copyright (c) 2026, SolidKosmos S.A. All rights reserved.
-- Original SolidKosmos work (fault-injection test harness). Part of the
-- NEORV32 hardening example design published by SolidKosmos S.A.
-- See LICENSE and THIRD_PARTY_NOTICES.md at the project root.
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity clk_cycles_ctrlr is
  Port (
    clk_i          : in  std_logic;                     -- free-running source clock (ungated)
    rstn_i         : in  std_logic;                     -- async reset, active low

    -- JTAG-facing step-count interface (see "tester" wrapper) --
    bscan_din_i    : in  std_logic_vector(31 downto 0); -- command / step-count word from JTAG
    step_cnt_out_o : out std_logic_vector(31 downto 0); -- live countdown / status readback

    -- Gated clock enable, drives an external BUFGCE --
    clk_en_o       : out std_logic;

    -- NEORV32 graceful-stop handshake --
    check_tx_i     : in  std_ulogic                     -- UART still busy/queued: hold the clock on
  );
end clk_cycles_ctrlr;

architecture Behavioral of clk_cycles_ctrlr is

  -- Command sentinels for the JTAG step-count word --
  constant CMD_START_C         : std_logic_vector(31 downto 0) := x"00000001";
  constant CMD_CANCEL_C        : std_logic_vector(31 downto 0) := x"00000002";
  constant TX_DRAIN_SENTINEL_C : std_logic_vector(31 downto 0) := x"0000BEEF";

  -- Countdown / clock-gating FSM --
  type fsm_state_t is (IDLE, WAIT_FOR_START, COUNTING, DRAIN_TX);
  signal state : fsm_state_t;

  signal cycles_remaining : unsigned(31 downto 0);
  signal clk_en_q         : std_logic;
  signal step_cnt_out_q   : std_logic_vector(31 downto 0);

  -- One-shot detector for a newly-written value on bscan_din_i. bscan_din_i
  -- is a level held by the JTAG register, not a strobe, so a new value has
  -- to be edge-detected here; writing the same value twice in a row does
  -- nothing.
  signal bscan_din_q    : std_logic_vector(31 downto 0);
  signal bscan_din_q2   : std_logic_vector(31 downto 0);
  signal step_cmd_pulse : std_logic_vector(31 downto 0);

begin

  -- One-shot pulse generator ------------------------------------------------
  one_shot_pulse: process(clk_i, rstn_i)
  begin
    if rstn_i = '0' then
      bscan_din_q    <= (others => '0');
      bscan_din_q2   <= (others => '0');
      step_cmd_pulse <= (others => '0');
    elsif rising_edge(clk_i) then
      bscan_din_q <= bscan_din_i;
      -- one shot generator: reset or change the value in sw to set a new count value
      if bscan_din_q /= bscan_din_q2 then
        step_cmd_pulse <= bscan_din_q;
        bscan_din_q2   <= bscan_din_q;
      else
        step_cmd_pulse <= (others => '0');
        bscan_din_q2   <= bscan_din_q;
      end if;
    end if;
  end process one_shot_pulse;

  -- Countdown / clock-gating FSM ---------------------------------------------
  countdown_to_injection: process(clk_i, rstn_i)
  begin
    if rstn_i = '0' then
      cycles_remaining <= (others => '0');
      clk_en_q         <= '0';
      state            <= IDLE;
      step_cnt_out_q   <= (others => '0');
    elsif rising_edge(clk_i) then
      case state is

        -- Wait for the host to load a non-zero cycle count.
        when IDLE =>
          clk_en_q       <= '0';
          step_cnt_out_q <= (others => '0');
          if step_cmd_pulse /= x"00000000" then
            cycles_remaining <= unsigned(step_cmd_pulse);
            step_cnt_out_q   <= step_cmd_pulse;
            state            <= WAIT_FOR_START;
          else
            state <= IDLE;
          end if;

        -- Count is loaded but the clock is still gated off; wait for an
        -- explicit go/cancel command before letting any cycles through.
        when WAIT_FOR_START =>
          clk_en_q <= '0';
          if step_cmd_pulse = CMD_START_C then
            state <= COUNTING;
          elsif step_cmd_pulse = CMD_CANCEL_C then
            state <= IDLE;
          end if;

        -- Clock is live; count down one cycle at a time. A busy/queued UART
        -- always takes priority over the countdown, so a message in flight
        -- is never cut off mid-transmission.
        when COUNTING =>
          clk_en_q <= '1';
          if check_tx_i = '1' then
            state <= DRAIN_TX;
          elsif cycles_remaining /= x"00000000" then
            cycles_remaining <= cycles_remaining - 1;
            step_cnt_out_q   <= std_logic_vector(cycles_remaining);
            state            <= COUNTING;
          else
            step_cnt_out_q <= (others => '0');
            state          <= IDLE;
          end if;

        -- Clock stays live purely to let the UART finish draining; the
        -- countdown keeps decrementing in the background but doesn't gate
        -- anything while parked here. Falls back to COUNTING once check_tx_i
        -- clears.
        when DRAIN_TX =>
          clk_en_q <= '1';
          if cycles_remaining /= x"00000000" then
            cycles_remaining <= cycles_remaining - 1;
          end if;
          if check_tx_i = '1' then
            step_cnt_out_q <= TX_DRAIN_SENTINEL_C; -- tell the host we're draining, not idle
            state          <= DRAIN_TX;
          else
            state <= COUNTING;
          end if;

      end case;
    end if;
  end process countdown_to_injection;

  clk_en_o       <= clk_en_q;
  step_cnt_out_o <= step_cnt_out_q;

end Behavioral;
