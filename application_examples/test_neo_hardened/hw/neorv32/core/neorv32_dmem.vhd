-- ========================================================================== --
-- NEORV32 SoC - Processor-Internal Data Memory (DMEM)                        --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --
-- Modified by SolidKosmos S.A. (2026): added per-byte-lane Hamming SEC       --
-- encode/ decode (secded_enc8b/secded_dec8b) around the memory core, and an  --
-- irq_ecc_dmem output flagging corrections. Gated behind the HARDEN_EN       --
-- generic -- when false, falls back to a plain, unprotected byte-wide RAM    --
-- matching stock NEORV32, for hardened-vs-unhardened fault-injection         --
-- comparisons. See THIRD_PARTY_NOTICES.md at the project root for the full   --
-- list of modified files.                                                    --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_dmem is
  generic (
    MEM_SIZE  : natural; -- memory size in bytes, has to be a power of 2, min 4
    OUTREG_EN : boolean; -- implement output register stage
    -- enable per-byte-lane Hamming SEC protection; when false, plain
    -- unprotected RAM (stock NEORV32 behavior)
    HARDEN_EN : boolean := true
  );
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- async reset, low-active
    bus_req_i : in  bus_req_t;  -- bus request
    bus_rsp_o : out bus_rsp_t;   -- bus response
    -- irq for ecc --
    irq_ecc_dmem : out std_ulogic
  );
end neorv32_dmem;

architecture neorv32_dmem_rtl of neorv32_dmem is

  -- auto-configuration --
  -- word address width
  constant awidth_c  : natural := index_size_f(MEM_SIZE/4);
  -- memory latency
  constant latency_c : natural := cond_sel_natural_f(OUTREG_EN, 2, 1);

  -- local signals --
  signal rdata : std_ulogic_vector(31 downto 0);
  signal wack  : std_ulogic;
  signal rden  : std_ulogic_vector(1 downto 0);
  signal en    : std_ulogic_vector(3 downto 0);
  
  signal corr_bits : std_ulogic_vector(3 downto 0);

  -- byte lanes that did a read: [3:0] in the last cycle, [7:4] one cycle
  -- earlier --
  signal lane_rd   : std_ulogic_vector(7 downto 0);
  -- lanes whose read data is on bus_rsp_o now
  signal lane_rd_q : std_ulogic_vector(3 downto 0);

  attribute dont_touch : string;
  attribute dont_touch of corr_bits : signal is "true";

begin

  -- Memory Core (hardened: per-byte-lane Hamming SEC) -------------------------
  -- ---------------------------------------------------------------------------
  -- Each byte lane is protected by a 12-bit Hamming codeword (8 data + 4
  -- parity bits) via secded_enc8b/secded_dec8b. The decoder corrects based
  -- on the syndrome only -- it does not check overall parity -- so it
  -- cannot tell a single-bit error apart from a double-bit one; the
  -- decoder's par_i and uncorr are left unused/open for that reason.
  dmem_ram_gen_hardened:
  if HARDEN_EN generate
    dmem_ram_gen:
    for i in 0 to 3 generate -- four individual byte-wide RAMs

      -- per-lane encode/decode signals --
      signal enc_par   : std_ulogic_vector(3 downto 0);
      signal cw_wr, cw_rd : std_ulogic_vector(11 downto 0); -- 8 data + 4 parity

      attribute DONT_TOUCH : string;
      attribute DONT_TOUCH of decoder, encoder : label is "TRUE";

      begin
        -- encode --
        encoder: entity neorv32.secded_enc8b
        generic map (
            data_len     => 8,
            parities_len => 4
        )
        port map (
               data_i    => bus_req_i.data(i*8+7 downto i*8),
               par_o     => enc_par,
               -- not stored; decoder doesn't check overall parity
               ded_par_o => open
        );
        cw_wr <= bus_req_i.data(i*8+7 downto i*8) & enc_par;

        ram_inst: entity neorv32.neorv32_prim_spram
        generic map (
          AWIDTH => awidth_c,
          DWIDTH => 12, -- 8 data + 4 parity
          OUTREG => OUTREG_EN
        )
        port map (
          clk_i  => clk_i,
          en_i   => en(i),
          rw_i   => bus_req_i.rw,
          addr_i => bus_req_i.addr(awidth_c+1 downto 2),
          data_i => cw_wr,
          data_o => cw_rd
        );

        -- decode --
        decoder: entity neorv32.secded_dec8b
         generic map (
              data_len     => 8,
              parities_len => 4
          )
          port map (
                 data_i     => cw_rd(11 downto 4),
                 ecc_pars_i => cw_rd(3 downto 0),
                 -- unused; decoder doesn't check overall parity
                 par_i      => '0',
                 dec_o      => rdata(i*8+7 downto i*8),
                 corr_bit_o => corr_bits(i),
                 -- always '0'; decoder can't compute this without par_i
                 uncorr_o   => open
          );
    end generate dmem_ram_gen;

    -- A correction raises the interrupt only for a byte lane that the bus
    -- actually reads
    lane_rd_q <= lane_rd(7 downto 4) when OUTREG_EN else lane_rd(3 downto 0);
    irq_ecc_dmem <= (corr_bits(3) and lane_rd_q(3))
        or (corr_bits(2) and lane_rd_q(2)) or (corr_bits(1) and lane_rd_q(1))
        or (corr_bits(0) and lane_rd_q(0));
  end generate dmem_ram_gen_hardened;


  -- Memory Core (unhardened: plain byte-wide RAM, no ECC, stock NEORV32
  -- behavior) -----------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  dmem_ram_gen_plain:
  if not HARDEN_EN generate
    dmem_ram_gen:
    for i in 0 to 3 generate -- four individual byte-wide RAMs
      ram_inst: entity neorv32.neorv32_prim_spram
      generic map (
        AWIDTH => awidth_c,
        DWIDTH => 8,
        OUTREG => OUTREG_EN
      )
      port map (
        clk_i  => clk_i,
        en_i   => en(i),
        rw_i   => bus_req_i.rw,
        addr_i => bus_req_i.addr(awidth_c+1 downto 2),
        data_i => bus_req_i.data(i*8+7 downto i*8),
        data_o => rdata(i*8+7 downto i*8)
      );
    end generate dmem_ram_gen;

    irq_ecc_dmem <= '0';
  end generate dmem_ram_gen_plain;


  -- byte-wise enable --
  en <= bus_req_i.ben when (bus_req_i.stb = '1') else (others => '0');


  -- Bus Handshake -------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  bus_handshake: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      wack <= '0';
      rden <= (others => '0');
      lane_rd <= (others => '0');
    elsif rising_edge(clk_i) then
      wack <= bus_req_i.stb and bus_req_i.rw;
      rden <= rden(0) & (bus_req_i.stb and (not bus_req_i.rw));
      -- byte lanes read in this access (en is 0 for all lanes without a
      -- request) --
      lane_rd(7 downto 4) <= lane_rd(3 downto 0);
      if (bus_req_i.rw = '0') then
        lane_rd(3 downto 0) <= en;
      else
        lane_rd(3 downto 0) <= (others => '0');
      end if;
    end if;
  end process bus_handshake;

  -- output gate
  bus_rsp_o.data <= rdata when (rden(latency_c-1) = '1') else (others => '0');
  bus_rsp_o.err  <= '0'; -- no access error possible
  bus_rsp_o.ack  <= rden(latency_c-1) or wack;


end neorv32_dmem_rtl;
