--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: ff_lut_top
-- Description: An FF shift register that operates continuously (JTAG
--              controls its clock gate) and an address-mapped LUTRAM. JTAG
--              controls and reads both through BSCAN.
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity ff_lut_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS". The value goes directly
    -- to clk_gen_wrapper.
    g_family       : string  := "7SERIES";
    -- The length of the shift register (8 bits by default)
    sr_len         : integer range 4 to 256 := 8;
    -- The data length of each LUTRAM word (32 bits by default)
    lut_data_len   : integer range 1 to 256 := 32;
    -- Half period of the shift clock in ms (for all clk_freq values). The
    -- shift register shifts every 2 x shift_interval ms (200 ms by default).
    shift_interval : integer range 1 to 100 := 100;
    -- The clock frequency in MHz, to make the time intervals accurate
    -- (100 MHz by default)
    clk_freq       : integer range 1 to 400 := 100
  );
  Port (
    clk_i  : in std_ulogic;
    -- Bits 3:0 of the FF shift register (sr_len is 8 by default)
    data_o : out std_ulogic_vector(3 downto 0)
  );
end ff_lut_top;

architecture Behavioral of ff_lut_top is

    -- This function finds the minimum number of
    -- bits that is necessary to address the full
    -- depth of the memory array.
    function clog2(depth : positive) return natural is
        variable bits : natural := 0;
        variable val  : natural := 1;
    begin
        while val < depth loop
            val  := val * 2;
            bits := bits + 1;
        end loop;
        return bits;
    end function;

    constant time_interval : integer := shift_interval * clk_freq * 1000;

    signal safe_clk, buf_safe_clk : std_ulogic := '0';
    
    signal clk_en, clk_en_d0, clk_en_sync : std_ulogic := '0';

    -- FF Shift Register 
	signal ff_sr          : std_ulogic_vector(sr_len - 1 downto 0);
	-- div_clk - gated shift clock
	signal div_clk : std_ulogic := '0';
	-- sr_ce is the pulse that shifts the SR
	signal sr_ce                  : std_ulogic := '0';

	constant shift_period : integer := 2 * time_interval; 
	signal counter        : integer range 0 to shift_period - 1 := 0;
    
    -- LUTRAM
    constant lut_mem_depth : natural := 64;
    constant addr_width    : natural := clog2(lut_mem_depth);
    signal addr_sel : natural range 0 to lut_mem_depth - 1;
    signal wr_en    : std_ulogic := '0';
    
    -- Interface signals of the BSCAN registers

    -- BSCAN USER 1 : CLOCK ENABLE ---------------------
    type bscan_clk_en_interfacing is record
        -- JTAG reads back the clock-enable state.
        data_to_jtag   : std_ulogic_vector(0 downto 0);
        -- JTAG writes this bit to enable or disable the clock.
        data_from_jtag : std_ulogic_vector(0 downto 0);
    end record bscan_clk_en_interfacing;

    -- BSCAN USER 2 : READ SHIFT REGISTER ---------------------
    type bscan_sr_read_interfacing is record
        -- JTAG reads back the shift register state (read-only channel).
        data_to_jtag : std_ulogic_vector(sr_len - 1 downto 0);
    end record bscan_sr_read_interfacing;

	-- BSCAN USER 3 : ADDRESS SELECT ---------------------
	type bscan_addr_interfacing is record
		-- JTAG reads back the selected address.
		data_to_jtag   : std_ulogic_vector(addr_width - 1 downto 0);
		-- JTAG writes this value to select the address. The _sync copy is
		-- the same value, latched in the buf_safe_clk domain.
		data_from_jtag, data_from_jtag_sync :
			std_ulogic_vector(addr_width - 1 downto 0);
		-- New address available. The signal goes to 1 when JTAG writes a new
		-- address.
		avail          : std_ulogic;
		avail_prev     : std_ulogic;
	end record bscan_addr_interfacing;

    -- BSCAN USER 4 : READ/WRITE DATA ---------------------
    type bscan_lut_data_interfacing is record
        -- JTAG reads back the data in the selected address.
        data_to_jtag   : std_ulogic_vector(lut_data_len - 1 downto 0);
        -- JTAG writes the data into the selected address.
        data_from_jtag : std_ulogic_vector(lut_data_len - 1 downto 0);
        -- New data word available. The signal goes to 1 when JTAG
        -- writes a word.
        avail          : std_ulogic;
        avail_prev     : std_ulogic;
    end record bscan_lut_data_interfacing;

    signal bscan_clk_en_user   : bscan_clk_en_interfacing;
    signal bscan_sr_read_user  : bscan_sr_read_interfacing;
    signal bscan_addr_user     : bscan_addr_interfacing;
    signal bscan_lut_data_user : bscan_lut_data_interfacing;
    

    -- Each sr_module instance makes a circular shift register that operates
    -- continuously.
    component sr_module is
      Generic (
        mass_bit_count : integer range 0 to 512 := 8
      );
      Port ( 
        clk_i   : in std_ulogic;
        data_o  : out std_ulogic_vector(mass_bit_count - 1 downto 0)
      ); 
    end component;

    -- The examples_utilities_pkg package declares clk_gen_wrapper and
    -- bscan_interface (see the use clause above). Only sr_module and
    -- lut_memory_array have local declarations here.

    component lut_memory_array is
      Generic (
        mem_depth  : natural := 10;
        addr_width : natural := 4;
        data_len : natural := 32
      );
      Port ( 
        clk_i  : in std_ulogic;
        addr_i : in natural range 0 to mem_depth - 1;
        wr_en_i: in std_ulogic;
        din_i  : in std_ulogic_vector(data_len - 1 downto 0);
        dout_o : out std_ulogic_vector(data_len - 1 downto 0)
      );
    end component;

