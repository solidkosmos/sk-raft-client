--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: bram_readback_writeback_top
-- Description: One block RAM with the built-in ECC of the BRAM and no
--              output register, for example5.
--              The read port is always enabled. JTAG/BSCAN writes the
--              words and reads the BRAM outputs (data, ECC parity,
--              SBITERR) directly.
--
-- BSCAN registers
--   USER1  1 bit   write: clock enable (1 = runs, 0 = stopped; 0 after
--                  programming). read: the enable.
--   USER2  16 bits write: BRAM address (bits 8:0). read: the address.
--   USER3  80 bits write: bits 63:0 go to the BRAM word at the address
--                  (one write for each JTAG write). read: the BRAM
--                  outputs (bits 79:73 are 0):
--                    63:0   data (DOBDO & DOADO)
--                    71:64  ECC parity (DOPBDOP & DOPADOP)
--                    72     SBITERR
--
-- The BRAM is a RAMB36E1 in simple dual-port (SDP) mode, 512 x 72
-- (64 data bits and 8 ECC bits), with no output register (DO_REG = 0) and
-- with the built-in ECC encoder and decoder (EN_ECC_WRITE = EN_ECC_READ =
-- TRUE). Port A is the read port. It is always enabled, so the BRAM reads
-- the word at the address on each clock edge. Port B is the write port.
-- clk_gen_wrapper (safe startup) makes safe_clk from clk_i. The BRAM and
-- the BSCAN logic run on gated_clk, the output of a BUFGCE on safe_clk.
-- The USER1 enable drives its CE.
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity bram_readback_writeback_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS". The value goes directly
    -- to clk_gen_wrapper. The RAMB36E1 builds only for 7-series parts.
    g_family : string                 := "7SERIES";
    -- The input clock frequency in MHz (100 MHz by default). The PLL
    -- wrapper uses it.
    clk_freq : integer range 1 to 400 := 100
  );
  Port (
    clk_i : in std_ulogic
  );
end bram_readback_writeback_top;

architecture Behavioral of bram_readback_writeback_top is

  -- Safe-startup clock from the PLL wrapper
  signal safe_clk               : std_ulogic;

  -- Clock gate: the USER1 enable, synchronized on safe_clk, drives a BUFGCE.
  signal gated_clk              : std_ulogic;
  signal clk_en_jtag, clk_en_rb : std_ulogic_vector(0 downto 0);
  signal clk_en_d0, clk_en_sync : std_ulogic := '0';

  -- USER2: address
  signal addr_from_jtag, addr_sync : std_ulogic_vector(15 downto 0) :=
    (others => '0');
  signal addr_avail, addr_avail_prev : std_ulogic := '0';

  -- USER3: write data, BRAM outputs
  signal data_from_jtag, data_sync : std_ulogic_vector(79 downto 0) :=
    (others => '0');
  signal data_to_jtag : std_ulogic_vector(79 downto 0);
  signal data_avail, data_avail_prev : std_ulogic := '0';

  -- One-cycle write pulse for each USER3 write
  signal we : std_ulogic := '0';

  -- BRAM connections
  signal bram_addr    : std_logic_vector(15 downto 0);
  signal bram_di      : std_logic_vector(63 downto 0);
  signal bram_do      : std_logic_vector(63 downto 0);
  signal bram_dop     : std_logic_vector(7 downto 0);
  signal bram_sbiterr : std_ulogic;

