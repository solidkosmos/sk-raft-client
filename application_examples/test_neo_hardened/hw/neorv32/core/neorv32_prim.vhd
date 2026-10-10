-- ========================================================================== --
-- NEORV32 - Primitives - Generic Single-Clock FIFO (FIFO)                    --
-- -------------------------------------------------------------------------- --
-- The FIFO operates in "first-word-fall-through" (FWFT) mode: the first      --
-- written word appears directly at the output (after the synchronous-read    --
-- delay) without any explicit read access.                                   --
--                                                                            --
-- The status signals "free space left" (free_o) and "data available"         --
-- (avail_o) are synchronized to the according port:                          --
-- - free_o  -> write port                                                    --
-- - avail_o -> read port                                                     --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity neorv32_prim_fifo is
  generic (
    -- number of FIFO entries; has to be a power of two; min 1
    AWIDTH  : natural;
    DWIDTH  : natural; -- size of data elements in FIFO
    OUTGATE : boolean  -- true = output zero if no data available
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic;                           -- clock, rising edge
    -- async reset, low-active
    rstn_i  : in  std_ulogic;
    -- sync reset, high-active
    clear_i : in  std_ulogic;
    -- write port --
    wdata_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    we_i    : in  std_ulogic;                           -- write enable
    -- at least one entry is free when set
    free_o  : out std_ulogic;
    -- read port --
    re_i    : in  std_ulogic;                           -- read enable
    rdata_o : out std_ulogic_vector(DWIDTH-1 downto 0); -- read data
    -- data available when set
    avail_o : out std_ulogic
  );
end neorv32_prim_fifo;

architecture neorv32_prim_fifo_rtl of neorv32_prim_fifo is

  -- memory core --
  type ram_t is array (0 to (2**AWIDTH)-1)
      of std_ulogic_vector(DWIDTH-1 downto 0);
  signal fifo : ram_t;

  -- local signals --
  signal rdata : std_ulogic_vector(DWIDTH-1 downto 0);
  signal we, re, ram_re, match, full, empty, avail : std_ulogic;
  signal w_pnt, w_nxt, r_pnt, r_nxt : std_ulogic_vector(AWIDTH downto 0);

begin

  -- Pointers ------------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  pointer_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      w_pnt <= (others => '0');
      r_pnt <= (others => '0');
    elsif rising_edge(clk_i) then
      w_pnt <= w_nxt;
      r_pnt <= r_nxt;
    end if;
  end process pointer_reg;

  -- access control --
  re <= re_i and (not empty); -- read only if data available
  we <= we_i and (not full);  -- write only if free space available

  -- pointer update --
  w_nxt <= (others => '0') when (clear_i = '1')
      else std_ulogic_vector(unsigned(w_pnt) + 1) when (we = '1') else w_pnt;
  r_nxt <= (others => '0') when (clear_i = '1')
      else std_ulogic_vector(unsigned(r_pnt) + 1) when (re = '1') else r_pnt;

  -- Status --------------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  -- more than 1 FIFO entry --
  fifo_status_large:
  if (AWIDTH > 0) generate
    match <= '1'
        when (r_pnt(AWIDTH-1 downto 0) = w_pnt(AWIDTH-1 downto 0)) else '0';
    full  <= '1' when (r_pnt(AWIDTH) /= w_pnt(AWIDTH))
        and (match = '1') else '0';
    empty <= '1' when (r_pnt(AWIDTH)  = w_pnt(AWIDTH))
        and (match = '1') else '0';
    -- [important] 'avail' is synchronized to the read port --
    status_reg: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        avail <= '0';
      elsif rising_edge(clk_i) then
        avail <= not empty;
      end if;
    end process status_reg;
  end generate;

  -- just 1 FIFO entry --
  fifo_status_small:
  if (AWIDTH = 0) generate
    match <= '1' when (r_pnt(0) = w_pnt(0)) else '0';
    full  <= not match;
    empty <= match;
    avail <= not empty;
  end generate;

  -- status output --
  free_o  <= not full;
  avail_o <= avail;


  -- Memory --------------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  -- more than 1 FIFO entry --
  fifo_memory_large:
  if (AWIDTH > 0) generate
    memory_core: process(clk_i) -- simple dual-port RAM
    begin
      if rising_edge(clk_i) then
        if (we = '1') then
          fifo(to_integer(unsigned(w_pnt(AWIDTH-1 downto 0)))) <= wdata_i;
        end if;
        rdata <= fifo(to_integer(unsigned(r_pnt(AWIDTH-1 downto 0))));
      end if;
    end process memory_core;
  end generate;

  -- just 1 FIFO entry --
  fifo_memory_small:
  if (AWIDTH = 0) generate
    memory_core: process(rstn_i, clk_i) -- single register
    begin
      if (rstn_i = '0') then
        fifo(0) <= (others => '0');
      elsif rising_edge(clk_i) then
        if (we = '1') then
          fifo(0) <= wdata_i;
        end if;
      end if;
    end process memory_core;
    rdata <= fifo(0);
  end generate;

  -- output gate: output zero if no data available --
  rdata_o <= (others => '0') when OUTGATE and (avail = '0') else rdata;

