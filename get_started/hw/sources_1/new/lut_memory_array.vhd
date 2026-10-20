--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: lut_memory_array
-- Description: LUTRAM (distributed RAM) memory array with a synchronous
--              write and an asynchronous read. ff_lut_top uses this array.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity lut_memory_array is
  Generic (
    mem_depth  : natural := 10;
    addr_width : natural := 4;
    data_len : natural := 32
  );
  Port ( 
    clk_i  : in std_ulogic;
    addr_i : in natural range 0 to mem_depth - 1;
    wr_en_i: in std_ulogic;
    din_i  : in std_ulogic_vector(data_len - 1 downto 0);
    dout_o : out std_ulogic_vector(data_len - 1 downto 0)
  );
end lut_memory_array;

architecture Behavioral of lut_memory_array is
    
    type lut_memory is array (0 to mem_depth - 1)
        of std_ulogic_vector(data_len - 1 downto 0);
    signal lut_mem : lut_memory := (others => (others => '0'));
    
    attribute ram_style : string;
    attribute ram_style of lut_mem : signal is "distributed";
    
begin

    lut_mem_access:process(clk_i)
        begin
           if rising_edge(clk_i) then
                -- New word available: write it. wr_en_i is a pulse of one
                -- cycle. Thus one JTAG write gives one memory write.
                if wr_en_i = '1' then
                    lut_mem(addr_i) <= din_i;
                end if;
           end if;
    end process lut_mem_access;
    
     dout_o <= lut_mem(addr_i);

end Behavioral;
