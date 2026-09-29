----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date: 16.04.2026 12:55:43
-- Design Name: 
-- Module Name: parity_generator - Behavioral
-- Project Name: 
-- Target Devices: 
-- Tool Versions: 
-- Description: 
-- 
-- Dependencies: 
-- 
-- Revision:
-- Revision 0.01 - File Created
-- Additional Comments:
-- 
----------------------------------------------------------------------------------
-- SPDX-License-Identifier: BSD-3-Clause
-- Copyright (c) 2026, SolidKosmos S.A. All rights reserved.
-- Original SolidKosmos work (parity_checker: parameterized parity checker
-- used for PC/PC2/RA parity hardening). Part of the NEORV32 hardening example
-- design published by SolidKosmos S.A. See LICENSE and THIRD_PARTY_NOTICES.md
-- at the project root.
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

entity parity_checker is
  Generic(
        data_len : integer := 8
  );
  Port (
        data_i      : in std_ulogic_vector(data_len - 1 downto 0);
        par_i       : in std_ulogic;
        check_o     : out std_ulogic
   );
end parity_checker;

architecture Behavioral of parity_checker is

signal int_sig : std_ulogic_vector(data_len - 1 downto 0);

begin

int_sig <= data_i;

parity_check:process(int_sig, par_i)
	variable vpar : std_ulogic;
	begin	
		vpar := '0';
		for i in 0 to data_len - 1 loop
			vpar := vpar XOR int_sig(i); --parity generation for error detection
		end loop;
		
		-- check parity mismatch --
		if vpar /= par_i then
		  check_o <= '1'; -- mismatch
		else 
		  check_o <= '0'; -- clear
		end if;
		
end process parity_check;

end Behavioral;
