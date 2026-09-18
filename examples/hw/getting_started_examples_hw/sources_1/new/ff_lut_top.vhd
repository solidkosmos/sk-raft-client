----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: ff_lut_top
-- Description: Free-running FF shift register (JTAG clock-gated) and an address-mapped LUTRAM, both driven over BSCAN.
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity ff_lut_top is
  Generic (
    g_family       : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
    sr_len         : integer range 1 to 256 := 8;  -- The lengths of the shift registers, 8 bits by default
    lut_data_len   : integer range 1 to 256 := 32;  -- The data length of each LUT data, 4 bits default (2 memory elements = 8 LUTRAMS)
    shift_interval : integer range 1 to 100 := 100; -- Shift every X ms for 100 MHz clock (1000 ms => 1 s)
    clk_freq       : integer range 1 to 400 := 100   -- Set the clock frequency to make the intervals time accurate (default 100MHz)
  );
  Port (
    clk_i  : in std_ulogic;
    data_o : out std_ulogic_vector(15 downto 0) -- 8 leds for the FF SR, 8 for the LUT SR
  );
end ff_lut_top;

architecture Behavioral of ff_lut_top is

    -- Function to find the least amount of 
    -- required bits to address the whole 
    -- memory array depth
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

    signal safe_clk, buf_safe_clk, div_clk : std_ulogic := '0';
    
    signal clk_en, clk_en_d0, clk_en_sync : std_ulogic := '0'; 
    
    signal locked_sig : std_ulogic;
    
    -- FF Shift Register 
    signal ff_sr    : std_ulogic_vector(sr_len - 1 downto 0);
    signal counter  : integer range 0 to time_interval - 1 := 0;
    
    -- LUT RAM 
    constant lut_mem_depth : natural := 10;
    constant addr_width    : natural := clog2(lut_mem_depth); -- 2 bits for depth=4
    signal addr_sel : natural range 0 to lut_mem_depth - 1;
    signal wr_en    : std_ulogic := '0';
    type lut_memory is array (0 to lut_mem_depth - 1) of std_ulogic_vector(lut_data_len - 1 downto 0);
    signal lut_mem : lut_memory;
    
    attribute ram_style : string;
    attribute ram_style of lut_mem : signal is "distributed";
    
    -- Setting the interfacing signals of BSCAN

    -- BSCAN USER 1 : CLOCK ENABLE ---------------------
    type bscan_clk_en_interfacing is record
        data_to_jtag   : std_ulogic_vector(0 downto 0); -- read back the clock-enable state
        data_from_jtag : std_ulogic_vector(0 downto 0); -- write to enable/disable the clock
    end record bscan_clk_en_interfacing;

    -- BSCAN USER 2 : READ SHIFT REGISTER ---------------------
    type bscan_sr_read_interfacing is record
        data_to_jtag : std_ulogic_vector(sr_len - 1 downto 0); -- read back the shift register state (read-only channel)
    end record bscan_sr_read_interfacing;

    -- BSCAN USER 3 : ADDRESS SELECT ---------------------
    type bscan_addr_interfacing is record
        data_to_jtag   : std_ulogic_vector(addr_width - 1 downto 0); -- read back the currently selected address
        data_from_jtag : std_ulogic_vector(addr_width - 1 downto 0); -- write to select the address
    end record bscan_addr_interfacing;

    -- BSCAN USER 4 : READ/WRITE DATA ---------------------
    type bscan_lut_data_interfacing is record
        data_to_jtag   : std_ulogic_vector(lut_data_len - 1 downto 0); -- read back the data residing in the selected address
        data_from_jtag : std_ulogic_vector(lut_data_len - 1 downto 0); -- write data into the selected address
        avail          : std_ulogic; -- new data word available, pulses when a word is explicitly written
        avail_prev     : std_ulogic;
    end record bscan_lut_data_interfacing;

    signal bscan_clk_en_user   : bscan_clk_en_interfacing;
    signal bscan_sr_read_user  : bscan_sr_read_interfacing;
    signal bscan_addr_user     : bscan_addr_interfacing;
    signal bscan_lut_data_user : bscan_lut_data_interfacing;
    

    -- Each sr_module instance generates a free-running, loop-around shift register
    component sr_module is
      Generic (
        mass_bit_count : integer range 0 to 512 := 8
      );
      Port ( 
        clk_i   : in std_ulogic;
        data_o  : out std_ulogic_vector(mass_bit_count - 1 downto 0)
      ); 
    end component;

    -- clk_gen_wrapper and bscan_interface are declared in examples_utilities_pkg
    -- (see use clause above); only sr_module and lut_memory_array stay local here.

    component lut_memory_array is
      Generic (
        mem_depth  : natural := 10;
        addr_width : natural := 4;
        data_len : natural := 32
      );
      Port ( 
        clk_i  : in std_logic;
        addr_i : in natural range 0 to mem_depth - 1;
        wr_en_i: in std_ulogic;
        din_i  : in std_ulogic_vector(data_len - 1 downto 0);
        dout_o : out std_ulogic_vector(data_len - 1 downto 0)
      );
    end component;

