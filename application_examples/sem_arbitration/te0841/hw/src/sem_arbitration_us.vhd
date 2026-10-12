--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: sem_arbitration_us
-- Description: Top of the UltraScale SEM arbitration example. The SEM
--              controller (sem_ultra_0, PG187) and SK-RAFT share the
--              configuration logic. SK-RAFT controls the ICAP arbitration
--              interface of the SEM (cap_gnt, cap_rel) through BSCAN
--              USER2. Target: Trenz TE0841-02 (Kintex UltraScale
--              XCKU040).
--
--   The SEM connects directly to ICAPE3 and FRAME_ECCE3. There is no
--   arbiter logic in the design: SK-RAFT does the handshake of the ICAP
--   arbitration interface itself (PG187):
--     cap_req (from the SEM) : 1 = the SEM needs the ICAP. After a boot or
--                              a reset the SEM sets cap_req and waits for
--                              cap_gnt before it initializes.
--     cap_gnt (to the SEM)   : 1 = the SEM can use the ICAP.
--     cap_rel (to the SEM)   : 1 = another user needs the ICAP. The SEM
--                              goes to idle at the next safe point and
--                              clears cap_req.
--   cap_gnt and cap_rel are 0 after configuration: the SEM waits at boot.
--
--   Clock tree: clk_i_p/clk_i_n (200 MHz) -> IBUFDS -> safe-startup PLL
--   (clk_gen_wrapper, 100 MHz) -> safe_clk -> BUFGCE (enable from USER1)
--   -> sem_clk. The SEM, the ICAPE3, the FRAME_ECCE3 and the monitor
--   interface use sem_clk. Only the BSCAN synchronizers use the ungated
--   safe_clk, so that the clock can be enabled again.
--
--   BSCAN registers:
--     USER1  write: bit 0  clock enable (1 = sem_clk operates, 0 = stopped).
--                          0 after configuration.
--            read : bit 0  the value written last
--     USER2  write: bit 0  cap_gnt of the SEM
--                   bit 1  cap_rel of the SEM
--            read : bit 0  cap_req of the SEM
--                   bit 1  cap_gnt, as applied to the SEM
--     USER3  read : the 10 SEM status signals (PG187 status interface)
--            bit 0  status_heartbeat       pulses while the SEM scans
--                                          (observation)
--            bit 1  status_initialization  the SEM initializes
--            bit 2  status_observation     the SEM scans for errors
--            bit 3  status_correction      the SEM corrects an error
--            bit 4  status_classification  the SEM classifies an error
--            bit 5  status_injection       the SEM injects an error
--            bit 6  status_diagnostic_scan the SEM is in a diagnostic scan
--            bit 7  status_detect_only     the SEM is in detect-only mode
--            bit 8  status_essential       the last error was essential
--            bit 9  status_uncorrectable   the last error was
--                                          uncorrectable
--
--   The SEM monitor port goes to the UART of the board (monitor_interface,
--   9600 8-N-1): the SEM sends its reports on tx_o and reads its commands
--   from rx_i.
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

library UNISIM;
use UNISIM.VComponents.all;

use work.examples_utilities_pkg.all;

entity sem_arbitration_us is
  Generic (
    -- Period of the board clock in ns (200 MHz oscillator U11 of the
    -- TE0841). clk_gen_wrapper makes the 100 MHz SEM clock from it.
    CLK_IN_PERIOD_NS : real := 5.0
  );
  Port (
    -- Board clock, differential
    clk_i_p : in  std_ulogic;
    clk_i_n : in  std_ulogic;
    -- UART to and from the host (SEM monitor, 9600 8-N-1)
    tx_o    : out std_ulogic;
    rx_i    : in  std_ulogic;
    -- Enable of the 200 MHz oscillator of the TE0841 (EN_OSC)
    en_osc  : out std_ulogic
  );
end sem_arbitration_us;

