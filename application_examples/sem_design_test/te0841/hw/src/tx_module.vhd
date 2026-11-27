--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: tx_module
-- Description: UART transmitter, 8 data bits, no parity, 1 stop bit. At
--              the first baud tick with start_tx_i = 1 it latches data_i,
--              sets ack_o for one baud period and sends the start bit.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity tx_module is
  Generic (
    -- Frequency of clk_i in Hz
    clk_freq : integer := 125000000;
    baud     : integer := 115200
  );
  Port (
    clk_i      : in  std_ulogic;
    rstn_i     : in  std_ulogic;
    data_i     : in  std_ulogic_vector(7 downto 0);
    tx_o       : out std_ulogic;
    -- 1 = start a transmission of data_i
    start_tx_i : in  std_ulogic;
    -- 1 = data_i is latched
    ack_o      : out std_ulogic
  );
end tx_module;

architecture Behavioral of tx_module is

    type tx_cycle is (IDLE, TRANSMIT);
    signal tx_sm : tx_cycle := IDLE;
    signal baud_count, data_count : natural := 0;
    signal tx_sig, baud_pulse, ack_sig : std_ulogic := '0';
    signal data_reg : std_ulogic_vector(7 downto 0) := x"00";

begin

    -- Baud tick: one pulse for each bit
    baud_pulse_gen : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            baud_pulse <= '0';
            baud_count <= 0;
        elsif rising_edge(clk_i) then
            if baud_count = (clk_freq / baud) - 1 then
                baud_pulse <= '1';
                baud_count <= 0;
            else
                baud_pulse <= '0';
                baud_count <= baud_count + 1;
            end if;
        end if;
    end process baud_pulse_gen;

    tx_fsm : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            tx_sm      <= IDLE;
            data_reg   <= x"00";
            tx_sig     <= '1';
            data_count <= 0;
            ack_sig    <= '0';
        elsif rising_edge(clk_i) then
            if baud_pulse = '1' then
                case tx_sm is
                    when IDLE =>
                        -- The line is 1 in IDLE. This is also the stop bit
                        -- of the previous byte.
                        data_reg <= x"00";
                        tx_sig   <= '1';
                        ack_sig  <= '0';
                        if start_tx_i = '1' then
                            -- Latch the data and send the start bit
                            tx_sm      <= TRANSMIT;
                            tx_sig     <= '0';
                            data_count <= 0;
                            data_reg   <= data_i;
                            ack_sig    <= '1';
                        end if;
                    when TRANSMIT =>
                        ack_sig <= '0';
                        if data_count < 8 then
                            tx_sig     <= data_reg(data_count);
                            data_count <= data_count + 1;
                        else
                            tx_sm  <= IDLE;
                            tx_sig <= '1';
                        end if;
                end case;
            end if;
        end if;
    end process tx_fsm;

    ack_o <= ack_sig;
    tx_o  <= tx_sig;

end Behavioral;
