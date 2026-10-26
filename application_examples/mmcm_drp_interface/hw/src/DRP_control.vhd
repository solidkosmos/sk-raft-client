-------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: DRP_control
-- Description: The FSM that controls the read/write operations issued through 
--              the BSCAN interface. It takes in packets that consist of the
--              MMCM RST flag, R/W flag, address select and data.
--              It also include a watchdog timer that checks if the DRDY 
--              signal is never asserted in the given time window,
--              setting an error signal for the driving software to handle.

--              The FSM walks through these states:
--
--              IDLE : Awaits for a new command to be issued,
--                     then it asserts RST to the MMCM and 
--                     goes to DRP_ACCESS

--              DRP_ACCESS : Checks if the MMCM RST bit is set. 
--                     Then it sets the selected address and 
--                     data, asserts DEN, DWE = R/W flag (1 = write,
--                     0 = read), clearing the WDT and moving  
--                     to WAIT_FOR_DRDY, else it returns back to IDLE
              
--              WAIT_FOR_DRDY : Deasserts DEN and DWE and waits  
--                     for DRDY to be asserted before transitioning
--                     to AWAIT_CMD. If the WDT reaches timeout,
--                     the error signal is asserted and 
--                     the FSM is sent to AWAIT_CMD 
             
--              AWAIT_CMD : Looks for a new access to be issued,
--                     samples the packet issued and then 
--                     returns to DRP_ACCESS
             
--              Reference : XAPP888 (v1.8) : MMCM and PLL Dynamic
--                                           Reconfiguration
-------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity DRP_control is
  Port ( 
    clk_i     : in std_ulogic;
    rstn_i    : in std_ulogic;
    new_cmd_i : in std_ulogic;
--  Each packet consists of:
--  (24)    MMCM RST
--  (23)    R/W flag 
--  [22:16] ADDR 
--  [15:0]  DATA
    pckt_i     : in std_ulogic_vector(24 downto 0);
    drdy_i     : in std_ulogic;
    mmcm_rst_o : out std_ulogic;
    addr_o     : out std_ulogic_vector(6 downto 0);
    data_o     : out std_ulogic_vector(15 downto 0);
    den_o      : out std_ulogic;
    dwe_o      : out std_ulogic;
    
    -- Set a sticky error signal that is triggered when
    -- a DRP access resulted in a timeout 
    drp_err_o : out std_ulogic
    
  );
end DRP_control;

architecture Behavioral of DRP_control is 
    
    signal new_cmd_s  : std_ulogic;
    signal drdy_s     : std_ulogic;
    signal mmcm_rst_s : std_ulogic;
    signal rw_flag    : std_ulogic;
    signal addr_s     : std_ulogic_vector(6 downto 0); 
    signal data_s     : std_ulogic_vector(15 downto 0);
    signal den_s      : std_ulogic;
    signal dwe_s      : std_ulogic;
    
    signal drp_err_s  : std_ulogic;
    
    type drp_ctrl_FSM_states is (IDLE, DRP_ACCESS, WAIT_FOR_DRDY, AWAIT_CMD);
    signal drp_ctrl_FSM : drp_ctrl_FSM_states := IDLE;

begin

    drp_control_fsm:process(clk_i, rstn_i)
        -- Set a watchdog counter to check if the 
        -- DRDY signal takes too long to be asserted 
        variable wd_cntr : natural range 0 to 1023 := 0;
        begin 
            if rstn_i = '0' then 
                new_cmd_s <= '0';
                drdy_s    <= '0';
                mmcm_rst_s <= '1'; 
                rw_flag <= '0'; 
                addr_s  <= (others => '0');
                data_s  <= (others => '0'); 
                den_s   <= '0';
                dwe_s   <= '0';
                drp_err_s <= '0';
                drp_ctrl_FSM <= IDLE;  
            elsif rising_edge(clk_i) then
                new_cmd_s <= new_cmd_i;
                drdy_s    <= drdy_i;
                case drp_ctrl_FSM is 
                    when IDLE => 
                        mmcm_rst_s <= '0';
                        rw_flag <= '0'; 
                        addr_s  <= (others => '0');
                        data_s  <= (others => '0'); 
                        den_s   <= '0';
                        dwe_s   <= '0';
                        drp_ctrl_FSM <= IDLE;
                        if new_cmd_s = '1' then 
                            mmcm_rst_s <= pckt_i(24);
                            rw_flag <= pckt_i(23);
                            addr_s  <= pckt_i(22 downto 16);
                            data_s  <= pckt_i(15 downto 0); 
                            drp_ctrl_FSM <= DRP_ACCESS;
                        end if;
                     when DRP_ACCESS => 
                        if mmcm_rst_s = '1' then
                            -- Since we unpacked and the address is sampled
                            -- we assert DEN to set it in the MMCM register 
                            -- and move to WAIT_FOR_DRDY.
                            den_s   <= '1';
                            dwe_s   <= rw_flag;
                            wd_cntr := 0;
                            drp_ctrl_FSM <= WAIT_FOR_DRDY;
                        else 
                            drp_ctrl_FSM <= IDLE;
                        end if;
                     when WAIT_FOR_DRDY =>
                        den_s   <= '0';
                        dwe_s   <= '0';
                        wd_cntr := wd_cntr + 1;
                        if wd_cntr = 1023 then
                            drp_err_s <= '1';
                            -- Send the FSM to AWAIT_CMD in order to 
                            -- keep the MMCM at a reset state 
                            -- letting the driving software decide
                            -- further operation
                            drp_ctrl_FSM <= AWAIT_CMD;
                        end if;
                        if drdy_s = '1' then 
                            -- Release the error signal (if it's set) 
                            -- when a successful transaction has occured
                            drp_err_s <= '0';
                            drp_ctrl_FSM <= AWAIT_CMD;
                        end if;
                     when AWAIT_CMD =>
                        if new_cmd_s = '1' then 
                            mmcm_rst_s <= pckt_i(24);
                            rw_flag <= pckt_i(23);
                            addr_s  <= pckt_i(22 downto 16);
                            data_s  <= pckt_i(15 downto 0); 
                            drp_ctrl_FSM <= DRP_ACCESS;
                        end if;
                end case;
            end if;
    end process;
                        
    mmcm_rst_o <= mmcm_rst_s;
    addr_o     <= addr_s;   
    data_o     <= data_s;    
    den_o      <= den_s;     
    dwe_o      <= dwe_s; 
    drp_err_o  <= drp_err_s;                    
                            

end Behavioral;
