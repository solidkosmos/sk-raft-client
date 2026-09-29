--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: bscan_primitive_wrapper
-- Description: Thin wrapper exposing BSCANE2 as a single packageable
--              component.
--------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity bscan_primitive_wrapper is
  Generic (
    JTAG_CHAIN    : integer range 1 to 4 := 1
  );
  Port (
    tck     : out std_ulogic;
    drck    : out std_ulogic;
    tms     : out std_ulogic;
    tdi     : out std_ulogic;
    tdo     : in  std_ulogic;
    sel     : out std_ulogic;
    shift   : out std_ulogic;
    update  : out std_ulogic;
    capture : out std_ulogic;
    reset   : out std_ulogic;
    runtest : out std_ulogic
  );
end bscan_primitive_wrapper;

architecture Behavioral of bscan_primitive_wrapper is
begin

    BSCANE2_inst : BSCANE2
      Generic map (
        JTAG_CHAIN => JTAG_CHAIN
      )
      Port map (
        TCK     => tck,
        DRCK    => drck,       
        TMS     => tms,
        TDI     => tdi,
        TDO     => tdo,
        SEL     => sel,
        SHIFT   => shift,
        UPDATE  => update,
        CAPTURE => capture,
        RESET   => reset,
        RUNTEST => runtest
      );


end Behavioral;