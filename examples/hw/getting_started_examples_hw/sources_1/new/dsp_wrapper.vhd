----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: dsp_wrapper
-- Description: Minimal signed multiply-accumulate-free wrapper (P = A*B, registered)
--              intended to map onto a single DSP48 tile via synthesis inference
--              rather than direct primitive instantiation.
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity dsp_wrapper is
  Generic (
    a_len : positive := 18; -- operand A width -- keep <= 18 bits so this maps onto ONE DSP48 tile on both 7-series (DSP48E1) and UltraScale/UltraScale+ (DSP48E2)
    b_len : positive := 18  -- operand B width -- DSP48E1/E2's B input is 18 bits wide on both families; this is the hard ceiling for a single-tile multiply
  );
  Port (
    clk_i : in  std_ulogic;
    ce_i  : in  std_ulogic := '1';                             -- pipeline clock enable, gates the output register
    a_i   : in  std_ulogic_vector(a_len - 1 downto 0);          -- signed operand A
    b_i   : in  std_ulogic_vector(b_len - 1 downto 0);          -- signed operand B
    p_o   : out std_ulogic_vector(a_len + b_len - 1 downto 0)   -- signed product, A*B (registered, one clk_i latency)
  );
end dsp_wrapper;

architecture Behavioral of dsp_wrapper is

    -- Attribute name/placement matches Xilinx's documented USE_DSP synthesis
    -- attribute: applied to the signal holding the arithmetic result, hinting
    -- synthesis to map it onto a hard DSP48 tile instead of fabric logic.
    signal product : std_ulogic_vector(a_len + b_len - 1 downto 0);
    attribute use_dsp : string;
    attribute use_dsp of product : signal is "yes";

begin

    mult_reg : process(clk_i)
    begin
        if rising_edge(clk_i) then
            if ce_i = '1' then
                product <= std_ulogic_vector(signed(a_i) * signed(b_i));
            end if;
        end if;
    end process mult_reg;

    p_o <= product;

end Behavioral;