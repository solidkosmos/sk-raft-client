----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: bscan_adder_top
-- Description: JTAG/BSCAN-driven adder -- two BSCAN write channels feed a single adder
-- and a TMR adder, the single adder sum is read back third through channel 3, 
-- TMRs result through channel 4.
-- 
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

use work.examples_utilities_pkg.all;

entity bscan_adder_top is
  Generic (
    op_len : integer range 1 to 32 := 4 -- The length in bits of each additive number (default 4 bits)
  );
  Port ( 
    data_o : out std_ulogic_vector(15 downto 0) -- The results of the additions
  );
end bscan_adder_top;

architecture Structure of bscan_adder_top is
    
    attribute keep_hierarchy : string;
    attribute keep_hierarchy of tmr_add, sngl_add : label is "TRUE";
    
    -- BSCAN Write data path (USER1 Single Adder Operands, 
    -- USER2 TMR Adder operands), write the numbers to be added 
    -- HI (7 : 4) - Op B / LO (3 : 0) - Op A 
    signal bscan_sngl_adder_ops : std_ulogic_vector(op_len * 2 - 1 downto 0);
    signal bscan_tmr_adder_ops  : std_ulogic_vector(op_len * 2 - 1 downto 0); 
    
    type bscan_result_interface is record
        data_to_jtag    : std_ulogic_vector(op_len downto 0); -- +1 length to account the carry bit overflow
--        data_from_jtag  : std_ulogic_vector(op_len - 1 downto 0); 
--        avail           : std_ulogic;        
--        ack             : std_ulogic; 
    end record;  
    
    -- BSCAN Read data path (USER3, USER4), 
    -- read the result of single adder through USER3, 
    -- TMR adder through USER4
    type readers is array (positive range 3 to 4)
        of std_ulogic_vector(op_len downto 0); -- +1 length to account for the carry bit overflow
    signal bscan_reader : readers;
    
    -- The result signal of the addition
    signal result_single_sig, result_tmr_sig :  unsigned(op_len downto 0);

    -- bscan_interface is declared in examples_utilities_pkg (see use clause above)
    
    signal min_vote_sig   : std_ulogic_vector(2 downto 0);
    signal total_fail_sig : std_ulogic;

begin

    -- BSCAN USER1 : Write a number to be added
    bscan_u1_1st_operand:bscan_interface
      Generic map (
        jtag_chain => 1,          --USER1
        data_len_r => 1, 
        data_len_w => op_len * 2,   
        sync       => false       -- No need for CDC handling
      )
      Port map (
      ----- CLK INPUT FOR CDC HANDLING (unused for this example) -----
        clk_i => '0',
      ----- TCK/DRCK OUTPUTS (unused for this example) -----
        tck_o => open,
        drck_o => open,
      ----- DATA PATH ( ONLY WRITE A NUMBER )-----
        data_to_jtag_i   => (others => '0'),
        data_from_jtag_o => bscan_sngl_adder_ops,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
      
    -- BSCAN USER2 : Write a number to be added
    bscan_u2_2nd_operand:bscan_interface
      Generic map (
        jtag_chain => 2,          --USER2
        data_len_r => 1, 
        data_len_w => op_len * 2,   
        sync       => false       -- No need for CDC handling
      )
      Port map (
      ----- CLK INPUT FOR CDC HANDLING (unused for this example) -----
        clk_i => '0',
      ----- TCK/DRCK OUTPUTS (unused for this example) -----
        tck_o => open,
        drck_o => open,
      ----- DATA PATH (only write) -----
        data_to_jtag_i   => (others => '0'),
        data_from_jtag_o => bscan_tmr_adder_ops,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
    
    -- BSCAN USER3 : Read the result of the single voter 
    bscan_u3_single_adder:bscan_interface
      Generic map (
        jtag_chain => 3,          --USER3
        data_len_r => op_len + 1, 
        data_len_w => 1,   
        sync       => false       -- No need for CDC handling
      )
      Port map (
      ----- CLK INPUT FOR CDC HANDLING (unused for this example) -----
        clk_i => '0',
      ----- TCK/DRCK OUTPUTS (unused for this example) -----
        tck_o => open,
        drck_o => open,
      ----- DATA PATH ( ONLY READ RESULT ) -----
        data_to_jtag_i   => bscan_reader(3),
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
    
    -- BSCAN USER4 : Read the result of the TMR voter 
    bscan_u4_tmr_adder:bscan_interface
      Generic map (
        jtag_chain => 4,          --USER4
        data_len_r => op_len + 1, 
        data_len_w => 1,   
        sync       => false       -- No need for CDC handling
      )
      Port map (
      ----- CLK INPUT FOR CDC HANDLING (unused for this example) -----
        clk_i => '0',
      ----- TCK/DRCK OUTPUTS (unused for this example) -----
        tck_o => open,
        drck_o => open,
      ----- DATA PATH ( ONLY READ RESULT ) -----
        data_to_jtag_i   =>  bscan_reader(4),
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
    
    sngl_add:entity work.single_adder
      Generic map (
        op_len => op_len
      )
      Port map ( 
        op_a_i =>  bscan_sngl_adder_ops(op_len - 1 downto 0), -- LO Op A
        op_b_i =>  bscan_sngl_adder_ops(op_len * 2 - 1 downto op_len), -- HI Op B 
        res_o  =>  bscan_reader(3)  
      );
      
    tmr_add:entity work.tmr_adder
      Generic map (
        op_len => op_len
      )
      Port map ( 
        op_a_i =>  bscan_tmr_adder_ops(op_len - 1 downto 0),
        op_b_i =>  bscan_tmr_adder_ops(op_len * 2 - 1 downto op_len),
        res_o  =>  bscan_reader(4),
        min_vote_o   => min_vote_sig,
        total_fail_o => total_fail_sig
      );
    
    data_o <=   total_fail_sig & min_vote_sig & (11 downto 10 => '0') & bscan_reader(4) & bscan_reader(3);

end Structure;
