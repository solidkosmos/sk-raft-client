----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: examples_utilities_pkg
-- Description: Shared component declarations for the reusable building blocks used
--              across the get-started examples (BSCAN interface, clock generator,
--              and the two BRAM wrappers) -- one place to instantiate from instead
--              of each example hand-copying (and risking drift on) its own copy.
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

package examples_utilities_pkg is

    -- Interfacing with BSCAN.
    -- This component spawns:
    -- 1) A BSCAN User Register IO instance -- serializes/deserializes data to/from JTAG BSCAN registers
    -- 2) A BSCAN Primitive Wrapper -- wraps the BSCAN USER register primitive
    -- per bscan_interface instance.
    component bscan_interface is
      Generic (
        jtag_chain : integer range 1 to 4;
        data_len_r : positive;
        data_len_w : positive;
        sync       : boolean := true
      );
      Port (
        ----- CLK INPUT FOR CDC HANDLING -----
        clk_i  : in  std_ulogic;
        ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        tck_o  : out std_ulogic;
        ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
        drck_o : out std_ulogic;
        ----- DATA PATH -----
        data_to_jtag_i   : in  std_ulogic_vector(data_len_r - 1 downto 0);
        data_from_jtag_o : out std_ulogic_vector(data_len_w - 1 downto 0);
        ----- CONTROL SIGNALS -----
        ux_avail_o : out std_ulogic;
        ux_ack_o   : out std_ulogic
      );
    end component;

    -- Portable, family-selecting, free-running PLL passthrough wrapper
    -- (7-series / UltraScale / UltraScale+).
    component clk_gen_wrapper is
      Generic (
        g_family          : string := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS"
        g_clkin_period_ns : real    := 10.0
      );
      Port (
        clk_i    : in  std_ulogic;
        clk_o    : out std_ulogic;
        locked_o : out std_ulogic
      );
    end component;


end package examples_utilities_pkg;
