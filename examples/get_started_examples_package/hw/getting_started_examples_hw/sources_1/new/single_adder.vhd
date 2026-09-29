--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: single_adder
-- Description: Thin single-instance wrapper around the adder component (no
--              redundancy) -- baseline counterpart to tmr_adder for A/B
--              fault-injection comparison.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity single_adder is
  Generic (
    op_len : positive
  );
  Port ( 
    op_a_i : in std_ulogic_vector(op_len - 1 downto 0);
    op_b_i : in std_ulogic_vector(op_len - 1 downto 0);
    res_o  : out std_ulogic_vector(op_len downto 0)
  );
end single_adder;

architecture Structure of single_adder is

    component adder is
      Generic (
        op_len : positive
      );
      Port ( 
        op_a_i : in std_ulogic_vector(op_len - 1 downto 0);
        op_b_i : in std_ulogic_vector(op_len - 1 downto 0);
        res_o  : out std_ulogic_vector(op_len downto 0)
      );
    end component;
    
begin

    sngl_add:adder
      Generic map (
        op_len => op_len
      )
      Port map ( 
        op_a_i =>  op_a_i,
        op_b_i =>  op_b_i,
        res_o  =>  res_o  
      );
    

end Structure;
