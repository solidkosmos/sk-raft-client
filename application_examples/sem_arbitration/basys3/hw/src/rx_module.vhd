--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: rx_module
-- Description: UART receiver, 8 data bits, no parity, 1 stop bit. It
--              samples rx_i oversample_rate times for each bit. After the
--              falling edge of the start bit it waits half a bit, then it
--              samples each data bit in its middle. avail_o is 1 from the
--              middle of the stop bit until the next start bit.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity rx_module is
  Generic (
    -- Frequency of clk_i in Hz
    clk_freq        : integer := 125000000;
    baud            : integer := 115200;
    oversample_rate : integer := 16
  );
  Port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    rx_i    : in  std_ulogic;
    -- 1 = new data in data_o
    avail_o : out std_ulogic;
    data_o  : out std_ulogic_vector(7 downto 0)
  );
end rx_module;

architecture Behavioral of rx_module is

    type rx_cycle is (IDLE, RECEIVE);
    signal rx_sm : rx_cycle := IDLE;
    signal os_count, os_tick, data_count : natural := 0;
    signal rx_sync, rx_reg, os_pulse, avail_sig : std_ulogic := '0';
    signal data_reg : std_ulogic_vector(7 downto 0) := x"00";

begin

    -- Two flip-flops synchronize rx_i to clk_i
    rx_sync_proc : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            rx_sync <= '1';
            rx_reg  <= '1';
        elsif rising_edge(clk_i) then
            rx_sync <= rx_i;
            rx_reg  <= rx_sync;
        end if;
    end process rx_sync_proc;

    -- Oversample tick: oversample_rate pulses for each bit
    os_generator : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            os_count <= 0;
            os_pulse <= '0';
        elsif rising_edge(clk_i) then
            if os_count = ((clk_freq / baud) / oversample_rate) - 1 then
                os_pulse <= '1';
                os_count <= 0;
            else
                os_pulse <= '0';
                os_count <= os_count + 1;
            end if;
        end if;
    end process os_generator;

    receiving_fsm : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            os_tick    <= 0;
            data_reg   <= x"00";
            data_count <= 0;
            rx_sm      <= IDLE;
            avail_sig  <= '0';
        elsif rising_edge(clk_i) then
            if os_pulse = '1' then
                case rx_sm is
                    when IDLE =>
                        if rx_reg = '0' then
                            os_tick <= os_tick + 1;
                            -- Middle of the start bit
                            if os_tick = oversample_rate / 2 then
                                avail_sig <= '0';
                                data_reg  <= x"00";
                                rx_sm     <= RECEIVE;
                                os_tick   <= 0;
                            end if;
                        else
                            -- The line went back to 1: it was a glitch,
                            -- not a start bit. Count again.
                            os_tick <= 0;
                        end if;
                    when RECEIVE =>
                        avail_sig <= '0';
                        os_tick   <= os_tick + 1;
                        -- One bit is oversample_rate ticks (os_tick counts
                        -- 0 to oversample_rate - 1)
                        if os_tick = oversample_rate - 1 then
                            if data_count < 8 then
                                data_reg(data_count) <= rx_reg;
                                data_count <= data_count + 1;
                            else
                                -- Middle of the stop bit
                                avail_sig  <= '1';
                                data_count <= 0;
                                rx_sm      <= IDLE;
                            end if;
                            os_tick <= 0;
                        end if;
                end case;
            end if;
        end if;
    end process receiving_fsm;

    avail_o <= avail_sig;
    data_o  <= data_reg;

end Behavioral;
