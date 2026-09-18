----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: vec_tmr_voter
-- Description: Combinational majority-vote TMR voter for vectors -- outputs the bitwise majority of
--              3 same-width inputs, plus minority-recovery and total-failure status flags.
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

entity vec_tmr_voter is
  Generic ( data_len : integer := 32
  );
  Port ( din_0 : in std_ulogic_vector(data_len-1 downto 0);
         din_1 : in std_ulogic_vector(data_len-1 downto 0);
         din_2 : in std_ulogic_vector(data_len-1 downto 0);
         dout  : out std_ulogic_vector(data_len-1 downto 0);
		 --control signals for recovery or total failure
		 min_vote : out std_ulogic_vector(2 downto 0);
		 total_fail : out std_ulogic --only available on vectored voting 
  );
end vec_tmr_voter;

architecture Behavioral of vec_tmr_voter is

begin

-- MAJORITY OTING LOGIC 
dout <=(din_0 and din_1) or (din_1 and din_2) or (din_0 and din_2);

--MINORITY VOTING LOGIC
min_vote(0) <= '1' when (din_0 /= din_1) and (din_0 /= din_2) and (din_1 = din_2) else '0'; 
min_vote(1) <= '1' when (din_1 /= din_0) and (din_1 /= din_2) and (din_0 = din_2) else '0'; 
min_vote(2) <= '1' when (din_2 /= din_0) and (din_2 /= din_1) and (din_0 = din_1) else '0';

total_fail <= '1' when (din_0 /= din_1) and (din_1 /= din_2) and (din_0 /= din_2) else
			  '0';
 
end Behavioral;
