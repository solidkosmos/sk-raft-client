--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: sem_arbitration_7series
-- Description: Top of the 7-series SEM arbitration example. The SEM
--              controller (sem_0, PG036) and SK-RAFT share the
--              configuration memory. SK-RAFT controls the icap_grant input
--              of the SEM through BSCAN USER2.
--
--   The SEM connects directly to ICAPE2 and FRAME_ECCE2. The 7-series SEM
--   reads icap_grant only at boot: it waits until icap_grant is 1, and
--   then it initializes. SK-RAFT injects while the SEM is idle (I
--   command), with sem_clk stopped (USER1 = 0), and then sends O to make
--   the SEM scan again.
--
--   Clock tree: clk_i -> safe-startup PLL (clk_gen_wrapper) -> safe_clk
--   -> BUFGCE (enable from USER1) -> sem_clk. The SEM, the ICAPE2 and the
--   monitor interface use sem_clk. Only the USER1 synchronizer uses the
--   ungated safe_clk, so that the clock can be enabled again.
--
--   BSCAN registers:
--     USER1  write: clock enable (1 = sem_clk operates, 0 = stopped).
--                   0 after configuration.
--            read : the value written last
--     USER2  write: icap_grant of the SEM (0 after configuration)
--            read : icap_request of the SEM
--     USER3  read : the 8 SEM status signals (PG036 status interface)
--            bit 0  status_heartbeat       pulses while the SEM scans
--                                          (observation). A single read
--                                          usually shows 0.
--            bit 1  status_initialization  the SEM initializes
--            bit 2  status_observation     the SEM scans for errors
--            bit 3  status_correction      the SEM corrects an error
--            bit 4  status_classification  the SEM classifies an error
--            bit 5  status_injection       the SEM injects an error
--            bit 6  status_essential       the last error was essential
--            bit 7  status_uncorrectable   the last error was
--                                          uncorrectable
--            Bits 5:1 all 0 = idle. Bits 5:1 all 1 = fatal error (halt).
--
--   The SEM monitor port goes to the UART of the board (monitor_interface,
--   9600 8-N-1).
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity sem_arbitration_7series is
  Port (
    -- 100 MHz board clock
    clk_i  : in  std_ulogic;
    -- UART to and from the host (SEM monitor, 9600 8-N-1)
    tx_o   : out std_ulogic;
    rx_i   : in  std_ulogic;
    -- SEM status outputs for the LEDs of the board
    icap_request_o          : out std_ulogic;
    status_heartbeat_o      : out std_ulogic;
    status_initialization_o : out std_ulogic;
    -- 1 = the SEM is idle (bits 5:1 of the status all 0)
    sem_idle_o              : out std_ulogic
  );
end sem_arbitration_7series;

