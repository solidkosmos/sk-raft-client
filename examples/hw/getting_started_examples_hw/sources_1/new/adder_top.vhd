----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: adder_top
-- Description: Static combinational adder (+5) driving LEDs directly from switch inputs -- first example in the get-started series.
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;


-- 1st Example : Static adder
-- Input a binary number that is increased by 5

-- Design was implemented on the Basys3 Board(XC7A35T) which has 16 leds available
-- Modify generics to fit your setup 

entity adder_top is
  Generic (
    added_num_bit_len : integer range 1 to 15 := 4 -- Max 15 bits, reserved 1 for the static 5 addition 
  );
  Port ( 
    sw_add_num_i : in unsigned(added_num_bit_len - 1 downto 0);
    data_o       : out unsigned(added_num_bit_len downto 0) -- added_num_len + 1bits to cover the +5 addition
  );
end adder_top;

architecture Behavioral of adder_top is
    
    signal addition_result : unsigned(added_num_bit_len downto 0) := (others =>  '0');
    
begin

    -- Combinational circuit, static addition with +5 
    addition_result <= ('0' & sw_add_num_i) + 5; -- extend by 1 bit to do the addition 
    -- Send to output(leds) 
    data_o <= addition_result;
    

end Behavioral;

