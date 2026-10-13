--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: sr_module
-- Description: N-bit circular shift register that operates continuously.
--              The initial value has a single '1' bit. The design
--              uses the register as a mass shift-register target for fault
--              injection and observation.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity sr_module is
  Generic (
    mass_bit_count : integer range 0 to 512 := 8
  );
  Port ( 
    clk_i   : in std_ulogic;
    data_o  : out std_ulogic_vector(mass_bit_count - 1 downto 0)
  );
end sr_module;

architecture Behavioral of sr_module is

    -- "000..01" pattern
    signal mass_s_reg :  std_ulogic_vector(mass_bit_count - 1 downto 0)
        := (0 => '1', others => '0');

    -- Synthesis attribute: prevent the optimization of the shift register
    -- signal. Keep each bit as a flip-flop. Fault injection targets these
    -- flip-flops, and synthesis can otherwise put them in SRLs or remove
    -- them.
    attribute dont_touch : string;
    attribute dont_touch of mass_s_reg : signal is "TRUE";
    
begin
    
    -- Circular shift register that operates continuously
    mass_sr_proc:process(clk_i)
        begin
            if rising_edge(clk_i) then
                mass_s_reg(0) <= mass_s_reg(mass_bit_count - 1); -- MSB to LSB
                for i in 0 to mass_bit_count - 2 loop
                    mass_s_reg(i + 1) <= mass_s_reg(i);
                end loop;
            end if;
    end process mass_sr_proc;

    data_o <= mass_s_reg;
     

end Behavioral;