begin

    -- Send the input clock through the portable PLL wrapper. The period (ns)
    -- comes directly from clk_freq (MHz). Thus clk_freq is the only source
    -- for the clock frequency of the design.
    clk_gen_inst : clk_gen_wrapper
      Generic map (
        g_family          => g_family,
        g_clkin_period_ns => 1000.0 / real(clk_freq)
      )
      Port map (
        clk_i  => clk_i,
        clk_o => safe_clk,
        locked_o => open
      );
    
    -- BSCAN U1 : CLOCK ENABLE/DISABLE
    bscan_u1_clk_en:bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => 1,
        data_len_w => 1, -- 1 bit for the clock enable
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CDC -----
        clk_i => '0',
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => bscan_clk_en_user.data_to_jtag,
        data_from_jtag_o => bscan_clk_en_user.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o  => open,      
        ux_ack_o    => open    
      );
      
    clk_en <= bscan_clk_en_user.data_from_jtag(0);
     
    -- Synchronize the clock-enable signal with two flip-flops. clk_en comes
    -- from the TCK domain. The two flip-flops synchronize it to safe_clk
    -- to prevent metastability.
    sync_clk_en:process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            clk_en_d0   <= clk_en; 
            clk_en_sync <= clk_en_d0;
        end if;
    end process sync_clk_en;
    
    bscan_clk_en_user.data_to_jtag(0) <= clk_en_sync;
        
    BUFGCE_inst : BUFGCE
        Port map (
           O => buf_safe_clk,   -- 1-bit output: Clock output
           CE => clk_en_sync, -- 1-bit input: Clock enable input for I0
           I => safe_clk    -- 1-bit input: Primary clock
        );
      
    -- FF SHIFT REGISTER ------------------------------------------------------
    
	-- The divider uses the gated clock. Thus it stops when JTAG sets clk_en
	-- to 0.
	-- sr_ce is a registered one-cycle pulse every shift_period cycles.
	div_proc : process(buf_safe_clk)
	begin
		if rising_edge(buf_safe_clk) then
			if counter = shift_period - 1 then
				counter <= 0;
				sr_ce   <= '1';
			else
				counter <= counter + 1;
				sr_ce   <= '0';
			end if;
		end if;
	end process div_proc;

	-- Shift clock: buf_safe_clk goes through only when sr_ce is 1.
	-- buf_safe_clk itself stops when clk_en is 0.
	BUFGCE_sr : BUFGCE
		Port map (
		   O  => div_clk,
		   CE => sr_ce,
		   I  => buf_safe_clk  
		);

	ff_sr_inst : sr_module
	  Generic map ( mass_bit_count => sr_len )
	  Port map (
		clk_i  => div_clk,
		data_o => ff_sr
	  );
    
    -- BSCAN U2 : READ SR STATE
    bscan_u2_read_sr:bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => sr_len,
        data_len_w => sr_len, -- not used
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CDC -----
        clk_i => '0',
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => bscan_sr_read_user.data_to_jtag, 
        data_from_jtag_o => open,
      ----- CONTROL SIGNALS ------
        ux_avail_o  => open,      
        ux_ack_o    => open    
      );
     
     bscan_sr_read_user.data_to_jtag <= ff_sr;
     
 --------------------------------------------------------------------------

    -- LUTRAM ----------------------------------------------------------------
    -- BSCAN USER3 : ADDRESS SELECT FOR THE LUTRAM
	bscan_u3_lut_ram_address:bscan_interface
	  Generic map (
		jtag_chain => 3,
		data_len_r => addr_width,
		data_len_w => addr_width,
		-- Synchronize avail and ack to buf_safe_clk with two flip-flops
		sync       => true
	  )
	  Port map (
	  ----- CLK INPUT FOR CDC -----
		clk_i => buf_safe_clk,
	  ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
		tck_o => open,
	  ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
		drck_o => open,
	  ----- DATA PATH -----
		data_to_jtag_i   => bscan_addr_user.data_to_jtag,
		data_from_jtag_o => bscan_addr_user.data_from_jtag,
	  ----- CONTROL SIGNALS ------
		ux_avail_o  => bscan_addr_user.avail,
		ux_ack_o    => open
	  );
	  
	  
    -- BSCAN USER4 : READ/WRITE TO THE LUTRAM
    bscan_u4_lut_ram_data:bscan_interface
      Generic map (
        jtag_chain => 4,
        data_len_r => lut_data_len,
        data_len_w => lut_data_len, -- lut_data_len bits for the data
        -- Synchronize avail and ack to buf_safe_clk with two flip-flops
        sync       => true
      )
      Port map ( 
      ----- CLK INPUT FOR CDC -----
        clk_i => buf_safe_clk,
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => bscan_lut_data_user.data_to_jtag,
        data_from_jtag_o => bscan_lut_data_user.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o  => bscan_lut_data_user.avail,      
        ux_ack_o    => open    
      );

    -- Generate the CDC control for the address interface. This process
	-- captures the address in the buf_safe_clk domain on the rising edge of
	-- avail, so the LUTRAM only sees a value that is stable.
	cdc_addr:process(buf_safe_clk)
	begin
		if rising_edge(buf_safe_clk) then
			bscan_addr_user.avail_prev <= bscan_addr_user.avail;
			if bscan_addr_user.avail = '1'
			   and bscan_addr_user.avail_prev = '0' then
				bscan_addr_user.data_from_jtag_sync <=
					bscan_addr_user.data_from_jtag;
			end if;
		end if;
	end process cdc_addr;

	addr_sel <= to_integer(unsigned(bscan_addr_user.data_from_jtag_sync));
	-- Simple feedback path for debug
    bscan_addr_user.data_to_jtag <=
        std_ulogic_vector(to_unsigned(addr_sel, addr_width));
    
    -- This logic uses the same gated clock as the FF shift register path.
    -- For fault injection, all downstream fabric logic stops when clk_en is
    -- 0, not only the main demo logic. Apply this clock gate to the
    -- peripheral logic of every example. Do this even if the example is
    -- safe without it.
    sample_avail:process(buf_safe_clk)
    begin
        if rising_edge(buf_safe_clk) then
            bscan_lut_data_user.avail_prev <= bscan_lut_data_user.avail;
        end if;
    end process sample_avail;

    -- Write-enable signal for the LUTRAM.
    -- A single strobe in the buf_safe_clk domain (the gated safe_clk).
    wr_en <= '1' when bscan_lut_data_user.avail = '1'
                  and bscan_lut_data_user.avail_prev = '0' else
             '0';

    LUTRAM:lut_memory_array
      Generic map (
        mem_depth   => lut_mem_depth,
        addr_width  => addr_width,
        data_len  => lut_data_len
      )
      Port map ( 
        clk_i   => buf_safe_clk     ,
        addr_i  => addr_sel         ,
        wr_en_i => wr_en            ,
        din_i   => bscan_lut_data_user.data_from_jtag,
        dout_o  => bscan_lut_data_user.data_to_jtag
      );
    
        
    data_o <= ff_sr(3 downto 0);

end Behavioral;