begin

  -- Send the input clock through the safe-startup PLL wrapper. The period
  -- (ns) comes from clk_freq (MHz).
  safe_pll : entity work.clk_gen_wrapper
    generic map (
      g_family          => g_family,
      g_clkin_period_ns => 1000.0 / real(clk_freq)
    )
    port map (
      clk_i    => clk_i,
      clk_o    => safe_clk,
      locked_o => open
    );

  -- BSCAN USER1: clock enable, 0 after programming
  bscan_u1_clk_en : entity work.bscan_interface
    generic map (
      jtag_chain => 1,
      data_len_r => 1,
      data_len_w => 1,
      sync       => false
    )
    port map (
      clk_i            => '0',
      tck_o            => open,
      drck_o           => open,
      data_to_jtag_i   => clk_en_rb,
      data_from_jtag_o => clk_en_jtag,
      ux_avail_o       => open,
      ux_ack_o         => open
    );

  -- Two flip-flops synchronize the enable from TCK to safe_clk.
  process (safe_clk)
  begin
    if rising_edge(safe_clk) then
      clk_en_d0   <= clk_en_jtag(0);
      clk_en_sync <= clk_en_d0;
    end if;
  end process;

  clk_en_rb(0) <= clk_en_sync;

  -- The clock gate. The BUFGCE output stops low.
  clk_gate : BUFGCE
    port map (
      O  => gated_clk,
      CE => clk_en_sync,
      I  => safe_clk
    );

  -- BSCAN USER2: address
  bscan_u2_addr : entity work.bscan_interface
    generic map (
      jtag_chain => 2,
      data_len_r => 16,
      data_len_w => 16,
      sync       => true
    )
    port map (
      clk_i            => gated_clk,
      tck_o            => open,
      drck_o           => open,
      data_to_jtag_i   => addr_sync,
      data_from_jtag_o => addr_from_jtag,
      ux_avail_o       => addr_avail,
      ux_ack_o         => open
    );

  -- BSCAN USER3: write data, BRAM outputs
  bscan_u3_data : entity work.bscan_interface
    generic map (
      jtag_chain => 3,
      data_len_r => 80,
      data_len_w => 80,
      sync       => true
    )
    port map (
      clk_i            => gated_clk,
      tck_o            => open,
      drck_o           => open,
      data_to_jtag_i   => data_to_jtag,
      data_from_jtag_o => data_from_jtag,
      ux_avail_o       => data_avail,
      ux_ack_o         => open
    );

  -- The BRAM outputs go directly to USER3.
  data_to_jtag <= (79 downto 73 => '0') & bram_sbiterr &
                  std_ulogic_vector(bram_dop) & std_ulogic_vector(bram_do);

  -- CDC: take each JTAG write on the rising edge of its avail signal.
  -- A USER3 write gives one write pulse (we).
  process (gated_clk)
  begin
    if rising_edge(gated_clk) then
      addr_avail_prev <= addr_avail;
      data_avail_prev <= data_avail;

      if addr_avail = '1' and addr_avail_prev = '0' then
        addr_sync <= addr_from_jtag;
      end if;

      we <= '0';
      if data_avail = '1' and data_avail_prev = '0' then
        data_sync <= data_from_jtag;
        we        <= '1';
      end if;
    end if;
  end process;

  -- The address of a 72-bit word is bits 14:6 of the primitive address.
  bram_addr <= '0' & std_logic_vector(addr_sync(8 downto 0)) & "000000";
  bram_di   <= std_logic_vector(data_sync(63 downto 0));

  bram_inst : RAMB36E1
    generic map (
      RAM_MODE      => "SDP",
      READ_WIDTH_A  => 72,
      WRITE_WIDTH_B => 72,
      WRITE_MODE_A  => "READ_FIRST",
      WRITE_MODE_B  => "READ_FIRST",
      DOA_REG       => 0,
      DOB_REG       => 0,
      EN_ECC_READ   => TRUE,
      EN_ECC_WRITE  => TRUE,
      SIM_DEVICE    => "7SERIES"
    )
    port map (
      -- Read port (A), always enabled: data on DOBDO & DOADO
      CLKARDCLK     => gated_clk,
      ADDRARDADDR   => bram_addr,
      ENARDEN       => '1',
      REGCEAREGCE   => '0',
      RSTRAMARSTRAM => '0',
      RSTREGARSTREG => '0',
      DOADO         => bram_do(31 downto 0),
      DOBDO         => bram_do(63 downto 32),
      DOPADOP       => bram_dop(3 downto 0),
      DOPBDOP       => bram_dop(7 downto 4),
      -- Write port (B): data on DIBDI & DIADI. The encoder makes the ECC
      -- bits.
      CLKBWRCLK     => gated_clk,
      ADDRBWRADDR   => bram_addr,
      ENBWREN       => we,
      WEBWE         => (others => '1'),
      DIADI         => bram_di(31 downto 0),
      DIBDI         => bram_di(63 downto 32),
      DIPADIP       => (others => '0'),
      DIPBDIP       => (others => '0'),
      -- Not used in SDP mode
      WEA           => (others => '0'),
      REGCEB        => '0',
      RSTRAMB       => '0',
      RSTREGB       => '0',
      -- No cascade, no error injection
      CASCADEINA    => '0',
      CASCADEINB    => '0',
      CASCADEOUTA   => open,
      CASCADEOUTB   => open,
      INJECTDBITERR => '0',
      INJECTSBITERR => '0',
      DBITERR       => open,
      SBITERR       => bram_sbiterr,
      ECCPARITY     => open,
      RDADDRECC     => open
    );

end Behavioral;