end neorv32_prim_fifo_rtl;


-- ========================================================================== --
-- NEORV32 - Primitives - Generic Single-Port RAM (SPRAM)                     --
-- -------------------------------------------------------------------------- --
-- Provides a single read/write port.                                         --
-- Can be mapped to blockRAM primitives.                                      --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library UNISIM;
use UNISIM.VComponents.all;

entity neorv32_prim_spram is
  generic (
    AWIDTH : natural; -- address width (number of bits)
    DWIDTH : natural; -- data width (number of bits)
    OUTREG : boolean  -- add output register stage
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic;                           -- global clock
    -- read/write port --
    en_i   : in  std_ulogic;                           -- access enable
    rw_i   : in  std_ulogic;                           -- 0=read, 1=write
    addr_i : in  std_ulogic_vector(AWIDTH-1 downto 0); -- address
    data_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    data_o : out std_ulogic_vector(DWIDTH-1 downto 0)  -- read data
  );
end neorv32_prim_spram;

architecture neorv32_prim_spram_rtl of neorv32_prim_spram is

  type ram_t is array (0 to (2**AWIDTH)-1)
      of std_ulogic_vector(DWIDTH-1 downto 0);
  signal spram : ram_t;
  signal rdata : std_ulogic_vector(DWIDTH-1 downto 0);

begin

  -- Memory Core ---------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  memory_core: process(clk_i)
  begin
    if rising_edge(clk_i) then
      if (en_i = '1') then
        if (rw_i = '1') then
          spram(to_integer(unsigned(addr_i))) <= data_i;
        else
          rdata <= spram(to_integer(unsigned(addr_i)));
        end if;
      end if;
    end if;
  end process memory_core;

    

  -- Output Register -----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  output_register_enabled:
  if OUTREG generate -- might improve FPGA mapping and/or timing results
    read_outreg: process(clk_i)
    begin
      if rising_edge(clk_i) then
        data_o <= rdata;
      end if;
    end process read_outreg;
  end generate;

  -- no output register --
  output_register_disabled:
  if not OUTREG generate
    data_o <= rdata;
  end generate;

end neorv32_prim_spram_rtl;


-- ========================================================================== --
-- NEORV32 - Primitives - Generic Simple Dual-Port RAM (SDPRAM)               --
-- -------------------------------------------------------------------------- --
-- Provides a single read/write port and a read-only port.                    --
-- Can be mapped to blockRAM primitives.                                      --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --
-- Modified by SolidKosmos S.A. (2026): added soft SECDED protection in       --
-- fabric logic (secded_enc32b on the write data, one secded_dec32b on each   --
-- read port) around the inferred block RAM, and an irq_ecc_o output that     --
-- flags a corrected read. Gated behind the HARDEN_EN generic -- when false,  --
-- falls back to the original inferred-BRAM behavioral description (no ECC)   --
-- for hardened-vs-unhardened                                                 --
-- fault-injection comparisons. Only this neorv32_prim_sdpram entity was      --
-- changed; the other primitives in this file are unmodified. See             --
-- THIRD_PARTY_NOTICES.md at the project root for the full list of modified   --
-- files.                                                                     --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library UNISIM;
use UNISIM.VComponents.all;

