--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: secded_dec32b
-- Description: 32-bit SECDED decoder in fabric logic, used for the
--              register-file hardening. It decodes the extended Hamming (39,32)
--              code of secded_enc32b:
--                no error           : corr_o = 0, uncorr_o = 0
--                one bit in error   : data_o is corrected, corr_o = 1
--                  (data or check bit)
--                two bits in error  : data_o is not corrected,
--                                     uncorr_o = 1
--              Three or more bits in error can be miscorrected (limit
--              of the code).
--------------------------------------------------------------------------------


library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity secded_dec32b is
  port (
    data_i   : in  std_ulogic_vector(31 downto 0); -- stored data
    -- stored check bits, (6) overall parity
    par_i    : in  std_ulogic_vector(6 downto 0);
    data_o   : out std_ulogic_vector(31 downto 0); -- corrected data
    -- single-bit error found and corrected
    corr_o   : out std_ulogic;
    -- double-bit error found, data_o not corrected
    uncorr_o : out std_ulogic
  );
end entity secded_dec32b;

architecture rtl of secded_dec32b is

  -- codeword position (3..38) of each data bit, as in secded_enc32b --
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

  decode: process(data_i, par_i)
    variable syn     : std_ulogic_vector(5 downto 0);
    variable syn_n   : natural range 0 to 63;
    variable all_par : std_ulogic;
    variable dat     : std_ulogic_vector(31 downto 0);
    variable found   : boolean;
  begin
    -- syndrome: stored check bits XOR check bits of the stored data --
    syn := par_i(5 downto 0);
    for i in 0 to 31 loop
      for j in 0 to 5 loop
        if ((pos_c(i) / (2**j)) mod 2) = 1 then
          syn(j) := syn(j) xor data_i(i);
        end if;
      end loop;
    end loop;
    syn_n := to_integer(unsigned(syn));

    -- overall parity of the full codeword: '1' for an odd number of bit errors
    -- --
    all_par := '0';
    for i in 0 to 31 loop
      all_par := all_par xor data_i(i);
    end loop;
    for j in 0 to 6 loop
      all_par := all_par xor par_i(j);
    end loop;

    dat      := data_i;
    corr_o   <= '0';
    uncorr_o <= '0';

    if (all_par = '1') then
      -- one bit in error --
      if (syn_n = 0) or (syn_n = 1) or (syn_n = 2) or (syn_n = 4) or
         (syn_n = 8) or (syn_n = 16) or (syn_n = 32) then
        -- error in a check bit or in the overall parity bit: the data is
        -- correct
        corr_o <= '1';
      else
        -- error in a data bit: flip the data bit at the syndrome position
        found := false;
        for i in 0 to 31 loop
          if (pos_c(i) = syn_n) then
            dat(i) := not dat(i);
            found  := true;
          end if;
        end loop;
        if found then
          corr_o <= '1';
        else
          -- syndrome outside the codeword (39..63): three or more bits in error
          uncorr_o <= '1';
        end if;
      end if;
    elsif (syn_n /= 0) then
      -- two bits in error: detected, not correctable --
      uncorr_o <= '1';
    end if;

    data_o <= dat;
  end process decode;

end architecture rtl;
