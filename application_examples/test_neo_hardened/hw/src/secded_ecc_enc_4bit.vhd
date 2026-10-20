--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: secded_enc4b
-- Description: 4-bit SECDED Hamming encoder, used for the CPU execute-engine
--              FSM-state hardening.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.std_logic_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity secded_enc4b is
  Generic(
    data_len     : integer := 4;
    parities_len : integer := 3
  );
  Port ( 
        data_i       : in std_ulogic_vector(data_len - 1 downto 0);
        --data_o   	 : out std_ulogic_vector(data_len - 1 downto 0);
        par_o        : out std_ulogic_vector(parities_len - 1 downto 0);
        ded_par_o 	 : out std_ulogic
  );
end secded_enc4b;

architecture Behavioral of secded_enc4b is

signal ecc_par : std_ulogic_vector(parities_len - 1 downto 0);

signal encoded_word : std_ulogic_vector((data_len + parities_len - 1) downto 0);

begin

ecc_par(0) <= data_i(0) XOR data_i(1) XOR data_i(3);
ecc_par(1) <= data_i(0) XOR data_i(2) XOR data_i(3); 
ecc_par(2) <= data_i(1) XOR data_i(2) XOR data_i(3); 

encoded_word <= data_i & ecc_par;


ded_parity_gen:process(encoded_word)
	variable vpar : std_ulogic;
	begin	
		vpar := '0';
		for i in 0 to 6 loop
            --parity generation for double error detection
            vpar := vpar XOR encoded_word(i);
		end loop;
		
		ded_par_o <= vpar;
end process ded_parity_gen;

par_o <= ecc_par;


end Behavioral;
