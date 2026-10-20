--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: monitor_interface
-- Description: UART bridge for the monitor port of the 7-series SEM
--              (PG036). The SEM writes its reports into the TX FIFO. A
--              feeder sends the FIFO words on the UART TX line. The bytes
--              that come in on the UART RX line go into the RX FIFO, and
--              the SEM reads its commands from there.
--
--   SEM monitor_txdata -> fifo_tx -> feeder -> uart_rx_tx -> tx_o
--   rx_i -> uart_rx_tx -> fifo_rx -> SEM monitor_rxdata
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity monitor_interface is
  Generic (
    -- Frequency of clk_i in Hz
    clk_freq : integer := 100000000;
    -- UART baud rate. The SEM monitor uses 9600 8-N-1.
    baud     : integer := 9600
  );
  Port (
    clk_i  : in  std_ulogic;
    rstn_i : in  std_ulogic;
    tx_o   : out std_ulogic;
    rx_i   : in  std_ulogic;
    -- Data from the SEM to the UART TX
    monitor_txdata_i  : in  std_ulogic_vector(7 downto 0);
    monitor_txwrite_i : in  std_ulogic;
    -- 1 = the TX FIFO is full: the SEM waits
    monitor_txfull_o  : out std_ulogic;
    -- Data from the UART RX to the SEM
    monitor_rxdata_o  : out std_ulogic_vector(7 downto 0);
    monitor_rxread_i  : in  std_ulogic;
    -- 1 = the RX FIFO is empty: the SEM has no command to read
    monitor_rxempty_o : out std_ulogic
  );
end monitor_interface;

architecture Behavioral of monitor_interface is

    -- The head word of the TX FIFO, and the received UART byte
    signal tx_fifo_head : std_ulogic_vector(7 downto 0);
    signal rx_byte      : std_ulogic_vector(7 downto 0);

    -- TX FIFO read side
    signal tx_empty  : std_ulogic;
    signal feed_read : std_ulogic;

    -- UART TX handshake: start_tx requests a transmission, ack is 1 for
    -- one baud period when the UART latched the data
    signal start_tx      : std_ulogic;
    signal ack, ack_prev : std_ulogic;

    -- UART RX: avail is 1 when a new byte is in rx_byte. Its rising edge
    -- writes the byte into the RX FIFO.
    signal avail, avail_prev : std_ulogic;
    signal rx_wr_en          : std_ulogic;

    -- Feeder that moves the TX FIFO words to the UART TX
    type feeder_states is (IDLE, POLL, SETTLE);
    signal feeder_fsm : feeder_states := IDLE;

begin

    -- The SEM writes into this FIFO. The feeder reads it.
    fifo_tx : entity work.fifo_mem
      Port map (
        clk_i   => clk_i,
        rstn_i  => rstn_i,
        din_i   => monitor_txdata_i,
        dout_o  => tx_fifo_head,
        wr_en_i => monitor_txwrite_i,
        rd_en_i => feed_read,
        empty_o => tx_empty,
        full_o  => monitor_txfull_o
      );

    -- The UART TX latches tx_dt_i at its next baud tick after it sees
    -- start_tx. This can be one bit time later. Then it sets ack. Thus the
    -- word stays at the head of the FIFO until ack rises, and only then the
    -- feeder removes it from the FIFO.
    feed_uart_proc : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            start_tx   <= '0';
            feed_read  <= '0';
            ack_prev   <= '0';
            feeder_fsm <= IDLE;
        elsif rising_edge(clk_i) then
            ack_prev  <= ack;
            -- feed_read is a strobe of one cycle
            feed_read <= '0';
            case feeder_fsm is
                when IDLE =>
                    start_tx <= '0';
                    -- Request a transmission of the head word
                    if tx_empty = '0' then
                        start_tx   <= '1';
                        feeder_fsm <= POLL;
                    end if;
                when POLL =>
                    -- Rising edge of ack: the UART latched the head word.
                    -- Remove it from the FIFO and clear the request.
                    if ack_prev = '0' and ack = '1' then
                        feed_read  <= '1';
                        start_tx   <= '0';
                        feeder_fsm <= SETTLE;
                    end if;
                when SETTLE =>
                    -- One cycle for the FIFO pointer (and tx_empty) to
                    -- update after the read
                    feeder_fsm <= IDLE;
            end case;
        end if;
    end process feed_uart_proc;

    -- The UART RX writes into this FIFO. The SEM reads it. full_o is not
    -- used: the SEM reads the commands much faster than the UART receives
    -- them, thus the FIFO does not fill.
    fifo_rx : entity work.fifo_mem
      Port map (
        clk_i   => clk_i,
        rstn_i  => rstn_i,
        din_i   => rx_byte,
        dout_o  => monitor_rxdata_o,
        wr_en_i => rx_wr_en,
        rd_en_i => monitor_rxread_i,
        empty_o => monitor_rxempty_o,
        full_o  => open
      );

    avail_prev_proc : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            avail_prev <= '0';
        elsif rising_edge(clk_i) then
            avail_prev <= avail;
        end if;
    end process avail_prev_proc;

    -- Rising edge of avail: a new byte
    rx_wr_en <= avail and not avail_prev;

    uart_interface : entity work.uart_rx_tx
      generic map (
        clk_freq        => clk_freq,
        baud            => baud,
        oversample_rate => 16,
        data_bits       => 8
      )
      Port map (
        clk_i      => clk_i,
        rstn_i     => rstn_i,
        tx_o       => tx_o,
        rx_i       => rx_i,
        tx_dt_i    => tx_fifo_head,
        tx_start_i => start_tx,
        rx_dt_o    => rx_byte,
        avail_o    => avail,
        ack_o      => ack
      );

end Behavioral;
