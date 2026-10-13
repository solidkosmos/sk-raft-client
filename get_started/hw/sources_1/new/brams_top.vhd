--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: brams_top
-- Description: Stock Block RAM with byte-wise Hamming SEC ECC, driven over
--              independent JTAG/BSCAN address and data channels. JTAG reads
--              the stock data or the ECC-corrected data, for A/B
--              fault-injection comparison.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity brams_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS". The value goes directly
    -- to clk_gen_wrapper.
    g_family       : string  := "7SERIES";
    -- The input clock frequency in MHz. The PLL wrapper uses it to set the
    -- PLL parameters for a correct passthrough clock.
    clk_freq       : integer range 1 to 400 := 100
  );
  Port (
    clk_i  : in std_ulogic;
    data_o : out std_ulogic_vector(3 downto 0) -- 3 byte ECC-correction flags
  );
end brams_top;

architecture Behavioral of brams_top is

    -- PLL clock, and its CE-gated version for all downstream fabric logic
    signal safe_clk, buf_safe_clk : std_ulogic;

    signal clk_en, clk_en_d0, clk_en_sync : std_ulogic := '0';

    constant bram_data_len : integer := 24; -- 3 bytes of data
    -- Bits 14:5 of the primitive address (the 10 address bits of this
    -- register) are the effective address bits, because the BRAM is 36 bits
    -- wide. The address has more than 8 bits, so the register has 16 bits
    -- (a multiple of 8).
    -- CAUTION: Keep the address value in the correct range (MAX
    -- 2**10 - 1). This design uses only bits 9:0, so a larger value
    -- accesses a lower address. All 10 bits are necessary to access the
    -- full memory array.
    constant bram_addr_len : integer := 16;
                                        
    -- Interface signals of the BSCAN registers

    -- BSCAN USER 1 : CLOCK ENABLE ---------------------
    type bscan_clk_en_interfacing is record
        -- JTAG reads back the clock-enable state.
        data_to_jtag   : std_ulogic_vector(0 downto 0);
        -- JTAG writes this bit to enable or disable the clock.
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
    
    
    -- The design uses all BSCAN USER registers as follows:
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
    
    -- 4 ECC parity bits for each of the 3 bytes (12 bits)
    signal bytes_ecc_gen_pars, ecc_pars :
        std_ulogic_vector((3 * 4) - 1  downto 0);
    -- The 3 bytes with their ECC parity bits (3 * 4)
    signal data_to_bram, data_from_bram   :
        std_ulogic_vector((bram_data_len + (3 * 4)) - 1 downto 0);
    signal corr_data : std_ulogic_vector(bram_data_len - 1 downto 0);
    signal stock_data : std_ulogic_vector(bram_data_len - 1 downto 0);
    
    -- One correction flag for each byte (1 = the decoder corrected a bit)
    signal corr_bytes : std_ulogic_vector(2 downto 0);

    -- The examples_utilities_pkg package declares clk_gen_wrapper and
    -- bscan_interface (see the use clause above).
    
    -- Simple Dual-Port Block RAM wrapper, built from a direct instantiation
    -- of the RAMB36E1/E2 primitive.
    component bram_sdp_native_wrapper is
      Generic (
        -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
        g_family : string := "7SERIES"
      );
      Port (
        clk_i     : in  std_ulogic;
        en_i      : in  std_ulogic;                     -- read-port enable
        we_i      : in  std_ulogic;                     -- write-port enable
        -- 1024 words deep in the 36-bit wide configuration of this primitive
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

    -- Synchronize the clock-enable signal with two flip-flops
    sync_clk_en:process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            clk_en_d0   <= clk_en;
            clk_en_sync <= clk_en_d0;
        end if;
    end process sync_clk_en;

    bscan_clk_en_user.data_to_jtag(0) <= clk_en_sync;

    -- For fault injection, all downstream fabric logic stops when clk_en
    -- is 0, not only the main demo logic of this example. Apply this clock
    -- gate to the peripheral logic of every example, also if the behaviour
    -- of that example is safe without it.
    BUFGCE_inst : BUFGCE
        Port map (
           O => buf_safe_clk, -- 1-bit output: Clock output
           CE => clk_en_sync, -- 1-bit input: Clock enable input for I0
           I => safe_clk      -- 1-bit input: Primary clock
        );
    
    -- Instantiate the BSCAN USER2 register and interface for address control
    bscan_u2_addr_uri:bscan_interface
        Generic map (
          jtag_chain => 2,
          data_len_r => bram_addr_len,
          data_len_w => bram_addr_len,
          sync       => true
        )
        Port map ( 
        ----- CLK INPUT FOR CONTROL SIGNAL CDC -----
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

    
    -- Instantiate the BSCAN USER3 register and interface for data control
    bscan_u3_data_uri:bscan_interface
        Generic map (
          jtag_chain => 3,
          data_len_r => bram_data_len,
          data_len_w => bram_data_len,
          sync       => true
        )
        Port map ( 
        ----- CLK INPUT FOR CONTROL SIGNAL CDC -----
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

    -- Generate the CDC control for the address interface
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
    -- Simple feedback path for debug
    bscan_addr_user.data_to_jtag <= bscan_addr_user.data_from_jtag_sync;
    
    -- Instantiate the BSCAN USER4 register and interface for the ECC read enable
    bscan_u4_ecc_read_en:bscan_interface
        Generic map (
          jtag_chain => 4,
          data_len_r => 1,
          data_len_w => 1,
          sync       => true
        )
        Port map ( 
        ----- CLK INPUT FOR CONTROL SIGNAL CDC -----
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
    
    -- Generate the CDC control for the ECC read-enable signal
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
    -- Simple feedback path for debug
    bscan_ecc_r_en.data_to_jtag <= bscan_ecc_r_en.data_from_jtag_sync;

    -- The ECC encoders use the data directly from BSCAN. Thus the parity
    -- bits are ready before the CDC process updates the synchronized data
    -- and sets the write signal.
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
            -- This example does not use double-error detection
            ded_par_o => open
          );
    end generate gen_byte_ecc_enc;
                                           
    -- Generate the CDC control for the data input interface
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
        -- 1024 words deep in the 36-bit wide configuration of this primitive
        wr_addr_i => bscan_addr_user.data_from_jtag_sync(9 downto 0),
        rd_addr_i => bscan_addr_user.data_from_jtag_sync(9 downto 0),
        -- All 36 physical bits are used. The 4 parity bits store data like
        -- the other bits, and this data goes to the decoders.
        din_i     => data_to_bram,
        dout_o    => data_from_bram
      );

    -- Connect the plain data bits
    stock_data <= data_from_bram(bram_data_len - 1 downto 0);
    -- Connect the related ECC parity bits
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
    
    -- Multiplex the output to BSCAN. The ECC read-enable signal selects the
    -- ECC-corrected data or the stock data.
    bscan_data_user.data_to_jtag <=
        corr_data when (bscan_ecc_r_en.data_from_jtag_sync(0) = '1') else
        stock_data;

    -- Output the ECC-correction flag of each byte (bit 3 is not used)
    data_o <= '0' & corr_bytes;
                                

end Behavioral;