architecture Behavioral of sem_arbitration_7series is

    -- The SEM IP (sem 4.1). create_project.tcl generates it with the
    -- name sem_0.
    component sem_0 is
      port (
        status_heartbeat      : out std_logic;
        status_initialization : out std_logic;
        status_observation    : out std_logic;
        status_correction     : out std_logic;
        status_classification : out std_logic;
        status_injection      : out std_logic;
        status_essential      : out std_logic;
        status_uncorrectable  : out std_logic;

        monitor_txdata  : out std_logic_vector(7 downto 0);
        monitor_txwrite : out std_logic;
        monitor_txfull  : in  std_logic;
        monitor_rxdata  : in  std_logic_vector(7 downto 0);
        monitor_rxread  : out std_logic;
        monitor_rxempty : in  std_logic;

        icap_o       : in  std_logic_vector(31 downto 0);
        icap_csib    : out std_logic;
        icap_rdwrb   : out std_logic;
        icap_i       : out std_logic_vector(31 downto 0);
        icap_clk     : in  std_logic;
        icap_request : out std_logic;
        icap_grant   : in  std_logic;

        fecc_crcerr        : in std_logic;
        fecc_eccerr        : in std_logic;
        fecc_eccerrsingle  : in std_logic;
        fecc_syndromevalid : in std_logic;
        fecc_syndrome      : in std_logic_vector(12 downto 0);
        fecc_far           : in std_logic_vector(25 downto 0);
        fecc_synbit        : in std_logic_vector(4 downto 0);
        fecc_synword       : in std_logic_vector(6 downto 0)
      );
    end component sem_0;

    -- Clocks: safe_clk from the PLL, sem_clk after the clock enable
    signal safe_clk : std_ulogic;
    signal sem_clk  : std_ulogic;
    -- PLL locked: the reset of the monitor interface (UART and FIFOs)
    signal locked   : std_ulogic;

    -- SEM status interface
    signal sem_heartbeat      : std_logic;
    signal sem_initialization : std_logic;
    signal sem_observation    : std_logic;
    signal sem_correction     : std_logic;
    signal sem_classification : std_logic;
    signal sem_injection      : std_logic;
    signal sem_essential      : std_logic;
    signal sem_uncorrectable  : std_logic;

    -- SEM monitor interface. The SEM uses std_logic_vector, the monitor
    -- interface uses std_ulogic_vector. The *_u signals convert the type,
    -- so that the code also compiles as VHDL-93.
    signal mon_txdata   : std_logic_vector(7 downto 0);
    signal mon_txwrite  : std_logic;
    signal mon_txfull   : std_logic;
    signal mon_rxdata   : std_logic_vector(7 downto 0);
    signal mon_rxread   : std_logic;
    signal mon_rxempty  : std_logic;
    signal mon_txdata_u : std_ulogic_vector(7 downto 0);
    signal mon_rxdata_u : std_ulogic_vector(7 downto 0);

    -- SEM <-> ICAPE2
    signal icap_o_s       : std_logic_vector(31 downto 0);
    signal icap_csib_s    : std_logic;
    signal icap_rdwrb_s   : std_logic;
    signal icap_i_s       : std_logic_vector(31 downto 0);
    signal icap_request_s : std_logic;

    -- SEM <-> FRAME_ECCE2
    signal fecc_crcerr_s        : std_logic;
    signal fecc_eccerr_s        : std_logic;
    signal fecc_eccerrsingle_s  : std_logic;
    signal fecc_syndromevalid_s : std_logic;
    signal fecc_syndrome_s      : std_logic_vector(12 downto 0);
    signal fecc_far_s           : std_logic_vector(25 downto 0);
    signal fecc_synbit_s        : std_logic_vector(4 downto 0);
    signal fecc_synword_s       : std_logic_vector(6 downto 0);

    -- USER1: clock enable. The written value comes back on a read.
    signal clk_en_jtag : std_ulogic_vector(0 downto 0);
    -- USER2: icap_grant (write) and icap_request (read)
    signal grant_jtag   : std_ulogic_vector(0 downto 0);
    signal request_jtag : std_ulogic_vector(0 downto 0);
    -- USER3: SEM status signals (bit map in the header)
    signal sem_status : std_ulogic_vector(7 downto 0);

    -- Two flip-flops synchronize the JTAG values to safe_clk
    signal clk_en_d0, clk_en_sync : std_ulogic := '0';
    signal grant_d0, grant_sync   : std_ulogic := '0';
    attribute async_reg : string;
    attribute async_reg of clk_en_d0, clk_en_sync, grant_d0, grant_sync :
        signal is "TRUE";