entity neorv32_prim_sdpram is
  generic (
    AWIDTH    : natural; -- address width (number of bits)
    DWIDTH    : natural; -- data width (number of bits)
    OUTREG    : boolean; -- add output register stage
    -- enable soft SECDED (fabric logic, DWIDTH = 32 only); when false, plain
    -- inferred BRAM (stock NEORV32 behavior)
    HARDEN_EN : boolean := true
  );
  port (
    -- global control --
    clk_i    : in  std_ulogic;                           -- global clock
    -- read/write port --
    a_en_i   : in  std_ulogic;                           -- access enable
    a_rw_i   : in  std_ulogic;                           -- 0=read, 1=write
    a_addr_i : in  std_ulogic_vector(AWIDTH-1 downto 0); -- read/write address
    a_data_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    a_data_o : out std_ulogic_vector(DWIDTH-1 downto 0); -- read data
    -- read port --
    b_en_i   : in  std_ulogic;                           -- access enable
    b_addr_i : in  std_ulogic_vector(AWIDTH-1 downto 0); -- read address
    b_data_o : out std_ulogic_vector(DWIDTH-1 downto 0); -- read data
    -- interrupt request --
    irq_ecc_o : out std_ulogic
  );
end neorv32_prim_sdpram;

architecture neorv32_prim_sdpram_rtl of neorv32_prim_sdpram is

  type ram_t is array (0 to (2**AWIDTH)-1)
      of std_ulogic_vector(DWIDTH-1 downto 0);
  signal sdpram : ram_t;
  signal a_rdata, b_rdata : std_ulogic_vector(DWIDTH-1 downto 0);
  
  -- soft SECDED (hardened path): each RAM word holds the data and 7 check bits
  -- --
  type ram_ecc_t is array (0 to (2**AWIDTH)-1)
      of std_ulogic_vector(DWIDTH+6 downto 0);
  signal ram_ecc : ram_ecc_t;
  attribute ram_style : string;
  -- keep the register file in block RAM
  attribute ram_style of ram_ecc : signal is "block";

  -- check bits of the write data
  signal enc_par            : std_ulogic_vector(6 downto 0);
  -- codeword to write
  signal a_cw_wr            : std_ulogic_vector(DWIDTH+6 downto 0);
  -- codewords read on port A and B
  signal a_cw_rd, b_cw_rd   : std_ulogic_vector(DWIDTH+6 downto 0);
  -- the port did a read in the last cycle
  signal a_rd_q, b_rd_q     : std_ulogic;
  -- port B reads the address port A writes in the same cycle
  signal b_coll             : std_ulogic;
  -- single-bit error corrected on the port
  signal a_corr, b_corr     : std_ulogic;
  -- double-bit error detected on the port (not used yet)
  signal a_uncorr, b_uncorr : std_ulogic;
  
