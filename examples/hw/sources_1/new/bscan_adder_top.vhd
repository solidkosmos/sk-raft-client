--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: bscan_adder_top
-- Description: JTAG/BSCAN-driven adder -- two BSCAN write channels feed a
-- single adder and a TMR adder, the single adder sum is read back third
-- through channel 3, TMRs result through channel 4.
--
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity bscan_adder_top is
  Generic (
    -- The length in bits of each additive number (default 4 bits)
    op_len : integer range 1 to 32 := 4
  );
  Port (
    data_o : out std_ulogic_vector(3 downto 0) -- total_fail & min_vote(2:0)
  );
end bscan_adder_top;

architecture Structure of bscan_adder_top is

    attribute keep_hierarchy : string;
    attribute keep_hierarchy of tmr_add, sngl_add : label is "TRUE";
    
    -- BSCAN Write data path (USER1), write the numbers to be added 
    -- to both adders
    -- HI (7 : 4) - Op B / LO (3 : 0) - Op A     
    type bscan_ops_interface is record
        data_from_jtag  : std_ulogic_vector(op_len * 2 - 1 downto 0);
    end record;
    signal bscan_adders_ops : bscan_ops_interface;
    
    -- Per the XAPP1086 Isolation Design Flow 
    -- we need to buffer the packed operands 
    -- to two seperate buffers before connecting them 
    -- to the adders, so that they share no connections
    signal sim_ops_buf, tmr_ops_buf :
        std_ulogic_vector(op_len * 2 - 1 downto 0);
    attribute dont_touch of sim_ops_buf, tmr_ops_buf : signal is "TRUE";
    
    -- BSCAN Read data path (USER2, USER3), 
    -- read the result of single adder through USER2, 
    -- TMR adder through USER3
    type bscan_result_interface is record
        -- +1 length to account the carry bit
        data_to_jtag    : std_ulogic_vector(op_len downto 0);
    end record;
    signal bscan_sim_res : bscan_result_interface;
    signal bscan_tmr_res : bscan_result_interface;
    
    -- bscan_interface is declared in examples_utilities_pkg (see use
    -- clause above)
    
    signal min_vote_sig   : std_ulogic_vector(2 downto 0);
    signal total_fail_sig : std_ulogic;

begin

    -- BSCAN USER1 : Write the operands to be added
    bscan_u1_operands:bscan_interface
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
        data_from_jtag_o => bscan_adders_ops.data_from_jtag,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
      
    gen_ops_lut_buf:for i in 0 to op_len * 2 - 1 generate        
        sim_lut_buf_inst : LUT1
            Generic map (
               INIT => "10")
            Port map (
               O => sim_ops_buf(i),   -- LUT general output
               I0 => bscan_adders_ops.data_from_jtag(i)  -- LUT input
            );
        tmr_lut_buf_inst : LUT1
            Generic map (
               INIT => "10")
            Port map (
               O => tmr_ops_buf(i),   -- LUT general output
               I0 => bscan_adders_ops.data_from_jtag(i)  -- LUT input
            );
    end generate gen_ops_lut_buf;
    
    sngl_add:entity work.single_adder
      Generic map (
        op_len => op_len
      )
      Port map ( 
        op_a_i =>  sim_ops_buf(op_len - 1 downto 0), -- LO Op A
        op_b_i =>  sim_ops_buf(op_len * 2 - 1 downto op_len), -- HI Op B 
        res_o  =>  bscan_sim_res.data_to_jtag  
      );
      
    tmr_add:entity work.tmr_adder
      Generic map (
        op_len => op_len
      )
      Port map ( 
        op_a_i =>  tmr_ops_buf(op_len - 1 downto 0),
        op_b_i =>  tmr_ops_buf(op_len * 2 - 1 downto op_len),
        res_o  =>  bscan_tmr_res.data_to_jtag,
        min_vote_o   => min_vote_sig,
        total_fail_o => total_fail_sig
      );
    
    -- BSCAN USER2 : Read the result of the simplex adder 
    bscan_u2_simplex_adder_res:bscan_interface
      Generic map (
        jtag_chain => 2,          --USER2
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
        data_to_jtag_i   => bscan_sim_res.data_to_jtag,
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
    
    -- BSCAN USER3 : Read the result of the TMR voter 
    bscan_u3_tmr_adder_res:bscan_interface
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
        data_to_jtag_i   =>  bscan_tmr_res.data_to_jtag,
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS (unused for this example) ------
        ux_avail_o       => open,
        ux_ack_o         => open
      );
      
    data_o <= total_fail_sig & min_vote_sig;

end Structure;
