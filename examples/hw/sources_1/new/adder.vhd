--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: adder
-- Description: Combinational adder. It adds two operands of op_len bits
--              and gives a sum of op_len+1 bits.
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

    -- Add the two numbers. Extend each operand by 1 bit, so that the sum
    -- has the same width as the result.
    res_o <= std_ulogic_vector(unsigned('0' & op_a_i) +
                               unsigned('0' & op_b_i));

end Behavioral;
