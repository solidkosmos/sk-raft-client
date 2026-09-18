----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: dsp_target_top
-- Description: Two identical DSP48-multiplier instances (clean reference vs. fault-injection target),
--              each fed its own JTAG/BSCAN operand-write channel (USER1 for the clean instance, USER2
--              for the target) -- write the same operand pair to both for a valid A/B comparison, the
--              design no longer forces them to match. Each result is read back over its own channel.
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

use work.examples_utilities_pkg.all;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

-- Uncomment the following library declaration if instantiating
-- any Xilinx leaf cells in this code.
--library UNISIM;
--use UNISIM.VComponents.all;

entity dsp_target_top is
  Generic (
    g_family : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
    clk_freq : integer range 1 to 400 := 100;   -- Set the clock frequency to set PLL parameters for proper passthrough clock
    a_len : positive := 16; -- Operand A bit length
    b_len : positive := 16  -- Operand B bit length 
  ); 
  Port ( 
    clk_i : in std_ulogic
  );
end dsp_target_top;

architecture Behavioral of dsp_target_top is

    signal safe_clk, locked_sig : std_ulogic;

    -- Setting the interfacing signals of BSCAN 
    type bscan_op_interface is record 
        data_to_jtag   : std_ulogic_vector(a_len + b_len - 1 downto 0);
        data_from_jtag, data_from_jtag_sync : std_ulogic_vector(a_len + b_len  - 1 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_op_interface;
    
    -- (31 : 16) HI is operand B, (15 : 0) LO is operand A 
    signal op_clean_bscan  : bscan_op_interface;
    signal op_target_bscan : bscan_op_interface;
    
    type bscan_result_interface is record 
        data_to_jtag   : std_ulogic_vector(a_len + b_len - 1 downto 0);
        data_from_jtag, data_from_jtag_sync : std_ulogic_vector(a_len + b_len - 1 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_result_interface;
    
    signal res_clean, res_target : bscan_result_interface;
    
    type dsp_ports is record
        a_i : std_ulogic_vector(a_len - 1 downto 0);          -- signed operand A                                   
        b_i : std_ulogic_vector(b_len - 1 downto 0);          -- signed operand B                                   
        p_o : std_ulogic_vector(a_len + b_len - 1 downto 0);  -- signed product, A*B (registered, one clk_i latency)
    end record dsp_ports; 
    
    signal dsp_cln, dsp_trgt : dsp_ports := (a_i => (others => '0'),
                                             b_i => (others => '0'),
                                             p_o => (others => '0'));
    
   
    component dsp_wrapper is
      Generic (
        a_len : positive := 18; -- operand A width -- keep <= 18 bits so this maps onto ONE DSP48 tile on both 7-series (DSP48E1) and UltraScale/UltraScale+ (DSP48E2)
        b_len : positive := 18  -- operand B width -- DSP48E1/E2's B input is 18 bits wide on both families; this is the hard ceiling for a single-tile multiply
      ); 
      Port (
        clk_i : in  std_ulogic;
        ce_i  : in  std_ulogic := '1';                             -- pipeline clock enable, gates the output register
        a_i   : in  std_ulogic_vector(a_len - 1 downto 0);          -- signed operand A
        b_i   : in  std_ulogic_vector(b_len - 1 downto 0);          -- signed operand B
        p_o   : out std_ulogic_vector(a_len + b_len - 1 downto 0)   -- signed product, A*B (registered, one clk_i latency)
      );
    end component;
    
    attribute keep_hierarchy : string;
    attribute keep_hierarchy of dsp_clean, dsp_target : label is "TRUE";
    
begin

    
    safe_pll:clk_gen_wrapper
      Generic map (
        g_family          => g_family,
        g_clkin_period_ns => 1000.0 / real(clk_freq)
      )
      Port map (
        clk_i    => clk_i,
        clk_o    => safe_clk,
        locked_o => locked_sig 
      );
    
    -- BSCAN USER1 : Write CLEAN DSP's operands
    bscan_op_clean_uri:bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => a_len + b_len,
        data_len_w => a_len + b_len,
        sync       => true
      )
      Port map ( 
      ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
        clk_i => safe_clk,
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => op_clean_bscan.data_to_jtag,
        data_from_jtag_o => op_clean_bscan.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o => op_clean_bscan.avail,        
        ux_ack_o   => op_clean_bscan.ack     
      );
    
    -- BSCAN USER2 : Write TARGET DSP's operands
    bscan_op_target_uri:bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => a_len + b_len,
        data_len_w => a_len + b_len,
        sync       => true
      )
      Port map ( 
      ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
        clk_i => safe_clk,
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => op_target_bscan.data_to_jtag,
        data_from_jtag_o => op_target_bscan.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o => op_target_bscan.avail,        
        ux_ack_o   => op_target_bscan.ack     
      );
    
    -- Generate CDC control for the op_clean_bscan and op_target_bscan interfaces 
    cdc_addr:process(safe_clk)
        begin 
            if rising_edge(safe_clk) then
                op_clean_bscan.avail_prev <= op_clean_bscan.avail; 
                op_target_bscan.avail_prev <= op_target_bscan.avail; 
                if op_clean_bscan.avail = '1' and op_clean_bscan.avail_prev = '0' then
                    op_clean_bscan.data_from_jtag_sync <= op_clean_bscan.data_from_jtag;
                end if;
                if op_target_bscan.avail = '1' and op_target_bscan.avail_prev = '0' then
                    op_target_bscan.data_from_jtag_sync <= op_target_bscan.data_from_jtag;
                end if;
            end if;
     end process cdc_addr;
    op_clean_bscan.data_to_jtag <= op_clean_bscan.data_from_jtag_sync; -- Simple feedback for debugging
    op_target_bscan.data_to_jtag <= op_target_bscan.data_from_jtag_sync;
    
    dsp_cln.a_i <= op_clean_bscan.data_from_jtag_sync(a_len - 1 downto 0); -- LO is op a
    dsp_cln.b_i <= op_clean_bscan.data_from_jtag_sync(a_len + b_len - 1 downto a_len); -- HI is op b
    
    dsp_trgt.a_i <= op_target_bscan.data_from_jtag_sync(a_len - 1 downto 0);
    dsp_trgt.b_i <= op_target_bscan.data_from_jtag_sync(a_len + b_len - 1 downto a_len);
    
    dsp_clean:dsp_wrapper
      Generic map (
        a_len => a_len, 
        b_len => b_len 
      )
      Port map (
        clk_i => safe_clk,
        ce_i  => locked_sig ,
        a_i   => dsp_cln.a_i,
        b_i   => dsp_cln.b_i,
        p_o   => dsp_cln.p_o
      );

    dsp_target:dsp_wrapper
      Generic map (
        a_len => a_len, 
        b_len => b_len 
      )
      Port map (
        clk_i => safe_clk,
        ce_i  => locked_sig ,
        a_i   => dsp_trgt.a_i,
        b_i   => dsp_trgt.b_i,
        p_o   => dsp_trgt.p_o
      );
    
    res_clean.data_to_jtag  <= dsp_cln.p_o; 
    res_target.data_to_jtag <= dsp_trgt.p_o;
    
    -- BSCAN USER 3 : Read the result of the clean DSP instance
    bscan_res_clean_uri:bscan_interface
      Generic map (
        jtag_chain => 3,
        data_len_r => a_len + b_len,
        data_len_w => a_len + b_len,
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
        clk_i => '0',
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => res_clean.data_to_jtag,
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS ------
        ux_avail_o => open,        
        ux_ack_o   => open   
      );
    
    -- BSCAN USER 4 : Read the result of the targeted DSP instance
    bscan_res_target_uri:bscan_interface
      Generic map (
        jtag_chain => 4,
        data_len_r => a_len + b_len,
        data_len_w => a_len + b_len,
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
        clk_i => '0',
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => res_target.data_to_jtag,
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS ------
        ux_avail_o => open,        
        ux_ack_o   => open   
      );  
     


end Behavioral;
