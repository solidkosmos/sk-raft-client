----------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: bscan_user_register_io
-- Description: BSCAN-side shift/capture/update register pair (data_to_jtag/data_from_jtag) plus the
--              IDLE/DECIDE/HOLD FSM that infers, from the TAP's Shift-DR exit path, whether a given
--              JTAG sequence is a read or a write.
----------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

-- Uncomment the following library declaration if using
-- arithmetic functions with Signed or Unsigned values
--use IEEE.NUMERIC_STD.ALL;

entity bscan_user_register_io is
  Generic (
    data_to_jtag_len   : positive;
    data_from_jtag_len : positive 
  );
  Port (
    -- General reset --
    -- No active reset; relies on configuration-time initial values --
    --clear_i  : in std_ulogic; -- meant to clear the output register 
    
    -- BSCAN interfacing signals --
    tck     : in  std_ulogic;
    tms     : in  std_ulogic;
    tdi     : in  std_ulogic;
    tdo     : out std_ulogic;
    sel     : in  std_ulogic;
    shift   : in  std_ulogic;
    update  : in  std_ulogic;
    capture : in  std_ulogic;
    
    -- Control signals (available, acknowledge) --
    avail_o : out std_ulogic := '0'; -- asserted from update-write until next shift begins
    ack_o   : out std_ulogic := '0'; -- single-cycle strobe on capture (data_to_jtag_i latched)
    
    -- Data -- 
    data_to_jtag_i   : in  std_ulogic_vector(data_to_jtag_len - 1 downto 0);
    data_from_jtag_o : out std_ulogic_vector(data_from_jtag_len - 1 downto 0)
  );
end bscan_user_register_io;

architecture Behavioral of bscan_user_register_io is

    -- Internal Data Registers --
    signal data_user_reg_data_in  : std_ulogic_vector(data_from_jtag_len - 1 downto 0) := (others => '0');
    signal data_user_reg_data_out : std_ulogic_vector(data_to_jtag_len - 1 downto 0)   := (others => '0');
    signal updated_data_user_reg  : std_ulogic_vector(data_from_jtag_len - 1 downto 0) := (others => '0');

    -- Branch Checker States --
    type state is (IDLE, DECIDE, HOLD);
    signal check_rw, check_rw_nxt : state := IDLE;

    -- R/W Signal --
    signal rw : std_ulogic := '0';

begin

    DATA_IO: process(tck)
    begin
        if rising_edge(tck) then
            -- state machine that checks if the given sequence is read or write
            check_rw <= check_rw_nxt;

            -- Default values --
            ack_o <= '0';

            -- If SELECT flag is asserted (this register is targeted).
            if sel = '1' then

                --------------------- INPUT FROM JTAG ---------------------
                if shift = '1' then
                    avail_o <= '0'; -- clear
                    -- Shift user reg.
                    for i in (data_from_jtag_len - 2) downto 0 loop
                        data_user_reg_data_in(i) <= data_user_reg_data_in(i+1); -- shift chain
                    end loop;
                    data_user_reg_data_in(data_from_jtag_len - 1) <= tdi;
                end if;

                -- On update, commit only if the branch decision resolved to write.
                if update = '1' and rw = '1' then
                    avail_o <= '1'; -- set
                    updated_data_user_reg <= data_user_reg_data_in; -- latch data for our circuit
                end if;

                --------------------- OUTPUT TO JTAG ---------------------
                if capture = '1' then
                    -- Parallel load.
                    data_user_reg_data_out <= data_to_jtag_i; -- latch data meant for JTAG
                    ack_o <= '1'; -- single strobe acknowledge
                end if;

                if shift = '1' then
                    -- Shift user reg.
                    for i in (data_to_jtag_len - 2) downto 0 loop
                        data_user_reg_data_out(i) <= data_user_reg_data_out(i+1); -- shift chain
                    end loop;
                end if;

            end if;
        end if;
    end process DATA_IO;

    data_from_jtag_o <= updated_data_user_reg; -- send to output
    tdo <= data_user_reg_data_out(0); -- shift out to TDO, bit per bit

    -- CHECK READ WRITE COMB --
    -- Infers read/write intent from which TAP exit path is taken out of Shift-DR:
    --   Shift-DR --TMS=1--> Exit1-DR --TMS=1--> Update-DR : write
    --   Shift-DR --TMS=1--> Exit1-DR --TMS=0--> Pause-DR  : read (disallow write)
    check_read_write_comb_fsm: process(check_rw, shift, tms, update)
    begin
        check_rw_nxt <= IDLE; -- default

        case check_rw is
            when IDLE =>
                rw <= '0'; -- read by default
                if shift = '1' and tms = '1' then -- exiting Shift-DR
                    check_rw_nxt <= DECIDE;
                end if;

            when DECIDE =>
                check_rw_nxt <= HOLD; -- rw fixed until update arrives
                if tms = '1' then
                    rw <= '1'; -- direct to Update-DR: write
                else
                    rw <= '0'; -- to Pause-DR: read, disallow write
                end if;

            when HOLD =>
                check_rw_nxt <= HOLD; -- hold rw until this sequence ends
                if update = '1' then
                    check_rw_nxt <= IDLE;
                end if;

        end case;
    end process check_read_write_comb_fsm;

end Behavioral;