begin

  -- Memory Core (hardened path: soft SECDED in fabric logic) ------------------
  -- ---------------------------------------------------------------------------
  -- The write data is encoded (secded_enc32b) and stored together with its 7
  -- check bits. Each read port decodes its codeword (secded_dec32b): a
  -- single-bit error is corrected before the data leaves the register file, a
  -- double-bit error is detected (a_uncorr/b_uncorr).
  memory_core_hardened:
  if HARDEN_EN generate

    assert (DWIDTH = 32)
        report "neorv32_prim_sdpram: the soft SECDED supports DWIDTH = 32 only"
        severity failure;

    -- encode the write data --
    encoder: entity work.secded_enc32b
    port map (
      data_i => a_data_i,
      par_o  => enc_par
    );
    a_cw_wr <= a_data_i & enc_par;

    -- memory core (same access scheme as the plain path, but with codewords) --
    memory_core: process(clk_i)
    begin
      if rising_edge(clk_i) then
        -- port A: read/write --
        if (a_en_i = '1') then
          if (a_rw_i = '1') then
            ram_ecc(to_integer(unsigned(a_addr_i))) <= a_cw_wr;
          else
            a_cw_rd <= ram_ecc(to_integer(unsigned(a_addr_i)));
          end if;
        end if;
        -- port B: read-only --
        if (b_en_i = '1') then
          b_cw_rd <= ram_ecc(to_integer(unsigned(b_addr_i)));
        end if;
      end if;
    end process memory_core;

    -- Read-during-write collision: port B (rs2) reads every cycle, also while
    -- port A writes back rd. When both address the same word, the BRAM returns
    -- a mix of the old and the new codeword, so the decoder sees a false error.
    -- The CPU never uses rs2 from such a cycle, so this read must not raise the
    -- interrupt.
    b_coll <= '1' when (a_en_i = '1') and (a_rw_i = '1')
        and (a_addr_i = b_addr_i) else '0';

    -- remember which port did a real read, so that only a real read can raise
    -- the interrupt --
    read_flags: process(clk_i)
    begin
      if rising_edge(clk_i) then
        a_rd_q <= a_en_i and (not a_rw_i);
        b_rd_q <= b_en_i and (not b_coll);
      end if;
    end process read_flags;

    -- decode port A (rs1) --
    decoder_a: entity work.secded_dec32b
    port map (
      data_i   => a_cw_rd(DWIDTH+6 downto 7),
      par_i    => a_cw_rd(6 downto 0),
      data_o   => a_rdata,
      corr_o   => a_corr,
      uncorr_o => a_uncorr
    );

    -- decode port B (rs2) --
    decoder_b: entity work.secded_dec32b
    port map (
      data_i   => b_cw_rd(DWIDTH+6 downto 7),
      par_i    => b_cw_rd(6 downto 0),
      data_o   => b_rdata,
      corr_o   => b_corr,
      uncorr_o => b_uncorr
    );

    -- interrupt: a read on port A or B returned corrected data --
    irq_ecc_o <= (a_rd_q and a_corr) or (b_rd_q and b_corr);

  end generate memory_core_hardened;

  -- Memory Core (plain path: inferred BRAM, no ECC -- stock NEORV32 behavior)
  -- ---------------------------------------------------------------------------
  memory_core_plain:
  if not HARDEN_EN generate
    memory_core: process(clk_i)
    begin
      if rising_edge(clk_i) then
        -- port A: read/write --
        if (a_en_i = '1') then
          if (a_rw_i = '1') then
            sdpram(to_integer(unsigned(a_addr_i))) <= a_data_i;
          else
            a_rdata <= sdpram(to_integer(unsigned(a_addr_i)));
          end if;
        end if;
        -- port B: read-only --
        if (b_en_i = '1') then
          b_rdata <= sdpram(to_integer(unsigned(b_addr_i)));
        end if;
      end if;
    end process memory_core;

    irq_ecc_o <= '0';
  end generate memory_core_plain;


  -- Output Register -----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  output_register_enabled:
  if OUTREG generate -- might improve FPGA mapping and/or timing results
    read_outreg: process(clk_i)
    begin
      if rising_edge(clk_i) then
        a_data_o <= a_rdata;
        b_data_o <= b_rdata;
      end if;
    end process read_outreg;
  end generate;

  -- no output register --
  output_register_disabled:
  if not OUTREG generate
    a_data_o <= a_rdata;
    b_data_o <= b_rdata;
  end generate;

end neorv32_prim_sdpram_rtl;


-- ========================================================================== --
-- NEORV32 - Primitives - Generic 2-Cycle Signed/Unsigned Integer Multiplier  --
-- (MUL)                                                                      --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity neorv32_prim_mul is
  generic (
    DWIDTH : natural -- operand width
  );
  port (
    -- global control --
    clk_i    : in  std_ulogic;                              -- global clock
    -- global reset, low-active, async
    rstn_i   : in  std_ulogic;
    -- data path --
    -- enable input operand registers
    en_i     : in  std_ulogic;
    opa_i    : in  std_ulogic_vector(DWIDTH-1 downto 0);    -- operand A
    -- operand A is a signed number
    opa_sn_i : in  std_ulogic;
    opb_i    : in  std_ulogic_vector(DWIDTH-1 downto 0);    -- operand B
    -- operand B is a signed number
    opb_sn_i : in  std_ulogic;
    res_o    : out std_ulogic_vector((2*DWIDTH)-1 downto 0) -- resulting product
  );