begin

    -- Safe-startup PLL: the output clock has the same frequency as clk_i
    safe_clk_gen : clk_gen_wrapper
      Generic map (
        g_family          => "7SERIES",
        g_clkin_period_ns => 10.0,
        g_clkout_freq_mhz => 0.0
      )
      Port map (
        clk_i    => clk_i,
        clk_o    => safe_clk,
        locked_o => locked
      );

    -- BSCAN USER1: clock enable
    bscan_u1_clk_en : bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => 1,
        data_len_w => 1,
        sync       => false
      )
      Port map (
        clk_i            => '0',
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => clk_en_jtag,
        data_from_jtag_o => clk_en_jtag,
        ux_avail_o       => open,
        ux_ack_o         => open
      );

    sync_clk_en : process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            clk_en_d0   <= clk_en_jtag(0);
            clk_en_sync <= clk_en_d0;
        end if;
    end process sync_clk_en;

    sem_clk_gate : BUFGCE
      generic map (
        CE_TYPE => "SYNC"
      )
      port map (
        O  => sem_clk,
        CE => clk_en_sync,
        I  => safe_clk
      );

    -- BSCAN USER2: icap_grant (write) and icap_request (read)
    bscan_u2_icap_grant : bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => 1,
        data_len_w => 1,
        sync       => false
      )
      Port map (
        clk_i            => '0',
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => request_jtag,
        data_from_jtag_o => grant_jtag,
        ux_avail_o       => open,
        ux_ack_o         => open
      );

    request_jtag(0) <= icap_request_s;

    sync_grant : process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            grant_d0   <= grant_jtag(0);
            grant_sync <= grant_d0;
        end if;
    end process sync_grant;

    -- BSCAN USER3: SEM status signals. The SEM registers its status
    -- outputs, thus each bit is a stable level.
    sem_status <= sem_uncorrectable  & sem_essential      &
                  sem_injection      & sem_classification &
                  sem_correction     & sem_observation    &
                  sem_initialization & sem_heartbeat;

    bscan_u3_sem_status : bscan_interface
      Generic map (
        jtag_chain => 3,
        data_len_r => 8,
        data_len_w => 8,
        sync       => false
      )
      Port map (
        clk_i            => '0',
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => sem_status,
        data_from_jtag_o => open,
        ux_avail_o       => open,
        ux_ack_o         => open
      );

    -- Configuration logic
    icap : ICAPE2
      generic map (
        ICAP_WIDTH        => "X32",
        SIM_CFG_FILE_NAME => "NONE"
      )
      port map (
        O     => icap_o_s,
        CLK   => sem_clk,
        CSIB  => icap_csib_s,
        I     => icap_i_s,
        RDWRB => icap_rdwrb_s
      );

    frame_ecc : FRAME_ECCE2
      generic map (
        FARSRC                => "EFAR",
        FRAME_RBT_IN_FILENAME => "NONE"
      )
      port map (
        CRCERROR       => fecc_crcerr_s,
        ECCERROR       => fecc_eccerr_s,
        ECCERRORSINGLE => fecc_eccerrsingle_s,
        FAR            => fecc_far_s,
        SYNBIT         => fecc_synbit_s,
        SYNDROME       => fecc_syndrome_s,
        SYNDROMEVALID  => fecc_syndromevalid_s,
        SYNWORD        => fecc_synword_s
      );

    -- SEM controller. The XDC puts this instance (u_sem) in pblock_sem.
    u_sem : sem_0
      port map (
        status_heartbeat      => sem_heartbeat,
        status_initialization => sem_initialization,
        status_observation    => sem_observation,
        status_correction     => sem_correction,
        status_classification => sem_classification,
        status_injection      => sem_injection,
        status_essential      => sem_essential,
        status_uncorrectable  => sem_uncorrectable,

        monitor_txdata  => mon_txdata,
        monitor_txwrite => mon_txwrite,
        monitor_txfull  => mon_txfull,
        monitor_rxdata  => mon_rxdata,
        monitor_rxread  => mon_rxread,
        monitor_rxempty => mon_rxempty,

        icap_o       => icap_o_s,
        icap_csib    => icap_csib_s,
        icap_rdwrb   => icap_rdwrb_s,
        icap_i       => icap_i_s,
        icap_clk     => sem_clk,
        icap_request => icap_request_s,
        icap_grant   => grant_sync,

        fecc_crcerr        => fecc_crcerr_s,
        fecc_eccerr        => fecc_eccerr_s,
        fecc_eccerrsingle  => fecc_eccerrsingle_s,
        fecc_syndromevalid => fecc_syndromevalid_s,
        fecc_syndrome      => fecc_syndrome_s,
        fecc_far           => fecc_far_s,
        fecc_synbit        => fecc_synbit_s,
        fecc_synword       => fecc_synword_s
      );

    -- UART bridge between the SEM monitor port and the host. It uses
    -- sem_clk like the SEM: if the clock stops, the monitor port of the
    -- SEM and the FIFOs stop together.
    mon_txdata_u <= std_ulogic_vector(mon_txdata);
    mon_rxdata   <= std_logic_vector(mon_rxdata_u);

    uart_sem_interface : entity work.monitor_interface
      generic map (
        clk_freq => 100000000,
        baud     => 9600
      )
      port map (
        clk_i             => sem_clk,
        rstn_i            => locked,
        tx_o              => tx_o,
        rx_i              => rx_i,
        monitor_txdata_i  => mon_txdata_u,
        monitor_txwrite_i => mon_txwrite,
        monitor_txfull_o  => mon_txfull,
        monitor_rxdata_o  => mon_rxdata_u,
        monitor_rxread_i  => mon_rxread,
        monitor_rxempty_o => mon_rxempty
      );

    -- Status outputs to the LEDs
    icap_request_o          <= icap_request_s;
    status_heartbeat_o      <= sem_heartbeat;
    status_initialization_o <= sem_initialization;
    sem_idle_o <= '1' when sem_initialization = '0' and
                           sem_observation    = '0' and
                           sem_correction     = '0' and
                           sem_classification = '0' and
                           sem_injection      = '0' else '0';

end Behavioral;