architecture Behavioral of sem_arbitration_us is

    -- The SEM IP (sem_ultra 3.1). create_project.tcl generates it with the
    -- name sem_ultra_0. The widths of command_code and fecc_far are for
    -- the XCKU040.
    component sem_ultra_0 is
      port (
        status_heartbeat       : out std_logic;
        status_initialization  : out std_logic;
        status_observation     : out std_logic;
        status_correction      : out std_logic;
        status_classification  : out std_logic;
        status_injection       : out std_logic;
        status_diagnostic_scan : out std_logic;
        status_detect_only     : out std_logic;
        status_essential       : out std_logic;
        status_uncorrectable   : out std_logic;

        monitor_txdata  : out std_logic_vector(7 downto 0);
        monitor_txwrite : out std_logic;
        monitor_txfull  : in  std_logic;
        monitor_rxdata  : in  std_logic_vector(7 downto 0);
        monitor_rxread  : out std_logic;
        monitor_rxempty : in  std_logic;

        command_strobe : in  std_logic;
        command_busy   : out std_logic;
        command_code   : in  std_logic_vector(39 downto 0);

        icap_clk     : in  std_logic;
        icap_o       : in  std_logic_vector(31 downto 0);
        icap_csib    : out std_logic;
        icap_rdwrb   : out std_logic;
        icap_i       : out std_logic_vector(31 downto 0);
        icap_prerror : in  std_logic;
        icap_prdone  : in  std_logic;
        icap_avail   : in  std_logic;

        cap_rel : in  std_logic;
        cap_gnt : in  std_logic;
        cap_req : out std_logic;

        fecc_eccerrorsingle    : in  std_logic;
        fecc_eccerrornotsingle : in  std_logic;
        fecc_endofframe        : in  std_logic;
        fecc_endofscan         : in  std_logic;
        fecc_crcerror          : in  std_logic;
        fecc_far               : in  std_logic_vector(25 downto 0);
        fecc_farsel            : out std_logic_vector(1 downto 0);

        aux_error_cr_ne : in  std_logic;
        aux_error_cr_es : in  std_logic;
        aux_error_uc    : in  std_logic
      );
    end component sem_ultra_0;

    -- Clocks and reset
    -- Board clock after the IBUFDS
    signal buf_clk  : std_ulogic;
    -- 100 MHz clock from clk_gen_wrapper, and the gated SEM clock
    signal safe_clk : std_ulogic;
    signal sem_clk  : std_ulogic;
    -- Reset of the monitor interface: 0 until the PLL is locked
    signal locked   : std_ulogic;

    -- SEM status interface
    signal sem_heartbeat       : std_logic;
    signal sem_initialization  : std_logic;
    signal sem_observation     : std_logic;
    signal sem_correction      : std_logic;
    signal sem_classification  : std_logic;
    signal sem_injection       : std_logic;
    signal sem_diagnostic_scan : std_logic;
    signal sem_detect_only     : std_logic;
    signal sem_essential       : std_logic;
    signal sem_uncorrectable   : std_logic;

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

    -- SEM <-> ICAPE3
    signal icap_o       : std_logic_vector(31 downto 0);
    signal icap_csib    : std_logic;
    signal icap_rdwrb   : std_logic;
    signal icap_i       : std_logic_vector(31 downto 0);
    signal icap_prerror : std_logic;
    signal icap_prdone  : std_logic;
    signal icap_avail   : std_logic;

    -- SEM ICAP arbitration interface
    signal cap_req : std_logic;

    -- SEM <-> FRAME_ECCE3
    signal fecc_eccerrorsingle    : std_logic;
    signal fecc_eccerrornotsingle : std_logic;
    signal fecc_endofframe        : std_logic;
    signal fecc_endofscan         : std_logic;
    signal fecc_crcerror          : std_logic;
    signal fecc_far               : std_logic_vector(25 downto 0);
    signal fecc_farsel            : std_logic_vector(1 downto 0);

    -- USER1: clock enable. The written value comes back on a read.
    signal clk_en_jtag : std_ulogic_vector(0 downto 0);
    -- USER2: cap_rel & cap_gnt (write), cap_gnt & cap_req (read)
    signal cap_jtag    : std_ulogic_vector(1 downto 0);
    signal cap_status  : std_ulogic_vector(1 downto 0);
    -- USER3: SEM status signals (bit map in the header)
    signal sem_status  : std_ulogic_vector(9 downto 0);

    -- Two flip-flops synchronize the JTAG values to safe_clk
    signal clk_en_d0, clk_en_sync : std_ulogic := '0';
    signal cap_d0, cap_sync       : std_ulogic_vector(1 downto 0) :=
        (others => '0');
    attribute async_reg : string;
    attribute async_reg of clk_en_d0, clk_en_sync, cap_d0, cap_sync :
        signal is "TRUE";

