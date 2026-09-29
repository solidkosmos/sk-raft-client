--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: adder
-- Description: Combinational adder -- adds two op_len-bit operands,
--              producing an (op_len+1)-bit sum.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

use IEEE.NUMERIC_STD.ALL;

entity adder is
  Generic (
    op_len : positive
  );
  Port ( 
    op_a_i : in std_ulogic_vector(op_len - 1 downto 0);
    op_b_i : in std_ulogic_vector(op_len - 1 downto 0);
    res_o  : out std_ulogic_vector(op_len downto 0)
  );
end adder;

architecture Behavioral of adder is

begin

    -- Add the two numbers, we have to extend them in order for them to be
    -- added and assigned to the result
    res_o <= std_ulogic_vector(unsigned('0' & op_a_i) +
                               unsigned('0' & op_b_i));

end Behavioral;
