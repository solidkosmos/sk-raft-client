----------------------------------------------------------------------------------
-- Company: 
-- Engineer: 
-- 
-- Create Date: 17.04.2026 01:32:48
-- Design Name: 
-- Module Name: secded_enc - Behavioral
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
-- Original SolidKosmos work (secded_enc8b: 8-bit SECDED Hamming encoder,
-- adds an overall/DED parity bit on top of the 4-bit Hamming code, used for
-- DMEM byte-lane hardening). Part of the NEORV32 hardening example design
-- published by SolidKosmos S.A. See LICENSE and THIRD_PARTY_NOTICES.md at
-- the project root.
----------------------------------------------------------------------------------


library IEEE;
use IEEE.std_logic_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity secded_enc8b is
  Generic(
    data_len     : integer := 8;
    parities_len : integer := 4
  );
  Port ( 
        data_i       : in std_ulogic_vector(data_len - 1 downto 0);
        --data_o   	 : out std_ulogic_vector(data_len - 1 downto 0);
        par_o        : out std_ulogic_vector(parities_len - 1 downto 0);
        ded_par_o 	 : out std_ulogic
  );
end secded_enc8b;

architecture Behavioral of secded_enc8b is

signal ecc_par : std_ulogic_vector(parities_len - 1 downto 0);

signal encoded_word : std_ulogic_vector((data_len + parities_len - 1) downto 0);

begin

ecc_par(0) <= data_i(0) XOR data_i(1) XOR data_i(3) XOR data_i(4) XOR data_i(6);
ecc_par(1) <= data_i(0) XOR data_i(2) XOR data_i(3) XOR data_i(5) XOR data_i(6); 
ecc_par(2) <= data_i(1) XOR data_i(2) XOR data_i(3) XOR data_i(7); 
ecc_par(3) <= data_i(4) XOR data_i(5) XOR data_i(6) XOR data_i(7);  

encoded_word <= data_i & ecc_par;

ded_parity_gen:process(encoded_word)
	variable vpar : std_ulogic;
	begin	
		vpar := '0';
		for i in 0 to (data_len + parities_len - 1)  loop
			vpar := vpar XOR encoded_word(i); --parity generation for double error detection
		end loop;
		
		ded_par_o <= vpar;
end process ded_parity_gen;

par_o <= ecc_par;


end Behavioral;
