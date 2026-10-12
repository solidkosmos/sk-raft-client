--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: fifo_mem
-- Description: Synchronous FIFO of 256 x 8 bits. The monitor interface
--              uses it as the UART buffer of the SEM. The read data
--              (dout_o) is the head word, without read latency. Writes to
--              a full FIFO and reads from an empty FIFO are ignored.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity fifo_mem is
  Port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    -- 8-bit write and read data
    din_i   : in  std_ulogic_vector(7 downto 0);
    dout_o  : out std_ulogic_vector(7 downto 0);
    -- Write and read enables, one word for each cycle
    wr_en_i : in  std_ulogic;
    rd_en_i : in  std_ulogic;
    empty_o : out std_ulogic;
    full_o  : out std_ulogic
  );
end fifo_mem;

architecture Behavioral of fifo_mem is

    -- Write and read pointers: 8 address bits and 1 lap bit (bit 8).
    -- If the address bits are equal, the FIFO is empty when the lap bits
    -- are equal, and full when they are different.
    signal wr_pntr, rd_pntr : unsigned(8 downto 0) := (others => '0');

    type fifo_mem_t is array (0 to 255) of std_ulogic_vector(7 downto 0);
    signal mem : fifo_mem_t;

    signal mem_full  : std_ulogic;
    signal mem_empty : std_ulogic;

begin

    fifo_pntr_proc : process(clk_i, rstn_i)
    begin
        if rstn_i = '0' then
            wr_pntr <= (others => '0');
            rd_pntr <= (others => '0');
        elsif rising_edge(clk_i) then
            if rd_en_i = '1' and mem_empty = '0' then
                rd_pntr <= rd_pntr + 1;
            end if;
            if wr_en_i = '1' and mem_full = '0' then
                wr_pntr <= wr_pntr + 1;
            end if;
        end if;
    end process fifo_pntr_proc;

    fifo_mem_proc : process(clk_i)
    begin
        if rising_edge(clk_i) then
            if wr_en_i = '1' and mem_full = '0' then
                mem(to_integer(wr_pntr(7 downto 0))) <= din_i;
            end if;
        end if;
    end process fifo_mem_proc;

    mem_empty <= '1' when wr_pntr = rd_pntr else '0';
    mem_full  <= '1' when wr_pntr(8) /= rd_pntr(8) and
                          wr_pntr(7 downto 0) = rd_pntr(7 downto 0)
                     else '0';

    empty_o <= mem_empty;
    full_o  <= mem_full;
    dout_o  <= mem(to_integer(rd_pntr(7 downto 0)));

end Behavioral;
