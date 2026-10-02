--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
--
-- Module Name: bscan_user_register_io
-- Description: BSCAN-side shift/capture/update register pair
--              (data_to_jtag/data_from_jtag) plus the IDLE/DECIDE/HOLD FSM
--              that infers, from the TAP's Shift-DR exit path, whether a
--              given JTAG sequence is a read or a write. FSM and rw are
--              both clocked here (no separate combinational next-state
--              process) so rw is a real flip-flop, not an inferred latch.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity bscan_user_register_io is
  Generic (
    data_to_jtag_len   : positive;
    data_from_jtag_len : positive
  );
  Port (
    -- BSCAN interfacing signals --
    clk_i     : in  std_ulogic;
    tms_i     : in  std_ulogic;
    tdi_i     : in  std_ulogic;
    tdo_o     : out std_ulogic;
    sel_i     : in  std_ulogic;
    shift_i   : in  std_ulogic;
    update_i  : in  std_ulogic;
    capture_i : in  std_ulogic;

    -- Control signals (available, acknowledge) --
    -- avail_o: asserted from update-write until next shift begins
    avail_o : out std_ulogic := '0';
    -- ack_o: single-cycle strobe on capture (data_to_jtag_i latched)
    ack_o   : out std_ulogic := '0';

    -- Data --
    data_to_jtag_i   : in  std_ulogic_vector(data_to_jtag_len - 1 downto 0);
    data_from_jtag_o : out std_ulogic_vector(data_from_jtag_len - 1 downto 0)
  );
end bscan_user_register_io;

architecture Behavioral of bscan_user_register_io is

    -- Internal Data Registers --
    signal data_user_reg_data_in  :
        std_ulogic_vector(data_from_jtag_len - 1 downto 0) := (others => '0');
    signal data_user_reg_data_out :
        std_ulogic_vector(data_to_jtag_len - 1 downto 0)   := (others => '0');
    signal updated_data_user_reg  :
        std_ulogic_vector(data_from_jtag_len - 1 downto 0) := (others => '0');

    -- Branch Checker State --
    -- Infers read/write intent from which TAP exit path is taken out of
    -- Shift-DR:
    --   Shift-DR --TMS=1--> Exit1-DR --TMS=1--> Update-DR : write
    --   Shift-DR --TMS=1--> Exit1-DR --TMS=0--> Pause-DR  : read
    --   (disallow write)
    type state is (IDLE, DECIDE, HOLD);
    signal check_rw : state := IDLE;

    -- R/W Flag Signal -- registered alongside check_rw below, both clocked
    -- on clk_i only
    signal rw : std_ulogic := '0';

begin

    data_io_proc: process(clk_i)
    begin
        if rising_edge(clk_i) then

            -- Default values --
            ack_o <= '0';

            -- If SELECT flag is asserted (this register is targeted).
            if sel_i = '1' then

                -- Read/write branch decision -- fully registered,
                -- current-state case.
                case check_rw is
                    when IDLE =>
                        rw <= '0'; -- read by default
                        -- exiting Shift-DR
                        if shift_i = '1' and tms_i = '1' then
                            check_rw <= DECIDE;
                        end if;

                    when DECIDE =>
                        -- '1': direct to Update-DR (write);
                        -- '0': to Pause-DR (read)
                        rw       <= tms_i;
                        check_rw <= HOLD;  -- rw fixed until update arrives

                    when HOLD =>
                        if update_i = '1' then
                            check_rw <= IDLE;
                        end if;
                        -- rw and check_rw otherwise hold: real registers,
                        -- no re-assignment needed
                end case;

                --------------------- INPUT FROM JTAG ---------------------
                if shift_i = '1' then
                    avail_o <= '0'; -- clear
                    -- Shift user reg.
                    for i in (data_from_jtag_len - 2) downto 0 loop
                        -- shift chain
                        data_user_reg_data_in(i) <= data_user_reg_data_in(i+1);
                    end loop;
                    data_user_reg_data_in(data_from_jtag_len - 1) <= tdi_i;
                end if;

                -- On update, commit only if the branch decision resolved
                -- to write.
                if update_i = '1' and rw = '1' then
                    avail_o <= '1'; -- set
                    -- latch data for our circuit
                    updated_data_user_reg <= data_user_reg_data_in;
                end if;

                --------------------- OUTPUT TO JTAG ---------------------
                if capture_i = '1' then
                    -- Parallel load.
                    -- latch data meant for JTAG
                    data_user_reg_data_out <= data_to_jtag_i;
                    ack_o <= '1'; -- single strobe acknowledge
                end if;

                if shift_i = '1' then
                    -- Shift user reg.
                    for i in (data_to_jtag_len - 2) downto 0 loop
                        -- shift chain
                        data_user_reg_data_out(i) <=
                            data_user_reg_data_out(i+1);
                    end loop;
                end if;

            end if;
        end if;
    end process data_io_proc;

    data_from_jtag_o <= updated_data_user_reg; -- send to output
    tdo_o <= data_user_reg_data_out(0); -- shift out to TDO, bit per bit

end Behavioral;