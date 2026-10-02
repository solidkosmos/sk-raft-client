--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: tmr_adder
-- Description: Triple-instantiated adder (3x adder, dont_touch/keep_hierarchy
--              protected) feeding a vec_tmr_voter majority vote -- TMR-hardened
--              counterpart to single_adder for A/B fault-injection comparison.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity tmr_adder is
  Generic (
    op_len : positive
  );
  Port ( 
    op_a_i : in std_ulogic_vector(op_len - 1 downto 0);
    op_b_i : in std_ulogic_vector(op_len - 1 downto 0);
    res_o  : out std_ulogic_vector(op_len downto 0);
    min_vote_o   : out std_ulogic_vector(2 downto 0);
    total_fail_o : out std_ulogic
  );
end tmr_adder;

architecture Structure of tmr_adder is

    type results is array (natural range 0 to 2)
        of std_ulogic_vector(op_len downto 0);
    signal res_sig : results;
    
    attribute dont_touch : string;
    attribute dont_touch of res_sig: signal is "TRUE";
    
    attribute keep_hierarchy : string;
    attribute keep_hierarchy of gen_adders : label is "TRUE";
    
    component adder is
      Generic (
        op_len : positive
      );
      Port ( 
        op_a_i : in std_ulogic_vector(op_len - 1 downto 0);
        op_b_i : in std_ulogic_vector(op_len - 1 downto 0);
        res_o  : out std_ulogic_vector(op_len downto 0)
      );
    end component;
    
    component vec_tmr_voter is
      Generic ( data_len : integer := 32
      );
      Port ( din_0_i : in std_ulogic_vector(data_len-1 downto 0);
             din_1_i : in std_ulogic_vector(data_len-1 downto 0);
             din_2_i : in std_ulogic_vector(data_len-1 downto 0);
             dout_o  : out std_ulogic_vector(data_len-1 downto 0);
             --control signals for recovery or total failure
             min_vote_o : out std_ulogic_vector(2 downto 0);
             total_fail_o : out std_ulogic --only available on vectored voting 
      );
    end component;
    
    
begin

    gen_adders:for i in 0 to 2 generate
        attribute dont_touch of add : label is "TRUE";
        begin 
            add:adder
              Generic map (
                op_len => op_len
              )
              Port map ( 
                op_a_i => op_a_i,
                op_b_i => op_b_i,
                res_o  => res_sig(i)  
              );
    end generate;
    
    tmr_vote:vec_tmr_voter
      Generic map ( 
        data_len => op_len + 1
      )
      Port map ( 
        din_0_i => res_sig(0),  
        din_1_i => res_sig(1),  
        din_2_i => res_sig(2),  
        dout_o  => res_o     ,
        --control signals for recovery or total failure
        min_vote_o   => min_vote_o,
        total_fail_o => total_fail_o
      );
    

end Structure;