end neorv32_prim_mul;

architecture neorv32_prim_mul_rtl of neorv32_prim_mul is

  signal opa, opb : signed(DWIDTH downto 0);
  signal res : signed((2*DWIDTH)+1 downto 0);

begin

  -- Input Registers -----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  in_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      opa <= (others => '0');
      opb <= (others => '0');
    elsif rising_edge(clk_i) then
      if (en_i = '1') then
        opa <= signed((opa_i(opa_i'left) and opa_sn_i) & opa_i);
        opb <= signed((opb_i(opb_i'left) and opb_sn_i) & opb_i);
      end if;
    end if;
  end process in_reg;

  -- Output Register -----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  out_reg: process(clk_i)
  begin
    if rising_edge(clk_i) then -- no reset to improve DSP mapping
      res <= opa * opb;
    end if;
  end process out_reg;

  -- result --
  res_o <= std_ulogic_vector(res((2*DWIDTH)-1 downto 0));

end neorv32_prim_mul_rtl;


-- ========================================================================== --
-- NEORV32 - Primitives - Generic 64-Bit Counter Module                       --
-- -------------------------------------------------------------------------- --
-- High and low words are split across two individual registers to improve    --
-- timing by cutting the carry chain. The actual counter width can be trimmed --
-- via CWIDTH. [WARNING] High and low words of counter output cnt_o are _NOT_ --
-- synchronized!                                                              --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity neorv32_prim_cnt is
  generic (
    CWIDTH : natural range 0 to 64 -- actual counter width (0..64)
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic;                     -- global clock, rising edge
    -- global reset, low-active, async
    rstn_i : in  std_ulogic;
    inc_i  : in  std_ulogic;                     -- enable counter increment
    -- read/write access --
    we_i   : in  std_ulogic_vector(1 downto 0);  -- subword write enable
    data_i : in  std_ulogic_vector(31 downto 0); -- subword write data
    oe_i   : in  std_ulogic;                     -- output enable
    cnt_o  : out std_ulogic_vector(63 downto 0)  -- trimmed counter output
  );
end neorv32_prim_cnt;

architecture neorv32_prim_cnt_rtl of neorv32_prim_cnt is

  signal count : std_ulogic_vector(63 downto 0);
  signal carry, inc : std_ulogic_vector(0 downto 0);
  signal inc_lo, inc_hi : std_ulogic_vector(32 downto 0);

begin

  -- 64-Bit Counter (split across two 32-bit registers) ------------------------
  -- ---------------------------------------------------------------------------
  counter_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      count <= (others => '0');
      carry <= (others => '0');
    elsif rising_edge(clk_i) then
      -- low-word --
      if (we_i(0) = '1') then
        count(31 downto 0) <= data_i;
      else
        count(31 downto 0) <= inc_lo(31 downto 0);
      end if;
      carry(0) <= inc_lo(32); -- low-to-high carry
      -- high-word --
      if (we_i(1) = '1') then
        count(63 downto 32) <= data_i;
      else
        count(63 downto 32) <= inc_hi(31 downto 0);
      end if;
    end if;
  end process counter_core;

  -- increments --
  inc(0) <= inc_i;
  inc_lo <= std_ulogic_vector(unsigned('0' & count(31 downto  0))
                              + unsigned(inc));
  inc_hi <= std_ulogic_vector(unsigned('0' & count(63 downto 32))
                              + unsigned(carry));

  -- Output Gating and Trimming ------------------------------------------------
  -- ---------------------------------------------------------------------------
  trim: process(oe_i, count)
  begin
    cnt_o <= (others => '0');
    if (oe_i = '1') then
      -- unconnected counter bits should be optimized away
      cnt_o(CWIDTH-1 downto 0) <= count(CWIDTH-1 downto 0);
    end if;
  end process trim;

end neorv32_prim_cnt_rtl;