----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: secded_dec8b
-- Description: 8-bit Hamming SEC decoder -- recomputes the syndrome from the 8 data bits and 4
--              Hamming parity bits and corrects any single-bit error. Does not check the overall/DED
--              parity bit, so it cannot tell a single-bit error apart from a double-bit one.
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

entity secded_dec8b is
  Generic(
    data_len     : integer := 8;
    parities_len : integer := 4
  );
  Port ( 
    data_i      : in std_ulogic_vector(data_len - 1  downto 0);
    ecc_pars_i  : in std_ulogic_vector(parities_len - 1  downto 0);  
	par_i       : in std_ulogic;
    dec_o       : out std_ulogic_vector(data_len - 1 downto 0);
    corr_bit_o  : out std_ulogic;
	uncorr      : out std_ulogic
  );
end secded_dec8b;

architecture Behavioral of secded_dec8b is

signal syndrome : std_ulogic_vector(parities_len - 1 downto 0);
signal wd_i, corr_data : std_ulogic_vector((data_len + parities_len - 1) downto 0);

begin

-- BITS :s 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0
--        d7   d6   d5  d4  p3  d3  d2  d1  p2  d0  p1  p0 

--p0 <= d(0) XOR d(1) XOR d(3) XOR d(4) XOR d(6);
--p1 <= d(0) XOR d(2) XOR d(3) XOR d(5) XOR d(6); 
--p2 <= d(1) XOR d(2) XOR d(3) XOR d(7); 
--p3 <= d(4) XOR d(5) XOR d(6) XOR d(7);

--b_indexes 0        2       4        6
--syn(0) <= p0 XOR d(0) XOR d(1) XOR d(3) XOR d(4) XOR d(6);

--			1       2 		 5        6
--syn(1) <= p1 XOR d(0) XOR d(2) XOR d(3) XOR d(5) XOR d(6);

--          3		4        5        6
--syn(2) <= p2 XOR d(1) XOR d(2) XOR d(3) XOR d(7);

--
--syn(3) <= p3 XOR d(4) XOR d(5) XOR d(6) XOR d(7);

wd_i(0) <= ecc_pars_i(0)   ;
wd_i(1) <= ecc_pars_i(1)   ;
wd_i(2) <= data_i(0)       ;
wd_i(3) <= ecc_pars_i(2)   ;
wd_i(4) <= data_i(1)       ;
wd_i(5) <= data_i(2)       ;
wd_i(6) <= data_i(3)       ;
wd_i(7) <= ecc_pars_i(3)   ;
wd_i(8) <= data_i(4)       ;
wd_i(9) <= data_i(5)       ;
wd_i(10) <= data_i(6)      ;
wd_i(11) <= data_i(7)      ;

syndrome(0)<= ecc_pars_i(0) XOR data_i(0) XOR data_i(1) XOR data_i(3) XOR data_i(4) XOR data_i(6);
syndrome(1)<= ecc_pars_i(1) XOR data_i(0) XOR data_i(2) XOR data_i(3) XOR data_i(5) XOR data_i(6);
syndrome(2)<= ecc_pars_i(2) XOR data_i(1) XOR data_i(2) XOR data_i(3) XOR data_i(7);
syndrome(3)<= ecc_pars_i(3) XOR data_i(4) XOR data_i(5) XOR data_i(6) XOR data_i(7);

-- Correction is based on the syndrome alone; par_i is not checked here, so a
-- double-bit error looks the same as a single-bit one and gets "corrected"
-- into wrong data instead of being flagged. uncorr is tied to '0' below
-- because that distinction needs the overall parity bit, which this decoder
-- doesn't check.
corr_data <= wd_i XOR "000000000001" when (syndrome = "0001") else -- flip wd_i(0)
             wd_i XOR "000000000010" when (syndrome = "0010") else -- flip wd_i(1)
             wd_i XOR "000000000100" when (syndrome = "0011") else -- flip wd_i(2)
             wd_i XOR "000000001000" when (syndrome = "0100") else -- flip wd_i(3)
             wd_i XOR "000000010000" when (syndrome = "0101") else -- flip wd_i(4)
             wd_i XOR "000000100000" when (syndrome = "0110") else -- flip wd_i(5)
             wd_i XOR "000001000000" when (syndrome = "0111") else -- flip wd_i(6)
             wd_i XOR "000010000000" when (syndrome = "1000") else -- flip wd_i(7)
             wd_i XOR "000100000000" when (syndrome = "1001") else -- flip wd_i(8)
             wd_i XOR "001000000000" when (syndrome = "1010") else -- flip wd_i(9)
             wd_i XOR "010000000000" when (syndrome = "1011") else -- flip wd_i(10)
             wd_i XOR "100000000000" when (syndrome = "1100") else -- flip wd_i(11)
             wd_i;

corr_bit_o <= '1' when (syndrome /= "0000") else '0';
uncorr     <= '0'; -- can't detect double-bit errors without checking par_i

-- Corrected word
dec_o <= corr_data(11) & corr_data(10) & corr_data(9) & corr_data(8) & corr_data(6) & corr_data(5) & corr_data(4) & corr_data(2);


end Behavioral;
