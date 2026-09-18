----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: targeted_top
-- Description: Two independent heartbeat counters (slow, fast) for targeted fault-injection experiments.
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

use work.examples_utilities_pkg.all;

-- Two heartbeat (slow, fast) module for targeted fault injection example

entity targeted_top is
  Generic (
    g_family       : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
    clk_freq       : integer range 1 to 400 := 100;   -- Set the clock frequency to make the intervals time accurate (default 100MHz)
    slow_heartbeat_interval : integer range 1 to 5*(10**8) := 1*(10**8);    -- Max 5s (500,000,000 cycles) for 100MHz
    fast_heartbeat_interval : integer range 1 to 5*(10**8) := (1*(10**8))/4 -- Set at default a quarter of a second
  );
  Port ( 
    clk_i : in std_ulogic;
    heartbeat_slow_o : out std_ulogic;
    heartbeat_fast_o : out std_ulogic
  );
end targeted_top;

architecture Structure of targeted_top is

    signal safe_clk : std_ulogic;
    
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
      generic map (
        g_family          => g_family,
        g_clkin_period_ns => 1000.0 / real(clk_freq)
      )
      port map (
        clk_i  => clk_i,
        clk_o => safe_clk,
        locked_o => open
      );

    
    slow_heartbeat:heartbeat
    Generic map (
      hb_interval => slow_heartbeat_interval
    )
    Port map ( 
      clk_i       => clk_i,
      heartbeat_o => heartbeat_slow_o
    );
    
    fast_heartbeat:heartbeat
    Generic map (
      hb_interval => fast_heartbeat_interval
    )
    Port map ( 
      clk_i       => clk_i,
      heartbeat_o => heartbeat_fast_o
    );


end Structure;
