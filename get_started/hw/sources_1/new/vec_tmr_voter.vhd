--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: vec_tmr_voter
-- Description: Combinational majority-vote TMR voter for vectors. The output
--              is the bitwise majority of 3 inputs with the same width. The
--              voter also gives minority-recovery and total-failure status
--              flags.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity vec_tmr_voter is
  Generic ( data_len : integer := 32
  );
  Port ( din_0_i : in std_ulogic_vector(data_len-1 downto 0);
         din_1_i : in std_ulogic_vector(data_len-1 downto 0);
         din_2_i : in std_ulogic_vector(data_len-1 downto 0);
         dout_o  : out std_ulogic_vector(data_len-1 downto 0);
         -- Control signals for recovery or total failure
         min_vote_o : out std_ulogic_vector(2 downto 0);
         total_fail_o : out std_ulogic -- Only available in the vector voter
  );
end vec_tmr_voter;

architecture Behavioral of vec_tmr_voter is

begin

-- MAJORITY VOTE LOGIC
dout_o <= (din_0_i and din_1_i) or (din_1_i and din_2_i)
          or (din_0_i and din_2_i);

-- MINORITY VOTE LOGIC
min_vote_o(0) <= '1' when (din_0_i /= din_1_i) and (din_0_i /= din_2_i)
                      and (din_1_i = din_2_i) else '0';
min_vote_o(1) <= '1' when (din_1_i /= din_0_i) and (din_1_i /= din_2_i)
                      and (din_0_i = din_2_i) else '0';
min_vote_o(2) <= '1' when (din_2_i /= din_0_i) and (din_2_i /= din_1_i)
                      and (din_0_i = din_1_i) else '0';

total_fail_o <= '1' when (din_0_i /= din_1_i) and (din_1_i /= din_2_i)
                     and (din_0_i /= din_2_i) else
                '0';
 
end Behavioral;
