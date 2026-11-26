--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: targeted_top
-- Description: Two independent feedback loop shift registers for
--              targeted fault-injection experiments.
--              Their parity is output to LEDs to indicate
--              erroneous behaviour.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

use work.examples_utilities_pkg.all;

-- Two feedback loop shift registers for the targeted fault-injection example

entity targeted_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS". The value goes directly
    -- to clk_gen_wrapper.
    g_family       : string  := "7SERIES";
    -- The input clock frequency in MHz (100 MHz by default). The PLL wrapper
    -- uses it. The shift registers shift at each clock cycle.
    clk_freq       : integer range 1 to 400 := 100;
    -- The number of bits each shift register will have
    sr_bit_count   : integer range 0 to 512 := 16
  );
  Port ( 
    clk_i : in std_ulogic;
    data_o : out std_ulogic_vector(1 downto 0)
  );
end targeted_top;

architecture Structure of targeted_top is

    signal safe_clk : std_ulogic;
    
    signal sr_0, sr_1 : std_ulogic_vector(sr_bit_count - 1 downto 0);

    signal sr_par_0,
           sr_par_1 : std_ulogic := '0';
    
    component sr_module is
      Generic (
        mass_bit_count : integer range 0 to 512 := 8
      );
      Port ( 
        clk_i   : in std_ulogic;
        data_o  : out std_ulogic_vector(mass_bit_count - 1 downto 0)
      );
    end component;

    -- Keep both shift registers. They have the same inputs and generics, so
    -- synthesis would otherwise keep only one of them (decloning).
    attribute dont_touch : string;
    attribute dont_touch of shift_reg_0, shift_reg_1 : label is "TRUE";
    
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

    
    shift_reg_0:sr_module
      Generic map (
        mass_bit_count => sr_bit_count
      )
      Port map ( 
        clk_i   => safe_clk,
        data_o  => sr_0
      );
    
    shift_reg_1:sr_module
      Generic map (
        mass_bit_count => sr_bit_count
      )
      Port map ( 
        clk_i   => safe_clk,
        data_o  => sr_1
      );

    -- Even parity generation for each shift reg
    sr_0_par_gen:process(sr_0)
      variable vpar : std_ulogic;
      begin
        vpar := '0';
        for i in 0 to (sr_bit_count - 1) loop
            vpar := vpar XOR sr_0(i);
        end loop;
        sr_par_0 <= vpar;
    end process sr_0_par_gen;

    sr_1_par_gen:process(sr_1)
      variable vpar : std_ulogic;
      begin
        vpar := '0';
        for i in 0 to (sr_bit_count - 1) loop
            vpar := vpar XOR sr_1(i);
        end loop;
        sr_par_1 <= vpar;
    end process sr_1_par_gen;
    
    data_o(0) <= sr_par_0;
    data_o(1) <= sr_par_1;

end Structure;
