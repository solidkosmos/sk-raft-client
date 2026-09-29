--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: brams_top
-- Description: Stock and ECC Block RAM instances driven over independent
--              JTAG/BSCAN address and data channels, for A/B
--              fault-injection comparison.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity brams_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to
    -- clk_gen_wrapper
    g_family       : string  := "7SERIES";
    -- Set the clock frequency to set PLL parameters for proper
    -- passthrough clock
    clk_freq       : integer range 1 to 400 := 100
  );
  Port (
    clk_i  : in std_ulogic;
    data_o : out std_ulogic_vector(3 downto 0) -- 3 byte ECC-correction flags
  );
end brams_top;

architecture Behavioral of brams_top is

    -- PLL clock, then CE-gated for all downstream fabric
    signal safe_clk, buf_safe_clk : std_ulogic;

    signal clk_en, clk_en_d0, clk_en_sync : std_ulogic := '0';

    constant bram_data_len : integer := 24; -- 3 byte data  
    -- 14:5 (10 bits address reg) are the effective bits in the address
    -- space since we use 32bit width BRAM we have to pad to a power of 8
    -- if the register is >8,
    -- !!! UNSAFE : Be sure to drive the address signal with the
    -- appropriate bounds (MAX 2**9 - 1) otherwise you will be targeting
    -- lower addresses, necessary if we want to access the whole mem
    -- array.
    constant bram_addr_len : integer := 16;
                                        
    -- Setting the interfacing signals of BSCAN 

    -- BSCAN USER 1 : CLOCK ENABLE ---------------------
    type bscan_clk_en_interfacing is record
        -- read back the clock-enable state
        data_to_jtag   : std_ulogic_vector(0 downto 0);
        -- write to enable/disable the clock
        data_from_jtag : std_ulogic_vector(0 downto 0);
    end record bscan_clk_en_interfacing;

    type bscan_address_interfacing is record
        data_to_jtag   : std_ulogic_vector(bram_addr_len - 1 downto 0);
        data_from_jtag, data_from_jtag_sync :
            std_ulogic_vector(bram_addr_len  - 1 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_address_interfacing;
    
    type bscan_data_interfacing is record 
        data_to_jtag   : std_ulogic_vector(bram_data_len - 1 downto 0);
        data_from_jtag, data_from_jtag_sync :
            std_ulogic_vector(bram_data_len - 1 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_data_interfacing;
    
    type bscan_ecc_interfacing is record 
        data_to_jtag   : std_ulogic_vector(0 downto 0);
        data_from_jtag, data_from_jtag_sync : std_ulogic_vector(0 downto 0);
        avail       : std_ulogic;
        avail_prev  : std_ulogic;
        ack         : std_ulogic;
    end record bscan_ecc_interfacing;
    
    
    -- We will utilize all BSCAN USER Registers as such:
    -- BSCAN USER 1 : CLOCK ENABLE (freeze all downstream fabric)  --
    -- BSCAN USER 2 : STOCK BRAM ADDRESS CONTROL                   --
    -- BSCAN USER 3 : STOCK BRAM DATA READ/WRITE                   --
    -- BSCAN USER 4 : ACTIVATE ECC READ                            --
    signal bscan_clk_en_user : bscan_clk_en_interfacing;
    signal bscan_addr_user : bscan_address_interfacing;
    signal bscan_data_user : bscan_data_interfacing;
    signal bscan_ecc_r_en  : bscan_ecc_interfacing;

    -- BRAM CONTROL/DATA SIGNALS --
    signal we   : std_ulogic := '0'; -- write enable
    
    -- 3 bytes with 4 parity bits for each one
    signal bytes_ecc_gen_pars, ecc_pars :
        std_ulogic_vector((3 * 4) - 1  downto 0);
    -- The 3 bytes with their ECC parity bits (3 * 4)
    signal data_to_bram, data_from_bram   :
        std_ulogic_vector((bram_data_len + (3 * 4)) - 1 downto 0);
    signal corr_data : std_ulogic_vector(bram_data_len - 1 downto 0);
    signal stock_data : std_ulogic_vector(bram_data_len - 1 downto 0);
    
    signal corr_bytes : std_ulogic_vector(2 downto 0); -- Corrected byte signal

    -- clk_gen_wrapper, bscan_interface are declared in examples_utilities_pkg
    -- (see use clause above).
    
    -- Simple Dual-Port Block RAM wrapper built from a direct RAMB36E1/E2
    -- primitive instantiation.
    component bram_sdp_native_wrapper is
      Generic (
        -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
        g_family : string := "7SERIES"
      );
      Port (
        clk_i     : in  std_ulogic;
        en_i      : in  std_ulogic;                     -- read-port enable
        we_i      : in  std_ulogic;                     -- write-port enable
        -- 1023-deep at this primitive's 36-bit-wide configuration
        wr_addr_i : in  std_ulogic_vector(9 downto 0);
        rd_addr_i : in  std_ulogic_vector(9 downto 0);
        -- 36 bits are used (24 data bits + 12 ECC parity bits)
        din_i     : in  std_ulogic_vector(35 downto 0);
        dout_o    : out std_ulogic_vector(35 downto 0)
      );
    end component;

    
    component secded_enc8b is
      Generic(
        data_len     : integer := 8;
        parities_len : integer := 4
      );
      Port ( 
        data_i       : in std_ulogic_vector(data_len - 1 downto 0);
        par_o        : out std_ulogic_vector(parities_len - 1 downto 0);
        ded_par_o : out std_ulogic
      );
    end component;

    component secded_dec8b is
      Generic(
        data_len     : integer := 8;
        parities_len : integer := 4
      );
      Port ( 
        data_i      : in std_ulogic_vector(data_len - 1  downto 0);
        ecc_pars_i  : in std_ulogic_vector(parities_len - 1  downto 0);  
        par_i       : in std_ulogic;
        dec_o       : out std_ulogic_vector(data_len - 1 downto 0);
        corr_bit_o  : out std_ulogic;
        uncorr_o    : out std_ulogic
      );
    end component;
    
begin
    
    safe_pll:clk_gen_wrapper
      Generic map (
        g_family          => g_family,
        g_clkin_period_ns => 1000.0 / real(clk_freq)
      )
      Port map (
        clk_i    => clk_i,
        clk_o    => safe_clk,
        locked_o => open
      );

    -- BSCAN U1 : CLOCK ENABLE/DISABLE
    bscan_u1_clk_en:bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => 1,
        data_len_w => 1,
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

    -- For fault injection every piece of downstream fabric freezes on
    -- clk_en, not just the headline demo logic for this example -- apply
    -- this to every example's peripheral logic, regardless of whether
    -- that example's own behaviour would still be safe without it.
    BUFGCE_inst : BUFGCE
        Port map (
           O => buf_safe_clk, -- 1-bit output: Clock output
           CE => clk_en_sync, -- 1-bit input: Clock enable input for I0
           I => safe_clk      -- 1-bit input: Primary clock
        );
    
    -- Instantiate BSCAN USER 2 Registers and interface for address control
    bscan_u2_addr_uri:bscan_interface
        Generic map (
          jtag_chain => 2,
          data_len_r => bram_addr_len,
          data_len_w => bram_addr_len,
          sync       => true
        )
        Port map ( 
        ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
          clk_i => buf_safe_clk,
        ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
          tck_o => open,
        ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
          drck_o => open,
        ----- DATA PATH -----
          data_to_jtag_i   => bscan_addr_user.data_to_jtag,
          data_from_jtag_o => bscan_addr_user.data_from_jtag,
        ----- CONTROL SIGNALS ------
          ux_avail_o => bscan_addr_user.avail,        
          ux_ack_o   => bscan_addr_user.ack      
        );

    
    -- Instantiate BSCAN USER 3 Register and interface for data control
    bscan_u3_data_uri:bscan_interface
        Generic map (
          jtag_chain => 3,
          data_len_r => bram_data_len,
          data_len_w => bram_data_len,
          sync       => true
        )
        Port map ( 
        ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
          clk_i => buf_safe_clk,
        ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
          tck_o => open,
        ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
          drck_o => open,
        ----- DATA PATH -----
          data_to_jtag_i   => bscan_data_user.data_to_jtag,
          data_from_jtag_o => bscan_data_user.data_from_jtag,
        ----- CONTROL SIGNALS ------
          ux_avail_o => bscan_data_user.avail,        
          ux_ack_o   => bscan_data_user.ack     
        );

    -- Generate CDC control for address interface 
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
    -- Simple feedback for debugging
    bscan_addr_user.data_to_jtag <= bscan_addr_user.data_from_jtag_sync;
    
    -- Instantiate BSCAN USER 4 Registers and interface for enabling ECC reading
    bscan_u4_ecc_read_en:bscan_interface
        Generic map (
          jtag_chain => 4,
          data_len_r => 1,
          data_len_w => 1,
          sync       => true
        )
        Port map ( 
        ----- CLK INPUT FOR CONTROL SIGNAL CDC HANDLING -----
          clk_i => buf_safe_clk,
        ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
          tck_o => open,
        ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
          drck_o => open,
        ----- DATA PATH -----
          data_to_jtag_i   => bscan_ecc_r_en.data_to_jtag,
          data_from_jtag_o => bscan_ecc_r_en.data_from_jtag,
        ----- CONTROL SIGNALS ------
          ux_avail_o => bscan_ecc_r_en.avail,        
          ux_ack_o   => bscan_ecc_r_en.ack      
        );
    
    -- Generate CDC control for ECC Read enable signal
    cdc_ecc_r:process(buf_safe_clk)
        begin 
            if rising_edge(buf_safe_clk) then
                bscan_ecc_r_en.avail_prev <= bscan_ecc_r_en.avail;
                if bscan_ecc_r_en.avail = '1'
                   and bscan_ecc_r_en.avail_prev = '0' then
                    bscan_ecc_r_en.data_from_jtag_sync <=
                        bscan_ecc_r_en.data_from_jtag;
                end if;
            end if;
     end process cdc_ecc_r;
    -- Simple feedback for debugging
    bscan_ecc_r_en.data_to_jtag <= bscan_ecc_r_en.data_from_jtag_sync;

    -- use the data coming straight from BSCAN for ECC generation so that
    -- they are computed before the CDC process updates the
    -- synchronization and triggers the write signal
    gen_byte_ecc_enc:for i in 0 to 2 generate
        ecc_enc_8b:secded_enc8b
          Generic map (
            data_len     => 8,
            parities_len => 4
          )
          Port map (
            data_i    =>
                bscan_data_user.data_from_jtag((8 + (8*i)) - 1 downto 8*i),
            par_o     => bytes_ecc_gen_pars((4 + (4*i)) - 1 downto 4*i),
            -- Double error detection left unused for this example
            ded_par_o => open
          );
    end generate gen_byte_ecc_enc;
                                           
    -- Generate CDC control for data input interfaces
    cdc_data:process(buf_safe_clk)
        begin 
            if rising_edge(buf_safe_clk) then
                bscan_data_user.avail_prev <= bscan_data_user.avail;
                if bscan_data_user.avail = '1'
                   and bscan_data_user.avail_prev = '0' then
                    bscan_data_user.data_from_jtag_sync <=
                        bscan_data_user.data_from_jtag;
                    we <= '1';
                else
                    we <= '0';
                end if;
            end if;
    end process cdc_data;
    
    data_to_bram <= bytes_ecc_gen_pars & bscan_data_user.data_from_jtag_sync;
    
    
    stock_bram:bram_sdp_native_wrapper
      Generic map (
        -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
        g_family => g_family
      )
      Port map (
        clk_i     => buf_safe_clk,
        en_i      => '1',  -- read-port enable
        we_i      => we ,  -- write-port enable
        -- 1024-deep at this primitive's 36-bit-wide configuration
        wr_addr_i => bscan_addr_user.data_from_jtag_sync(9 downto 0),
        rd_addr_i => bscan_addr_user.data_from_jtag_sync(9 downto 0),
        -- 36 of the 36 physical bits are used, the 4 parity bits used as
        -- data that pass to the decoders
        din_i     => data_to_bram,
        dout_o    => data_from_bram
      );

    -- connect the plain data
    stock_data <= data_from_bram(bram_data_len - 1 downto 0);
    -- connect the corresponding ECC parities
    ecc_pars <=
        data_from_bram((bram_data_len + (3 * 4)) - 1 downto bram_data_len);
                            
    gen_byte_ecc_dec:for i in 0 to 2 generate
        ecc_dec_8b:secded_dec8b
          Generic map (
            data_len     => 8,
            parities_len => 4
          )
          Port map ( 
            data_i     => stock_data((8 + (8*i)) - 1 downto 8*i),
            ecc_pars_i => ecc_pars((4 + (4*i)) - 1 downto 4*i),   
            par_i      => '0', 
            dec_o      => corr_data((8 + (8*i)) - 1 downto 8*i),
            corr_bit_o => corr_bytes(i), 
            uncorr_o   => open
          );
    end generate gen_byte_ecc_dec;
    
    -- MUX the output to BSCAN depending on the ECC Read enable signal
    bscan_data_user.data_to_jtag <=
        corr_data when (bscan_ecc_r_en.data_from_jtag_sync(0) = '1') else
        stock_data;

    -- Output the per-byte ECC-correction flags (bit 3 unused)
    data_o <= '0' & corr_bytes;
                                

end Behavioral;
