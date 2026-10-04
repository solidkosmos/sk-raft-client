--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: secded_enc8b
-- Description: 8-bit Hamming SEC encoder. It calculates 4 Hamming parity
--              bits from 8 data bits. It also calculates an overall (DED)
--              parity bit (ded_par_o) to extend the code to SECDED.
--------------------------------------------------------------------------------



library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity secded_enc8b is
  Generic(
    data_len     : integer := 8;
    parities_len : integer := 4
  );
  Port ( 
    data_i    : in std_ulogic_vector(data_len - 1 downto 0);
    par_o     : out std_ulogic_vector(parities_len - 1 downto 0);
    ded_par_o : out std_ulogic
  );
end secded_enc8b;

architecture Behavioral of secded_enc8b is

    signal ecc_par : std_ulogic_vector(parities_len - 1 downto 0);

    signal encoded_word :
        std_ulogic_vector((data_len + parities_len - 1) downto 0);

begin

    ecc_par(0) <= data_i(0) XOR data_i(1) XOR data_i(3) XOR data_i(4)
                  XOR data_i(6);
    ecc_par(1) <= data_i(0) XOR data_i(2) XOR data_i(3) XOR data_i(5)
                  XOR data_i(6);
    ecc_par(2) <= data_i(1) XOR data_i(2) XOR data_i(3) XOR data_i(7);
    ecc_par(3) <= data_i(4) XOR data_i(5) XOR data_i(6) XOR data_i(7);

    encoded_word <= data_i & ecc_par;

    ded_parity_gen:process(encoded_word)
        variable vpar : std_ulogic;
        begin
            vpar := '0';
            for i in 0 to (data_len + parities_len - 1) loop
                -- Parity generation for double-error detection
                vpar := vpar XOR encoded_word(i);
            end loop;

            ded_par_o <= vpar;
    end process ded_parity_gen;

    par_o <= ecc_par;

end Behavioral;