begin

    ---------------------------------------------------------------------------
    -- Clock
    ---------------------------------------------------------------------------
    -- The 200 MHz oscillator of the TE0841 operates only when EN_OSC is 1
    en_osc <= '1';

    -- Differential board clock. No internal termination (see the XDC).
    clk_ibuf : IBUFDS
      generic map (
        DIFF_TERM    => FALSE,
        IBUF_LOW_PWR => TRUE,
        IOSTANDARD   => "LVDS"
      )
      port map (
        O  => buf_clk,
        I  => clk_i_p,
        IB => clk_i_n
      );

    -- Safe-startup PLL: 100 MHz for the SEM (CLOCK_PERIOD of the IP) and
    -- for the baud rate of the monitor interface
    safe_clk_gen : clk_gen_wrapper
      Generic map (
        g_family          => "ULTRASCALE",
        g_clkin_period_ns => CLK_IN_PERIOD_NS,
        g_clkout_freq_mhz => 100.0
      )
      Port map (
        clk_i    => buf_clk,
        clk_o    => safe_clk,
        locked_o => locked
      );

    ---------------------------------------------------------------------------
    -- BSCAN USER1: clock enable
    ---------------------------------------------------------------------------
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
      port map (
        O  => sem_clk,
        CE => clk_en_sync,
        I  => safe_clk
      );

    ---------------------------------------------------------------------------
    -- BSCAN USER2: ICAP arbitration interface of the SEM
    ---------------------------------------------------------------------------
    bscan_u2_cap : bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => 2,
        data_len_w => 2,
        sync       => false
      )
      Port map (
        clk_i            => '0',
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => cap_status,
        data_from_jtag_o => cap_jtag,
        ux_avail_o       => open,
        ux_ack_o         => open
      );

    sync_cap : process(safe_clk)
    begin
        if rising_edge(safe_clk) then
            cap_d0   <= cap_jtag;
            cap_sync <= cap_d0;
        end if;
    end process sync_cap;

    cap_status <= cap_sync(0) & cap_req;

    ---------------------------------------------------------------------------
    -- BSCAN USER3: SEM status signals. The SEM registers its status
    -- outputs, thus each bit is a stable level.
    ---------------------------------------------------------------------------
    sem_status <= sem_uncorrectable   & sem_essential       &
                  sem_detect_only     & sem_diagnostic_scan &
                  sem_injection       & sem_classification  &
                  sem_correction      & sem_observation     &
                  sem_initialization  & sem_heartbeat;

    bscan_u3_sem_status : bscan_interface
      Generic map (
        jtag_chain => 3,
        data_len_r => 10,
        data_len_w => 10,
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

    ---------------------------------------------------------------------------
    -- SEM controller. The XDC puts this instance (u_sem) in pblock_sem.
    ---------------------------------------------------------------------------
    u_sem : sem_ultra_0
      port map (
        status_heartbeat       => sem_heartbeat,
        status_initialization  => sem_initialization,
        status_observation     => sem_observation,
        status_correction      => sem_correction,
        status_classification  => sem_classification,
        status_injection       => sem_injection,
        status_diagnostic_scan => sem_diagnostic_scan,
        status_detect_only     => sem_detect_only,
        status_essential       => sem_essential,
        status_uncorrectable   => sem_uncorrectable,

        monitor_txdata  => mon_txdata,
        monitor_txwrite => mon_txwrite,
        monitor_txfull  => mon_txfull,
        monitor_rxdata  => mon_rxdata,
        monitor_rxread  => mon_rxread,
        monitor_rxempty => mon_rxempty,

        -- The commands come through the monitor interface
        command_strobe => '0',
        command_busy   => open,
        command_code   => (others => '0'),

        icap_clk     => sem_clk,
        icap_o       => icap_o,
        icap_csib    => icap_csib,
        icap_rdwrb   => icap_rdwrb,
        icap_i       => icap_i,
        icap_prerror => icap_prerror,
        icap_prdone  => icap_prdone,
        icap_avail   => icap_avail,

        -- From BSCAN USER2
        cap_rel => cap_sync(1),
        cap_gnt => cap_sync(0),
        cap_req => cap_req,

        fecc_eccerrorsingle    => fecc_eccerrorsingle,
        fecc_eccerrornotsingle => fecc_eccerrornotsingle,
        fecc_endofframe        => fecc_endofframe,
        fecc_endofscan         => fecc_endofscan,
        fecc_crcerror          => fecc_crcerror,
        fecc_far               => fecc_far,
        fecc_farsel            => fecc_farsel,

        -- No external error sources
        aux_error_cr_ne => '0',
        aux_error_cr_es => '0',
        aux_error_uc    => '0'
      );

    ---------------------------------------------------------------------------
    -- Configuration logic
    ---------------------------------------------------------------------------
    icap : ICAPE3
      generic map (
        ICAP_AUTO_SWITCH  => "DISABLE",
        SIM_CFG_FILE_NAME => "NONE"
      )
      port map (
        AVAIL   => icap_avail,
        O       => icap_o,
        PRDONE  => icap_prdone,
        PRERROR => icap_prerror,
        CLK     => sem_clk,
        CSIB    => icap_csib,
        I       => icap_i,
        RDWRB   => icap_rdwrb
      );

    -- FRAME_ECCE3 is the frame ECC primitive of UltraScale (FRAME_ECCE4 is
    -- for UltraScale+)
    frame_ecc : FRAME_ECCE3
      port map (
        CRCERROR          => fecc_crcerror,
        ECCERRORNOTSINGLE => fecc_eccerrornotsingle,
        ECCERRORSINGLE    => fecc_eccerrorsingle,
        ENDOFFRAME        => fecc_endofframe,
        ENDOFSCAN         => fecc_endofscan,
        FAR               => fecc_far,
        FARSEL            => fecc_farsel,
        ICAPBOTCLK        => sem_clk,
        ICAPTOPCLK        => sem_clk
      );

    ---------------------------------------------------------------------------
    -- Monitor interface. It uses sem_clk like the SEM: if the clock stops,
    -- the monitor port of the SEM and the FIFOs stop together.
    ---------------------------------------------------------------------------
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

end Behavioral;
