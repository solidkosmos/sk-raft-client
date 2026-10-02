--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: bram_sdp_native_wrapper
-- Description: Simple Dual-Port Block RAM wrapper built from a direct
--              RAMB36E1/E2 primitive instantiation. 36-bit-wide, 1024-deep
--              -- sized for 3 bytes each with 4-bit byte-wise Hamming SEC
--              ECC (8+4 per byte = 12 bits x 3 = 36). The wrapper itself
--              has no ECC logic of its own; it just exposes the full
--              36-bit physical storage (main + parity pins together) as
--              one flat bus. Packing/unpacking and correcting the
--              byte-wise ECC is done by the caller.
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Built from a DIRECT primitive instantiation
-- (RAMB36E1 on 7-series, RAMB36E2 on UltraScale/UltraScale+) instead of
-- inferred VHDL 

entity bram_sdp_native_wrapper is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
    g_family : string := "7SERIES"
  );
  Port (
    clk_i     : in  std_ulogic;
    en_i      : in  std_ulogic;                     -- read-port enable
    we_i      : in  std_ulogic;                     -- write-port enable
    -- 1024-deep at this primitive's 36-bit-wide configuration
    wr_addr_i : in  std_ulogic_vector(9 downto 0);
    rd_addr_i : in  std_ulogic_vector(9 downto 0);
    -- all 36 physical bits exposed: (35 downto 0) = 3 bytes x (8 data + 4
    -- Hamming SEC ECC bits) -- byte-wise ECC is packed/unpacked by the
    -- caller, not this wrapper
    din_i     : in  std_ulogic_vector(35 downto 0);
    dout_o    : out std_ulogic_vector(35 downto 0)
  );
end bram_sdp_native_wrapper;

