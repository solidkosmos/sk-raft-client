----------------------------------------------------------------------------------
-- Company: 
-- Engineer: Mario Bello
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
-- Original SolidKosmos work (secded_dec4b: 4-bit SECDED Hamming decoder used
-- for CPU exe-engine FSM-state hardening). Part of the NEORV32 hardening
-- example design published by SolidKosmos S.A. See LICENSE and
-- THIRD_PARTY_NOTICES.md at the project root.
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

entity secded_dec4b is
  Generic(
    data_len     : integer := 4;
    parities_len : integer := 3
  );
  Port ( 
        data_i      : in std_ulogic_vector(data_len - 1  downto 0);
        ecc_pars_i  : in std_ulogic_vector(parities_len - 1  downto 0);  
		par_i       : in std_ulogic;
        dec_o       : out std_ulogic_vector(data_len - 1 downto 0);
        corr_bit_o  : out std_ulogic;
		uncorr      : out std_ulogic
		
        
  );
end secded_dec4b;

architecture Behavioral of secded_dec4b is

signal syndrome : std_ulogic_vector(parities_len - 1 downto 0);
signal wd_i, corr_data : std_ulogic_vector((data_len + parities_len - 1) downto 0);
signal par_mismatch : std_ulogic;

begin


-- BITS :s 6 | 5 | 4 | 3 | 2 | 1 | 0
--         d3  d2  d1  p2  d0  p1  p0 


--p0 <= d(0) XOR d(1) XOR d(3);
--p1 <= d(0) XOR d(2) XOR d(3); 
--p2 <= d(1) XOR d(2) XOR d(3); 

--w_indexes 0        2       4        6
--syn(0) <= p0 XOR d(0) XOR d(1) XOR d(3);

--			1       2 		 5        6
--syn(1) <= p1 XOR d(0) XOR d(2) XOR d(3);

--          3		4        5        6
--syn(2) <= p2 XOR d(1) XOR d(2) XOR d(3);

wd_i(0) <= ecc_pars_i(0)   ;
wd_i(1) <= ecc_pars_i(1)   ;
wd_i(2) <= data_i(0)       ;
wd_i(3) <= ecc_pars_i(2)   ;
wd_i(4) <= data_i(1)       ;
wd_i(5) <= data_i(2)       ;
wd_i(6) <= data_i(3)       ;

ded_parity_gen:process(wd_i, par_i)
	variable vpar : std_ulogic;
	begin	
		vpar := '0';
		for i in 0 to 6 loop
			vpar := vpar XOR wd_i(i); --parity generation for double error detection
		end loop;
		
		par_mismatch <= vpar XOR par_i;
end process ded_parity_gen;


syndrome(0)<= ecc_pars_i(0) XOR data_i(0) XOR data_i(1) XOR data_i(3);
syndrome(1)<= ecc_pars_i(1) XOR data_i(0) XOR data_i(2) XOR data_i(3); 
syndrome(2)<= ecc_pars_i(2) XOR data_i(1) XOR data_i(2) XOR data_i(3); 

corr_data <= wd_i XOR "0000001" when (syndrome = "001" and par_mismatch = '1') else
             wd_i XOR "0000010" when (syndrome = "010" and par_mismatch = '1') else
             wd_i XOR "0000100" when (syndrome = "011" and par_mismatch = '1') else
             wd_i XOR "0001000" when (syndrome = "100" and par_mismatch = '1') else
             wd_i XOR "0010000" when (syndrome = "101" and par_mismatch = '1') else
             wd_i XOR "0100000" when (syndrome = "110" and par_mismatch = '1') else
             wd_i XOR "1000000" when (syndrome = "111" and par_mismatch = '1') else
             wd_i;

corr_bit_o <= '1' when(syndrome /= "000" and par_mismatch = '1') else
            '0';
			
uncorr     <= '1' when(syndrome /= "000" and par_mismatch = '0') else
            '0';
			



dec_o <= corr_data(6) & corr_data(5) & corr_data(4) & corr_data(2);







end Behavioral;
