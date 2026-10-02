--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: heartbeat
-- Description: Generic toggling (heartbeat) module with a configurable
--              clock-cycle interval.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Toggling (heartbeat) module with generic time intervals

entity heartbeat is
  Generic (
    -- Max 5s (5000000000 ns) for 100MHz clock
    hb_interval : integer range 1 to 5*(10**8) := 1
  );
  Port ( 
    clk_i : in std_ulogic;
    heartbeat_o : out std_ulogic
  );
end heartbeat;

architecture Behavioral of heartbeat is

    signal heartbeat_count : integer range 0 to hb_interval := 0;
    signal heartbeat_sig   : std_ulogic := '0';

begin

    --Count up to the interval
    heartbeat_proc:process(clk_i)
        begin
            if rising_edge(clk_i) then 
                heartbeat_count <= heartbeat_count + 1;
                -- when the interval is reached
                if heartbeat_count + 1 = hb_interval then
                    heartbeat_sig <= NOT heartbeat_sig;     -- toggle the signal
                    heartbeat_count <= 0;                   -- clear the counter
                end if;
            end if;
    end process heartbeat_proc;

	heartbeat_o <= heartbeat_sig;
	
end Behavioral;
