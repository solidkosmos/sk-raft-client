--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: targeted_top
-- Description: Two independent heartbeat counters (slow, fast) for
--              targeted fault-injection experiments.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

use work.examples_utilities_pkg.all;

-- Two heartbeat (slow, fast) module for targeted fault injection example

entity targeted_top is
  Generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to
    -- clk_gen_wrapper
    g_family       : string  := "7SERIES";
    -- Set the clock frequency to make the intervals time accurate
    -- (default 100MHz)
    clk_freq       : integer range 1 to 400 := 100;
    -- Max 5s (500,000,000 cycles) for 100MHz
    slow_heartbeat_interval : integer range 1 to 5*(10**8) := 1*(10**8);
    -- Set at default a quarter of a second
    fast_heartbeat_interval : integer range 1 to 5*(10**8) := (1*(10**8))/4
  );
  Port ( 
    clk_i : in std_ulogic;
    data_o : out std_ulogic_vector(1 downto 0)
  );
end targeted_top;

architecture Structure of targeted_top is

    signal safe_clk : std_ulogic;
    
    signal heartbeat_slow_sig,
           heartbeat_fast_sig : std_ulogic := '0';
    
    component heartbeat is
      Generic (
        hb_interval : integer range 1 to 5*(10**8) := 1 
      );
      Port ( 
        clk_i : in std_ulogic;
        heartbeat_o : out std_ulogic
      );
    end component;
    
begin
    
    -- Condition the incoming clock through the portable PLL wrapper. Period
    -- (ns) is derived straight from clk_freq (MHz) so there's only one
    -- source of truth for the design's operating frequency.
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

    
    slow_heartbeat:heartbeat
    Generic map (
      hb_interval => slow_heartbeat_interval
    )
    Port map ( 
      clk_i       => safe_clk,
      heartbeat_o => heartbeat_slow_sig
    );
    
    fast_heartbeat:heartbeat
    Generic map (
      hb_interval => fast_heartbeat_interval
    )
    Port map ( 
      clk_i       => safe_clk,
      heartbeat_o => heartbeat_fast_sig
    );
    
    data_o(0) <= heartbeat_slow_sig;
    data_o(1) <= heartbeat_fast_sig;

end Structure;
