--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: bscan_user_register_io
-- Description: BSCAN-side shift/capture/update register pair
--              (data_to_jtag/data_from_jtag) and the IDLE/DECIDE/HOLD FSM.
--              The FSM uses the TAP exit path from Shift-DR to find if a
--              JTAG sequence is a read or a write. The FSM and rw are both
--              clocked here (there is no separate combinational next-state
--              process). Thus rw is a real flip-flop, not an inferred latch.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity bscan_user_register_io is
  Generic (
    data_to_jtag_len   : positive;
    data_from_jtag_len : positive
  );
  Port (
    -- BSCAN interface signals --
    clk_i     : in  std_ulogic;
    tms_i     : in  std_ulogic;
    tdi_i     : in  std_ulogic;
    tdo_o     : out std_ulogic;
    sel_i     : in  std_ulogic;
    shift_i   : in  std_ulogic;
    update_i  : in  std_ulogic;
    capture_i : in  std_ulogic;

    -- Control signals (available, acknowledge) --
    -- avail_o: set at the update of a write, cleared when the next shift starts
    avail_o : out std_ulogic := '0';
    -- ack_o: strobe of one cycle at capture (data_to_jtag_i is latched)
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
    -- The FSM finds the read or write intent from the TAP exit path out of
    -- Shift-DR:
    --   Shift-DR --TMS=1--> Exit1-DR --TMS=1--> Update-DR : write
    --   Shift-DR --TMS=1--> Exit1-DR --TMS=0--> Pause-DR  : read
    --   (write is not allowed)
    type state is (IDLE, DECIDE, HOLD);
    signal check_rw : state := IDLE;

    -- R/W flag signal. The process below registers rw together with
    -- check_rw. Both use only clk_i as the clock.
    signal rw : std_ulogic := '0';

begin

    data_io_proc: process(clk_i)
    begin
        if rising_edge(clk_i) then

            -- Default values --
            ack_o <= '0';

            -- If the SEL flag is asserted, JTAG targets this register.
            if sel_i = '1' then

                -- Read/write branch decision. The decision is fully
                -- registered and uses a case on the current state.
                case check_rw is
                    when IDLE =>
                        rw <= '0'; -- read is the default
                        -- The TAP leaves Shift-DR.
                        if shift_i = '1' and tms_i = '1' then
                            check_rw <= DECIDE;
                        end if;

                    when DECIDE =>
                        -- '1': go directly to Update-DR (write).
                        -- '0': go to Pause-DR (read).
                        rw       <= tms_i;
                        check_rw <= HOLD;  -- rw stays fixed until the update

                    when HOLD =>
                        if update_i = '1' then
                            check_rw <= IDLE;
                        end if;
                        -- Otherwise rw and check_rw keep their values. They
                        -- are real registers, so no new assignment is necessary.
                end case;

                --------------------- INPUT FROM JTAG ---------------------
                if shift_i = '1' then
                    avail_o <= '0'; -- clear
                    -- Shift the user register.
                    for i in (data_from_jtag_len - 2) downto 0 loop
                        -- shift chain
                        data_user_reg_data_in(i) <= data_user_reg_data_in(i+1);
                    end loop;
                    data_user_reg_data_in(data_from_jtag_len - 1) <= tdi_i;
                end if;

                -- At update, commit the data only if the branch decision
                -- is a write.
                if update_i = '1' and rw = '1' then
                    avail_o <= '1'; -- set
                    -- Latch the data for the user logic.
                    updated_data_user_reg <= data_user_reg_data_in;
                end if;

                --------------------- OUTPUT TO JTAG ---------------------
                if capture_i = '1' then
                    -- Parallel load.
                    -- Latch the data for JTAG.
                    data_user_reg_data_out <= data_to_jtag_i;
                    ack_o <= '1'; -- acknowledge strobe of one cycle
                end if;

                if shift_i = '1' then
                    -- Shift the user register.
                    for i in (data_to_jtag_len - 2) downto 0 loop
                        -- shift chain
                        data_user_reg_data_out(i) <=
                            data_user_reg_data_out(i+1);
                    end loop;
                end if;

            end if;
        end if;
    end process data_io_proc;

    data_from_jtag_o <= updated_data_user_reg; -- Send to the output.
    tdo_o <= data_user_reg_data_out(0); -- Send to TDO, one bit at a time.

end Behavioral;