architecture Structure of bram_sdp_native_wrapper is

    component RAMB36E1 is
      generic (
        RAM_MODE       : string  := "TDP";
        READ_WIDTH_A   : integer := 0;
        WRITE_WIDTH_B  : integer := 0;
        WRITE_MODE_A   : string  := "WRITE_FIRST";
        WRITE_MODE_B   : string  := "WRITE_FIRST";
        DOA_REG        : integer := 0;
        DOB_REG        : integer := 0;
        EN_ECC_READ    : boolean := false;
        EN_ECC_WRITE   : boolean := false
      );
      port (
        DOADO          : out std_ulogic_vector(31 downto 0);
        DOPADOP        : out std_ulogic_vector(3 downto 0);
        DOBDO          : out std_ulogic_vector(31 downto 0);
        DOPBDOP        : out std_ulogic_vector(3 downto 0);
        SBITERR        : out std_ulogic;
        DBITERR        : out std_ulogic;
        RDADDRECC      : out std_ulogic_vector(8 downto 0);
        DIADI          : in  std_ulogic_vector(31 downto 0);
        DIPADIP        : in  std_ulogic_vector(3 downto 0);
        DIBDI          : in  std_ulogic_vector(31 downto 0);
        DIPBDIP        : in  std_ulogic_vector(3 downto 0);
        ADDRARDADDR    : in  std_ulogic_vector(15 downto 0);
        ADDRBWRADDR    : in  std_ulogic_vector(15 downto 0);
        CLKARDCLK      : in  std_ulogic;
        CLKBWRCLK      : in  std_ulogic;
        ENARDEN        : in  std_ulogic;
        ENBWREN        : in  std_ulogic;
        WEA            : in  std_ulogic_vector(3 downto 0);
        WEBWE          : in  std_ulogic_vector(7 downto 0);
        RSTRAMARSTRAM  : in  std_ulogic;
        RSTRAMB        : in  std_ulogic;
        RSTREGARSTREG  : in  std_ulogic;
        RSTREGB        : in  std_ulogic;
        REGCEAREGCE    : in  std_ulogic;
        REGCEB         : in  std_ulogic;
        INJECTSBITERR  : in  std_ulogic;
        INJECTDBITERR  : in  std_ulogic
      );
    end component;

    component RAMB36E2 is
      generic (
        RAM_MODE       : string  := "TDP";
        READ_WIDTH_A   : integer := 0;
        WRITE_WIDTH_B  : integer := 0;
        WRITE_MODE_A   : string  := "WRITE_FIRST";
        WRITE_MODE_B   : string  := "WRITE_FIRST";
        DOA_REG        : integer := 1;
        DOB_REG        : integer := 1;
        EN_ECC_READ    : string  := "FALSE";
        EN_ECC_WRITE   : string  := "FALSE"
      );
      port (
        DOUTADOUT      : out std_ulogic_vector(31 downto 0);
        DOUTPADOUTP    : out std_ulogic_vector(3 downto 0);
        DOUTBDOUT      : out std_ulogic_vector(31 downto 0);
        DOUTPBDOUTP    : out std_ulogic_vector(3 downto 0);
        SBITERR        : out std_ulogic;
        DBITERR        : out std_ulogic;
        RDADDRECC      : out std_ulogic_vector(8 downto 0);
        DINADIN        : in  std_ulogic_vector(31 downto 0);
        DINPADINP      : in  std_ulogic_vector(3 downto 0);
        DINBDIN        : in  std_ulogic_vector(31 downto 0);
        DINPBDINP      : in  std_ulogic_vector(3 downto 0);
        ADDRARDADDR    : in  std_ulogic_vector(14 downto 0);
        ADDRBWRADDR    : in  std_ulogic_vector(14 downto 0);
        CLKARDCLK      : in  std_ulogic;
        CLKBWRCLK      : in  std_ulogic;
        ENARDEN        : in  std_ulogic;
        ENBWREN        : in  std_ulogic;
        WEA            : in  std_ulogic_vector(3 downto 0);
        WEBWE          : in  std_ulogic_vector(7 downto 0);
        RSTRAMARSTRAM  : in  std_ulogic;
        RSTRAMB        : in  std_ulogic;
        RSTREGARSTREG  : in  std_ulogic;
        RSTREGB        : in  std_ulogic;
        REGCEAREGCE    : in  std_ulogic;
        REGCEB         : in  std_ulogic;
        INJECTSBITERR  : in  std_ulogic;
        INJECTDBITERR  : in  std_ulogic
      );
    end component;

    -- SDP mode at width <= 36 uses ONLY ONE data pin set per direction, and
    -- it is NOT simply "the A side": reads stay paired with the A-side
    -- address/output pins (DOADO/DOPADOP, since ADDRARDADDR is the read
    -- address), but writes are paired with the B-side input pins (DIBDI/
    -- DIPBDIP, since ADDRBWRADDR is the write address) -- confirmed against
    -- AMD/Xilinx UG473 Table 1-13 (SDP Mode Port Name Mapping, "Width <= 36"
    -- row). DIADI/DOBDO (and their parity companions) are unused at this
    -- width and are tied off / left open below.
    --
    -- The full 36-bit width is exposed as ONE flat data bus: (31 downto 0)
    -- on the "main" data pins (DIBDI/DOADO), (35 downto 32) on the "parity"
    -- pins (DIPBDIP/DOPADOP, only 2 bits wide -- see UG473 Table 1-13's
    -- x36 row: DIP[3:2] = DIPBDIP[1:0] on write, DOP[3:2] = DOPADOP[1:0] on
    -- read). This wrapper does no ECC of its own -- din_i/dout_o(35 downto
    -- 0) is just raw storage; packing 3 bytes as 3 x (8 data + 4 Hamming
    -- SEC ECC bits) into that 36-bit field is the caller's job.
    --
    -- Address mapping: confirmed against UG473 Table 1-12 (Port Aspect
    -- Ratio for RAMB36E1 in SDP Mode) -- the x36 row gives depth 1,024 with
    -- 10 significant address bits at ADDR[14:5], ADDR[4:0] unused/tied low.


    signal addr_a_full, addr_b_full : std_ulogic_vector(15 downto 0);
    signal webwe_full : std_ulogic_vector(7 downto 0);

