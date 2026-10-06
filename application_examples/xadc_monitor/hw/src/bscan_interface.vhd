--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: bscan_interface
-- Description: Top-level JTAG/BSCAN wrapper. It connects a BSCAN User
--              Register IO instance to a BSCAN Primitive Wrapper. It gives
--              the design a read/write data path (data_to_jtag_i/
--              data_from_jtag_o) and avail/ack handshake signals. If sync
--              is true, two flip-flops synchronize avail/ack to clk_i. The
--              data path is not synchronized.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity bscan_interface is
  Generic (
    jtag_chain : integer range 1 to 4;
    data_len_r : positive; 
    data_len_w : positive;
    sync       : boolean := true
  );
  Port ( 
  ----- CLK INPUT FOR CDC -----
    clk_i : in std_ulogic;
  ----- TCK OUTPUT FOR CDC, LOGIC ISOLATION -----
    tck_o : out std_ulogic;
  ----- DRCK OUTPUT FOR CDC, LOGIC ISOLATION -----
    drck_o : out std_ulogic;
  ----- DATA PATH -----
    data_to_jtag_i   : in std_ulogic_vector(data_len_r - 1 downto 0);
    data_from_jtag_o : out std_ulogic_vector(data_len_w - 1 downto 0);
  ----- CONTROL SIGNALS ------
    ux_avail_o       : out std_ulogic;
    ux_ack_o         : out std_ulogic 
  );
end bscan_interface;

architecture Behavioral of bscan_interface is

    signal ux_buf_tck          :  std_ulogic;
    signal ux_tck              :  std_ulogic; 
    signal ux_drck             :  std_ulogic; 
    signal ux_tms              :  std_ulogic;
    signal ux_tdi              :  std_ulogic;
    signal ux_tdo              :  std_ulogic;
    signal ux_sel              :  std_ulogic;
    signal ux_shift            :  std_ulogic;
    signal ux_update           :  std_ulogic;
    signal ux_capture          :  std_ulogic;     
    signal ux_avail            :  std_ulogic;
    signal ux_ack              :  std_ulogic;         
    signal ux_data_to_jtag_i   :  std_ulogic_vector(data_len_r - 1 downto 0);
    signal ux_data_from_jtag_o :  std_ulogic_vector(data_len_w - 1 downto 0);
    
    -- CDC CONTROL SIGNALS -- 
    signal avail_d0, avail_sync : std_ulogic; 
    signal ack_d0, ack_sync : std_ulogic;

begin

    
    ----------- USER(X) READ/WRITE -----------------------------
    bscan_interface_read_write_uX:entity work.bscan_user_register_io
      Generic map(
         data_to_jtag_len    => data_len_r,
         data_from_jtag_len  => data_len_w
      )
      Port map (
          clk_i             => ux_buf_tck          , 
          tms_i             => ux_tms              ,
          tdi_i             => ux_tdi              ,
          tdo_o             => ux_tdo              ,
          sel_i             => ux_sel              ,
          shift_i           => ux_shift            ,
          update_i          => ux_update           ,
          capture_i         => ux_capture          ,
          avail_o           => ux_avail            ,
          ack_o             => ux_ack              ,
          data_to_jtag_i    => data_to_jtag_i      ,
          data_from_jtag_o  => data_from_jtag_o 
                       
      ); 
       
    
    
    bscan_primitive_uX:entity work.bscan_primitive_wrapper
      Generic map (
            JTAG_CHAIN    => jtag_chain
      )
      Port map (
            tck                   => ux_tck              ,
            drck                  => ux_drck             ,
            tms                   => ux_tms              ,
            tdi                   => ux_tdi              ,
            tdo                   => ux_tdo              ,
            sel                   => ux_sel              ,
            shift                 => ux_shift            ,
            update                => ux_update           ,
            capture               => ux_capture          ,
            reset                 => open,
            runtest               => open
      );
    
    sync_sigs_on:if sync generate
        sync_proc:process(clk_i)
            begin
                if rising_edge(clk_i) then
                    -- DOUBLE FLOPPED CONTROL SIGNALS --
                    -- FOR CLEANER CODE IN THE TOP --
                    avail_d0   <= ux_avail;
                    ack_d0     <= ux_ack ;
                    avail_sync <= avail_d0;
                    ack_sync   <= ack_d0 ;
                end if;
        end process sync_proc;
        ux_avail_o <= avail_sync;
        ux_ack_o   <= ack_sync ;
    end generate sync_sigs_on;
    
    sync_sigs_off:if not sync generate
        ux_avail_o <= ux_avail;
        ux_ack_o   <= ux_ack ;
    end generate sync_sigs_off;
    
    tck_BUFG_inst : BUFG
    Port map (
       O => ux_buf_tck, 
       I => ux_tck  
    );
    
    drck_o <= ux_drck;
    tck_o  <= ux_tck;
    
end Behavioral;


