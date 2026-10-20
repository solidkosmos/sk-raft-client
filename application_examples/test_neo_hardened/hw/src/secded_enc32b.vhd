--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: secded_enc32b
-- Description: 32-bit SECDED encoder in fabric logic, used for the
--              register-file hardening. Code: extended Hamming (39,32). The 32
--              data bits take the codeword positions 1..38 that are not a power
--              of two (3, 5, 6, 7, 9, ...). Check bit j (0..5) is the XOR of
--              the data bits whose position has bit j set. Check bit 6 is the
--              overall parity of the data bits and check bits 0..5.
--              secded_dec32b decodes this code.
--------------------------------------------------------------------------------


library ieee;
use ieee.std_logic_1164.all;

entity secded_enc32b is
  port (
    data_i : in  std_ulogic_vector(31 downto 0); -- data word
    -- (5:0) Hamming check bits, (6) overall parity
    par_o  : out std_ulogic_vector(6 downto 0)
  );
end entity secded_enc32b;

architecture rtl of secded_enc32b is

  -- codeword position (3..38) of each data bit --
  type pos_t is array (0 to 31) of natural;

  function data_pos_f return pos_t is
    variable res : pos_t;
    variable pos : natural := 3;
  begin
    for i in 0 to 31 loop
      -- skip the positions of the check bits (powers of two)
      while (pos = 4) or (pos = 8) or (pos = 16) or (pos = 32) loop
        pos := pos + 1;
      end loop;
      res(i) := pos;
      pos    := pos + 1;
    end loop;
    return res;
  end function data_pos_f;

  constant pos_c : pos_t := data_pos_f;

begin

  encode: process(data_i)
    variable chk     : std_ulogic_vector(5 downto 0);
    variable all_par : std_ulogic;
  begin
    -- Hamming check bits --
    chk := (others => '0');
    for i in 0 to 31 loop
      for j in 0 to 5 loop
        if ((pos_c(i) / (2**j)) mod 2) = 1 then
          chk(j) := chk(j) xor data_i(i);
        end if;
      end loop;
    end loop;
    -- overall parity of data and check bits --
    all_par := '0';
    for i in 0 to 31 loop
      all_par := all_par xor data_i(i);
    end loop;
    for j in 0 to 5 loop
      all_par := all_par xor chk(j);
    end loop;
    par_o <= all_par & chk;
  end process encode;

end architecture rtl;
