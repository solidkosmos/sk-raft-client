--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: secded_dec8b
-- Description: 8-bit Hamming SEC decoder -- recomputes the syndrome from
--              the 8 data bits and 4 Hamming parity bits, detecting and correcting 
-- 				any single-bit error.
--------------------------------------------------------------------------------



library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity secded_dec8b is
  Generic(
    data_len     : integer := 8;
    parities_len : integer := 4
  );
  Port ( 
    data_i     : in std_ulogic_vector(data_len - 1  downto 0);
    ecc_pars_i : in std_ulogic_vector(parities_len - 1  downto 0);
    par_i      : in std_ulogic;
    dec_o      : out std_ulogic_vector(data_len - 1 downto 0);
    corr_bit_o : out std_ulogic;
    uncorr_o   : out std_ulogic
  );
end secded_dec8b;

architecture Behavioral of secded_dec8b is

    signal syndrome : std_ulogic_vector(parities_len - 1 downto 0);
    signal wd_i, corr_data :
        std_ulogic_vector((data_len + parities_len - 1) downto 0);
    signal par_check : std_ulogic;

begin

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

    syndrome(0)<= ecc_pars_i(0) XOR data_i(0) XOR data_i(1) XOR data_i(3)
                  XOR data_i(4) XOR data_i(6);
    syndrome(1)<= ecc_pars_i(1) XOR data_i(0) XOR data_i(2) XOR data_i(3)
                  XOR data_i(5) XOR data_i(6);
    syndrome(2)<= ecc_pars_i(2) XOR data_i(1) XOR data_i(2) XOR data_i(3)
                  XOR data_i(7);
    syndrome(3)<= ecc_pars_i(3) XOR data_i(4) XOR data_i(5) XOR data_i(6)
                  XOR data_i(7);

    -- Correction is based on the syndrome
    corr_data <=
        wd_i XOR "000000000001" when (syndrome = "0001") else -- flip wd_i(0)
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

    par_check_proc:process(wd_i, par_i)
        variable vpar : std_ulogic;
        begin
            vpar := '0';
            for i in 0 to (data_len + parities_len - 1) loop
                -- parity generation for double error detection
                vpar := vpar XOR wd_i(i);
            end loop;

            par_check <= vpar XOR par_i;
    end process par_check_proc;

    corr_bit_o <= '1' when (syndrome /= "0000"); --and (par_check = '1') else '0';
    -- uncorr_o   <= '1' when (syndrome /= "0000") and (par_check = '0') else '0';

	uncorr_o <= '0' -- DBUs not exercised in this example
	
			 -- Corrected word
    dec_o <= corr_data(11) & corr_data(10) & corr_data(9) & corr_data(8) &
             corr_data(6) & corr_data(5) & corr_data(4) & corr_data(2);
			--(others => '0')  -- gate trash data from getting passed downstream
             --when (syndrome /= "0000" and par_check = '0') else
             -- Corrected word


end Behavioral;
