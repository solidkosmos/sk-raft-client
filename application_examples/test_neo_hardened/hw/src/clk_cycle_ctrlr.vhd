--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: clk_cycles_ctrlr
-- Description:
--   Single-step / burst clock-cycle controller used by the fault-injection
--   test harness. A host tool loads a 32-bit cycle count over JTAG (via the
--   "harness_controller" BSCAN bridge), this FSM gates an external BUFGCE to
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
--   Step-count command word, written via JTAG onto bscan_din_i. The FSM
--   only reads the word in the clk_i cycle where valid_i is 1:
--     0x00000000             - ignored, even with valid_i = 1
--     any other 32-bit value - load as the new cycle countdown value
--     CMD_START_C (0x1)      - release the countdown
--                              (WAIT_FOR_START -> COUNTING)
--     CMD_CANCEL_C (0x2)     - abort back to IDLE without running
--
--   step_cnt_out_o reports the live countdown value while COUNTING, and
--   reports TX_DRAIN_SENTINEL_C while parked in DRAIN_TX, so the host tool
--   can tell "still draining the UART" apart from "genuinely idle" (0x0).
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity clk_cycles_ctrlr is
  Port (
    -- free-running source clock (ungated)
    clk_i          : in  std_ulogic;
    -- async reset, active low
    rstn_i         : in  std_ulogic;

    -- JTAG-facing step-count interface (see "harness_controller") --
    -- command / step-count word from JTAG, synchronized to clk_i
    bscan_din_i    : in  std_ulogic_vector(31 downto 0);
    -- one clk_i cycle high when bscan_din_i has a new JTAG write
    valid_i        : in  std_ulogic;
    -- live countdown / status readback
    step_cnt_out_o : out std_ulogic_vector(31 downto 0);

    -- Gated clock enable, drives an external BUFGCE --
    clk_en_o       : out std_ulogic;

    -- NEORV32 graceful-stop handshake --
    -- UART still busy/queued: hold the clock on
    check_tx_i     : in  std_ulogic
  );
end clk_cycles_ctrlr;

architecture Behavioral of clk_cycles_ctrlr is

  -- Command sentinels for the JTAG step-count word --
  -- CMD_START_C  : Driver sets the countdown to start 
  -- CMD_CANCEL_C : Driver resets to IDLE for new step count to be written
  -- TX_DRAIN_SENTINEL_C : Codeword for driver to read and keep polling in order
  -- to pull UART data safely
  constant CMD_START_C         : std_ulogic_vector(31 downto 0) := x"00000001";
  constant CMD_CANCEL_C        : std_ulogic_vector(31 downto 0) := x"00000002";
  constant TX_DRAIN_SENTINEL_C : std_ulogic_vector(31 downto 0) := x"0000BEEF";

  -- Countdown / clock-gating FSM --
  type fsm_state_t is (IDLE, WAIT_FOR_START, COUNTING, DRAIN_TX);
  signal state : fsm_state_t;

  signal cycles_remaining : unsigned(31 downto 0);
  signal clk_en_q         : std_ulogic;
  signal step_cnt_out_q   : std_ulogic_vector(31 downto 0);

begin

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
          if valid_i = '1' and bscan_din_i /= x"00000000" then
            cycles_remaining <= unsigned(bscan_din_i);
            step_cnt_out_q   <= bscan_din_i;
            state            <= WAIT_FOR_START;
          else
            state <= IDLE;
          end if;

        -- Count is loaded but the clock is still gated off; wait for an
        -- explicit go/cancel command before letting any cycles through.
        when WAIT_FOR_START =>
          clk_en_q <= '0';
          if valid_i = '1' and bscan_din_i = CMD_START_C then
            state <= COUNTING;
          elsif valid_i = '1' and bscan_din_i = CMD_CANCEL_C then
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
            step_cnt_out_q   <= std_ulogic_vector(cycles_remaining);
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
            -- tell the host we're draining, not idle
            step_cnt_out_q <= TX_DRAIN_SENTINEL_C;
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