----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: sr_module
-- Description: Free-running, self-wrapping N-bit shift register seeded with a single '1' bit --
--              used as a mass shift-register fault-injection/observation target.
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity sr_module is
  Generic (
    mass_bit_count : integer range 0 to 512 := 8
  );
  Port ( 
    clk_i   : in std_ulogic;
    data_o  : out std_ulogic_vector(mass_bit_count - 1 downto 0)
    --halt_i  : in std_ulogic
  );
end sr_module;

architecture Behavioral of sr_module is

    signal mass_s_reg :  std_ulogic_vector(mass_bit_count - 1 downto 0) := (0 => '1', others => '0'); -- "000..01" pattern
    
    -- Synthesis attributes: prevent optimization/flattening for every signal and instance --
    attribute dont_touch : string;
    attribute dont_touch of mass_s_reg : signal is "true";
    
begin
    
    -- Loop-around free-running shift register
    mass_sr_proc:process(clk_i)
        begin
            if rising_edge(clk_i) then
                mass_s_reg(0) <= mass_s_reg(mass_bit_count - 1); -- wrap
                for i in 0 to mass_bit_count - 2 loop
                    mass_s_reg(i + 1) <= mass_s_reg(i);
                end loop;
            end if;
    end process mass_sr_proc;

    data_o <= mass_s_reg;
     

end Behavioral;
