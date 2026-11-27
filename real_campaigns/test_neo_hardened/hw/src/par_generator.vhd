--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: parity_generator
-- Description: Parameterized parity generator, used for the PC/PC2/RA parity
--              hardening.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity parity_generator is
  Generic(
        data_len : integer := 8
  );
  Port (
        data_i      : in std_ulogic_vector(data_len - 1 downto 0);
        par_o       : out std_ulogic
   );
end parity_generator;

architecture Behavioral of parity_generator is

signal int_sig : std_ulogic_vector(data_len - 1 downto 0);

begin

int_sig <= data_i;

parity_gen:process(int_sig)
	variable vpar : std_ulogic;
	begin	
		vpar := '0';
		for i in 0 to data_len - 1 loop
			vpar := vpar XOR int_sig(i); --parity generation for error detection
		end loop;
		
		par_o <= vpar;
end process parity_gen;

end Behavioral;