begin

    addr_a_full <= '0' & rd_addr_i(9 downto 0) & "00000";
    addr_b_full <= '0' & wr_addr_i(9 downto 0) & "00000";
    webwe_full  <= (others => we_i);

    gen_7series : if g_family = "7SERIES" generate
    begin

        ramb36e1_inst : RAMB36E1
          Generic map (
            RAM_MODE      => "SDP",
            READ_WIDTH_A  => 36,
            WRITE_WIDTH_B => 36,
            WRITE_MODE_A  => "READ_FIRST",
            WRITE_MODE_B  => "READ_FIRST",
            DOA_REG       => 0,
            DOB_REG       => 0,
            EN_ECC_READ   => false,
            EN_ECC_WRITE  => false
          )
          Port map (
            DOADO   => dout_o(31 downto 0), DOPADOP => dout_o(35 downto 32),
            DOBDO   => open,                DOPBDOP => open,
            SBITERR => open,
            DBITERR => open,
            RDADDRECC => open,
            DIADI   => (others => '0'),      DIPADIP => (others => '0'),
            DIBDI   => din_i(31 downto 0),   DIPBDIP => din_i(35 downto 32),
            ADDRARDADDR => addr_a_full(15 downto 0),
            ADDRBWRADDR => addr_b_full(15 downto 0),
            CLKARDCLK   => clk_i,
            CLKBWRCLK   => clk_i,
            ENARDEN     => en_i,
            ENBWREN     => we_i,
            WEA         => (others => '0'),
            WEBWE       => webwe_full,
            RSTRAMARSTRAM => '0', RSTRAMB => '0',
            RSTREGARSTREG => '0', RSTREGB => '0',
            REGCEAREGCE   => '0', REGCEB   => '0',
            INJECTSBITERR => '0',
            INJECTDBITERR => '0'
          );
    end generate gen_7series;

    gen_ultrascale_family : if g_family = "ULTRASCALE"
                             or g_family = "ULTRASCALEPLUS" generate
    begin

        ramb36e2_inst : RAMB36E2
          Generic map (
            RAM_MODE      => "SDP",
            READ_WIDTH_A  => 36,
            WRITE_WIDTH_B => 36,
            WRITE_MODE_A  => "READ_FIRST",
            WRITE_MODE_B  => "READ_FIRST",
            DOA_REG       => 0,
            DOB_REG       => 0,
            EN_ECC_READ   => "FALSE",
            EN_ECC_WRITE  => "FALSE"
          )
          Port map (
            DOUTADOUT   => dout_o(31 downto 0),
            DOUTPADOUTP => dout_o(35 downto 32),
            DOUTBDOUT   => open,                 DOUTPBDOUTP => open,
            SBITERR => open,
            DBITERR => open,
            RDADDRECC => open,
            DINADIN   => (others => '0'),     DINPADINP => (others => '0'),
            DINBDIN   => din_i(31 downto 0),  DINPBDINP => din_i(35 downto 32),
            ADDRARDADDR => addr_a_full(14 downto 0),
            ADDRBWRADDR => addr_b_full(14 downto 0),
            CLKARDCLK   => clk_i,
            CLKBWRCLK   => clk_i,
            ENARDEN     => en_i,
            ENBWREN     => we_i,
            WEA         => (others => '0'),
            WEBWE       => webwe_full,
            RSTRAMARSTRAM => '0', RSTRAMB => '0',
            RSTREGARSTREG => '0', RSTREGB => '0',
            REGCEAREGCE   => '1', REGCEB   => '1',
            INJECTSBITERR => '0',
            INJECTDBITERR => '0'
          );
    end generate gen_ultrascale_family;

end Structure;
