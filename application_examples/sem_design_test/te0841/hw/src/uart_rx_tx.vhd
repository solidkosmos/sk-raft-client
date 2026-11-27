--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: uart_rx_tx
-- Description: UART with one receiver (rx_module) and one transmitter
--              (tx_module). 8 data bits, no parity, 1 stop bit.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity uart_rx_tx is
  Generic (
    -- Frequency of clk_i in Hz
    clk_freq        : integer := 100000000;
    baud            : integer := 9600;
    -- Samples for each bit in the receiver
    oversample_rate : integer := 16;
    data_bits       : integer := 8
  );
  Port (
    clk_i      : in  std_ulogic;
    rstn_i     : in  std_ulogic;
    -- Transmit line
    tx_o       : out std_ulogic;
    -- Receive line. The receiver starts at the falling edge of the start
    -- bit.
    rx_i       : in  std_ulogic;
    -- Data to transmit
    tx_dt_i    : in  std_ulogic_vector(data_bits - 1 downto 0);
    -- 1 = start a transmission of tx_dt_i
    tx_start_i : in  std_ulogic;
    -- Received data
    rx_dt_o    : out std_ulogic_vector(data_bits - 1 downto 0);
    -- 1 = new data in rx_dt_o
    avail_o    : out std_ulogic;
    -- 1 = the transmitter latched tx_dt_i
    ack_o      : out std_ulogic
  );
end uart_rx_tx;

architecture Structural of uart_rx_tx is
begin

    rx_data : entity work.rx_module
      generic map (
        clk_freq        => clk_freq,
        baud            => baud,
        oversample_rate => oversample_rate
      )
      port map (
        clk_i   => clk_i,
        rstn_i  => rstn_i,
        rx_i    => rx_i,
        avail_o => avail_o,
        data_o  => rx_dt_o
      );

    tx_data : entity work.tx_module
      generic map (
        clk_freq => clk_freq,
        baud     => baud
      )
      port map (
        clk_i      => clk_i,
        rstn_i     => rstn_i,
        data_i     => tx_dt_i,
        tx_o       => tx_o,
        start_tx_i => tx_start_i,
        ack_o      => ack_o
      );

end Structural;