begin

    -- Condition the incoming clock through the portable PLL wrapper. Period
    -- (ns) is derived straight from clk_freq (MHz) so there's only one
    -- source of truth for the design's operating frequency.
    clk_gen_inst : clk_gen_wrapper
      generic map (
        g_family          => g_family,
        g_clkin_period_ns => 1000.0 / real(clk_freq)
      )
      port map (
        clk_i  => clk_i,
        clk_o => safe_clk,
        locked_o => locked_sig
      );
    
    -- BSCAN U1 : CLOCK ENABLE/DISABLE
    bscan_u1_clk_en:bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => 1,
        data_len_w => 1, -- addr_width bits for the address + 1 write enable
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CDC HANDLING -----
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
     
    -- Double flop to synchronize the clock gating 
    sync_clk_en:process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            clk_en_d0   <= clk_en; 
            clk_en_sync <= clk_en_d0;
        end if;
    end process sync_clk_en;
    
    bscan_clk_en_user.data_to_jtag(0) <= clk_en_sync;
        
    BUFGCE_inst : BUFGCE
        port map (
           O => buf_safe_clk,   -- 1-bit output: Clock output
           CE => clk_en_sync, -- 1-bit input: Clock enable input for I0
           I => safe_clk    -- 1-bit input: Primary clock
        );
      
    -- FF SHIFT REGISTER -------------------------------------------------------
    
    -- Feed the gated clock into the divider to freeze intervals
    -- Divider: produces one shift_en pulse every time_interval clk cycles
    div_proc : process(buf_safe_clk)
    begin
        if rising_edge(buf_safe_clk) then
            if counter = time_interval - 1 then
                counter  <= 0;
                div_clk  <= not div_clk;
            else
                counter  <= counter + 1; -- Incement 
            end if;
        end if;
    end process div_proc;
    
    ff_sr_inst : sr_module
      generic map ( 
        mass_bit_count => sr_len
      ) 
      port map ( 
        clk_i      => div_clk,
        data_o     => ff_sr 
      );
    
    -- BSCAN U2 : READ SR STATE
    bscan_u2_read_sr:bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => sr_len,
        data_len_w => sr_len, -- unused
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CDC HANDLING -----
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
     
 -------------------------------------------------------------------------------------------------------
    
    -- LUT RAM ---------------------------------------------------------------
    -- BSCAN USER3 : ADDRESS SELECT AND WRITE ENABLE TO LUTRAMS
    bscan_u3_lut_ram_address:bscan_interface
      Generic map (
        jtag_chain => 3,
        data_len_r => addr_width,
        data_len_w => addr_width, -- addr_width bits for the address + 1 write enable
        sync       => false
      )
      Port map ( 
      ----- CLK INPUT FOR CDC HANDLING -----
        clk_i => '0',
      ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o => open,
      ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o => open,
      ----- DATA PATH -----
        data_to_jtag_i   => bscan_addr_user.data_to_jtag,
        data_from_jtag_o => bscan_addr_user.data_from_jtag,
      ----- CONTROL SIGNALS ------
        ux_avail_o  => open,      
        ux_ack_o    => open    
      );
      
    -- BSCAN USER4 :READ/WRITE TO LUTRAMS
    bscan_u4_lut_ram_data:bscan_interface
      Generic map (
        jtag_chain => 4,
        data_len_r => lut_data_len,
        data_len_w => lut_data_len, -- lut_data_len bits for the data
        sync       => true          -- sync the control signals on the clk_i (double flopped)
      )
      Port map ( 
      ----- CLK INPUT FOR CDC HANDLING -----
        clk_i => safe_clk,
      ----- TCK OUTPUT FOR CDC -----
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

    -- Address and data r/w are on different domains but they never collide, each operation occurs sequentially in this example
    
    addr_sel <= to_integer(unsigned(bscan_addr_user.data_from_jtag(addr_width - 1 downto 0)));         
    bscan_addr_user.data_to_jtag <= std_ulogic_vector(to_unsigned(addr_sel, addr_width));
    
    sample_avail:process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            bscan_lut_data_user.avail_prev <= bscan_lut_data_user.avail;
        end if;
    end process sample_avail;

    -- Write enable signal for the LUT Mem array
    wr_en <= '1' when bscan_lut_data_user.avail = '1' and bscan_lut_data_user.avail_prev = '0' else -- Single strobe based on the safe_clk domain 
             '0';

    LUTRAM:lut_memory_array
      Generic map (
        mem_depth   => lut_mem_depth,
        addr_width  => addr_width,
        data_len  => lut_data_len
      )
      Port map ( 
        clk_i   => safe_clk         ,
        addr_i  => addr_sel         ,
        wr_en_i => wr_en            ,
        din_i   => bscan_lut_data_user.data_from_jtag,
        dout_o  => bscan_lut_data_user.data_to_jtag
      );
    
        
    data_o <= ff_sr & bscan_lut_data_user.data_to_jtag(7 downto 0);

end Behavioral;