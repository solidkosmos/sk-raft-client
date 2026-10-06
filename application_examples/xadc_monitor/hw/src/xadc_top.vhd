--------------------------------------------------------------------------------
-- Company: SolidKosmos S.A.
-- SPDX-License-Identifier: Apache-2.0
-- Copyright (C) 2026 SOLIDKOSMOS S.A.
--
-- Module Name: xadc_top
-- Description: Die temperature and supply voltage monitor for 7-series and
--              Zynq-7000 devices.
--              The XADC operates in continuous sequence mode. The INIT
--              values come from the XADC instantiation example in UG480,
--              with no auxiliary channels and with the PS supplies on
--              Zynq-7000.
--              At each end of conversion (EOC), the design reads the result
--              from the XADC status register of that channel. UG480 gives
--              this method: EOC goes to DEN and CHANNEL goes to DADDR.
--              A pending flag blocks DEN until DRDY. Thus a delayed DRP
--              access (JTAG has the DRP) cannot start a second read.
--              JTAG reads the results through two BSCAN USER registers:
--                USER1 (write): request a snapshot of all results.
--                USER2 (read):  the snapshot (160 bits, see below).
--              The snapshot does not change between two requests. Thus a
--              JTAG read of USER2 always gets one consistent set of values.
--
-- USER2 snapshot (bit 0 shifts out first):
--   15:0    temperature      (XADC status register 00h)
--   31:16   VCCINT           (01h)
--   47:32   VCCAUX           (02h)
--   63:48   VCCBRAM          (06h)
--   79:64   VCCPINT          (0Dh, Zynq-7000 only, else 0)
--   95:80   VCCPAUX          (0Eh, Zynq-7000 only, else 0)
--   111:96  VCCO_DDR         (0Fh, Zynq-7000 only, else 0)
--   127:112 end-of-sequence count (16 bits, wraps)
--   135:128 ALM(7:0)
--   143:136 snapshot count   (8 bits, wraps, +1 for each request)
--   151:144 design ID        (X"5A")
--   159:152 flags            (bit 152: OT, bit 153: g_zynq)
-- The 12-bit ADC code is in bits 15:4 of each 16-bit result (UG480).
--------------------------------------------------------------------------------


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

library UNISIM;
use UNISIM.VComponents.all;

entity xadc_top is
  Generic (
    -- 1: Zynq-7000. The XADC also measures VCCPINT, VCCPAUX and VCCO_DDR.
    -- 0: Other 7-series device. build.tcl sets this value from the part.
    g_zynq : integer range 0 to 1 := 0
  );
  Port (
    -- Board clock. It is also the XADC DRP clock (DCLK).
    -- The INIT_42 value below is correct for 100 MHz.
    clk_i  : in  std_ulogic;
    -- data_o(0): OT, over-temperature alarm
    -- data_o(1): ALM(7), logic OR of the temperature and supply alarms
    -- data_o(2): heartbeat (the PL is configured and the clock operates)
    -- data_o(3): not used
    data_o : out std_ulogic_vector(3 downto 0)
  );
end xadc_top;

architecture Behavioral of xadc_top is

    -- Select one of two XADC INIT values from g_zynq. There are two
    -- versions of the function: the UNISIM library can declare the INIT
    -- generics as bit_vector or as std_logic_vector.
    function sel(zynq : integer; zynq_value, other_value : bit_vector)
        return bit_vector is
    begin
        if zynq = 1 then
            return zynq_value;
        else
            return other_value;
        end if;
    end function sel;

    function sel(zynq : integer;
                 zynq_value, other_value : std_logic_vector)
        return std_logic_vector is
    begin
        if zynq = 1 then
            return zynq_value;
        else
            return other_value;
        end if;
    end function sel;

    constant SNAPSHOT_LEN : integer := 160;
    constant DESIGN_ID    : std_ulogic_vector(7 downto 0) := X"5A";

    -- XADC channel numbers (CHANNEL output, UG480). For channels 0 to 15,
    -- the status register address is equal to the channel number.
    constant CH_TEMP     : std_logic_vector(4 downto 0) := "00000";
    constant CH_VCCINT   : std_logic_vector(4 downto 0) := "00001";
    constant CH_VCCAUX   : std_logic_vector(4 downto 0) := "00010";
    constant CH_VCCBRAM  : std_logic_vector(4 downto 0) := "00110";
    constant CH_VCCPINT  : std_logic_vector(4 downto 0) := "01101";
    constant CH_VCCPAUX  : std_logic_vector(4 downto 0) := "01110";
    constant CH_VCCO_DDR : std_logic_vector(4 downto 0) := "01111";

    -- XADC ports
    signal xadc_daddr   : std_logic_vector(6 downto 0);
    signal xadc_do      : std_logic_vector(15 downto 0);
    signal xadc_drdy    : std_logic;
    signal xadc_channel : std_logic_vector(4 downto 0);
    signal xadc_eoc     : std_logic;
    signal xadc_eos     : std_logic;
    signal xadc_alm     : std_logic_vector(7 downto 0);
    signal xadc_ot      : std_logic;

    -- DRP read control: DEN, read in progress, channel of that read
    signal xadc_den   : std_logic;
    signal rd_pending : std_logic := '0';
    signal rd_channel : std_logic_vector(4 downto 0) := (others => '0');

    -- Latest result of each channel (16-bit status register values)
    signal temp_r     : std_ulogic_vector(15 downto 0) := (others => '0');
    signal vccint_r   : std_ulogic_vector(15 downto 0) := (others => '0');
    signal vccaux_r   : std_ulogic_vector(15 downto 0) := (others => '0');
    signal vccbram_r  : std_ulogic_vector(15 downto 0) := (others => '0');
    signal vccpint_r  : std_ulogic_vector(15 downto 0) := (others => '0');
    signal vccpaux_r  : std_ulogic_vector(15 downto 0) := (others => '0');
    signal vccoddr_r  : std_ulogic_vector(15 downto 0) := (others => '0');

    signal eos_count  : unsigned(15 downto 0) := (others => '0');
    signal snap_count : unsigned(7 downto 0)  := (others => '0');

    -- Two flip-flops synchronize ALM and OT to clk_i
    signal alm_d0, alm_sync : std_ulogic_vector(7 downto 0) := (others => '0');
    signal ot_d0, ot_sync   : std_ulogic := '0';
    attribute ASYNC_REG : string;
    attribute ASYNC_REG of alm_d0, alm_sync, ot_d0, ot_sync : signal is "TRUE";

    signal heartbeat : unsigned(26 downto 0) := (others => '0');

    -- BSCAN USER1: snapshot request (write only)
    signal req_avail     : std_ulogic;
    signal req_avail_d   : std_ulogic := '0';

    -- BSCAN USER2: snapshot (read only)
    signal snapshot : std_ulogic_vector(SNAPSHOT_LEN - 1 downto 0) :=
        (others => '0');

    signal zynq_flag : std_ulogic;

begin

    zynq_flag <= '1' when g_zynq = 1 else '0';

    ----------------------------------------------------------------------------
    -- XADC. INIT values from the UG480 instantiation example, with two
    -- changes: INIT_49 selects no auxiliary channels (UG480: X"000F"), and
    -- for Zynq-7000, INIT_48 and INIT_4A also select the PS supplies
    -- (bits 5 to 7: VCCPINT, VCCPAUX, VCCO_DDR).
    ----------------------------------------------------------------------------
    xadc_inst : XADC
      Generic map (
        INIT_40 => X"9000", -- Calibration averaging off, averaging of 16
        INIT_41 => X"2EF0", -- Continuous sequence, PS alarms off, cal. on
        INIT_42 => X"0400", -- DCLK / 4: ADCCLK 25 MHz at DCLK 100 MHz
        -- Sequence: calibration, temperature, VCCINT, VCCAUX, VCCBRAM
        -- (and VCCPINT, VCCPAUX, VCCO_DDR on Zynq-7000)
        INIT_48 => sel(g_zynq, X"47E1", X"4701"),
        INIT_49 => X"0000", -- No auxiliary channels
        -- Averaging on the same channels (not on calibration)
        INIT_4A => sel(g_zynq, X"47E0", X"4700"),
        INIT_4B => X"0000",
        INIT_4C => X"0000", -- Unipolar
        INIT_4D => X"0000",
        INIT_4E => X"0000", -- Default settling time
        INIT_4F => X"0000",
        INIT_50 => X"B5ED", -- Temperature upper alarm 85 C
        INIT_51 => X"5999", -- VCCINT upper alarm 1.05 V
        INIT_52 => X"A147", -- VCCAUX upper alarm 1.89 V
        INIT_53 => X"0000", -- OT upper limit 125 C (default)
        INIT_54 => X"A93A", -- Temperature alarm reset 60 C
        INIT_55 => X"5111", -- VCCINT lower alarm 0.95 V
        INIT_56 => X"91EB", -- VCCAUX lower alarm 1.71 V
        INIT_57 => X"AE4E", -- OT reset 70 C
        INIT_58 => X"5999", -- VCCBRAM upper alarm 1.05 V
        INIT_5C => X"5111"  -- VCCBRAM lower alarm 0.95 V
      )
      Port map (
        CONVST       => '0',
        CONVSTCLK    => '0',
        RESET        => '0',
        VP           => '0',
        VN           => '0',
        VAUXP        => (others => '0'),
        VAUXN        => (others => '0'),
        DCLK         => clk_i,
        DEN          => xadc_den,  -- Read the status register at each EOC
        DADDR        => xadc_daddr,
        DWE          => '0',
        DI           => (others => '0'),
        DO           => xadc_do,
        DRDY         => xadc_drdy,
        CHANNEL      => xadc_channel,
        EOC          => xadc_eoc,
        EOS          => xadc_eos,
        BUSY         => open,
        ALM          => xadc_alm,
        OT           => xadc_ot,
        JTAGBUSY     => open,
        JTAGLOCKED   => open,
        JTAGMODIFIED => open,
        MUXADDR      => open
      );

    -- The status register address of channels 0 to 15 is the channel number
    xadc_daddr <= "00" & xadc_channel;
    xadc_den   <= xadc_eoc and not rd_pending;

    ----------------------------------------------------------------------------
    -- Keep the result of each DRP read
    ----------------------------------------------------------------------------
    read_proc : process(clk_i)
    begin
        if rising_edge(clk_i) then
            -- DADDR is valid with DEN. Keep the channel until DRDY.
            if xadc_den = '1' then
                rd_channel <= xadc_channel;
                rd_pending <= '1';
            end if;

            if xadc_drdy = '1' then
                rd_pending <= '0';
                case rd_channel is
                    when CH_TEMP     => temp_r    <= std_ulogic_vector(xadc_do);
                    when CH_VCCINT   => vccint_r  <= std_ulogic_vector(xadc_do);
                    when CH_VCCAUX   => vccaux_r  <= std_ulogic_vector(xadc_do);
                    when CH_VCCBRAM  => vccbram_r <= std_ulogic_vector(xadc_do);
                    when CH_VCCPINT  => vccpint_r <= std_ulogic_vector(xadc_do);
                    when CH_VCCPAUX  => vccpaux_r <= std_ulogic_vector(xadc_do);
                    when CH_VCCO_DDR => vccoddr_r <= std_ulogic_vector(xadc_do);
                    when others      => null; -- calibration
                end case;
            end if;

            if xadc_eos = '1' then
                eos_count <= eos_count + 1;
            end if;

            alm_d0   <= std_ulogic_vector(xadc_alm);
            alm_sync <= alm_d0;
            ot_d0    <= xadc_ot;
            ot_sync  <= ot_d0;

            heartbeat <= heartbeat + 1;
        end if;
    end process read_proc;

    ----------------------------------------------------------------------------
    -- BSCAN USER1: snapshot request. A JTAG write sets avail. The
    -- bscan_interface synchronizes avail to clk_i (sync => true).
    ----------------------------------------------------------------------------
    bscan_u1_request : entity work.bscan_interface
      Generic map (
        jtag_chain => 1,
        data_len_r => 1,
        data_len_w => 1,
        sync       => true
      )
      Port map (
        clk_i            => clk_i,
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => (others => '0'),
        data_from_jtag_o => open,
        ux_avail_o       => req_avail,
        ux_ack_o         => open
      );

    -- At the rising edge of avail, copy all results into the snapshot
    snapshot_proc : process(clk_i)
    begin
        if rising_edge(clk_i) then
            req_avail_d <= req_avail;
            if req_avail = '1' and req_avail_d = '0' then
                snapshot <= "000000" & zynq_flag & ot_sync     -- 159:152
                          & DESIGN_ID                          -- 151:144
                          & std_ulogic_vector(snap_count + 1)  -- 143:136
                          & alm_sync                           -- 135:128
                          & std_ulogic_vector(eos_count)       -- 127:112
                          & vccoddr_r                          -- 111:96
                          & vccpaux_r                          -- 95:80
                          & vccpint_r                          -- 79:64
                          & vccbram_r                          -- 63:48
                          & vccaux_r                           -- 47:32
                          & vccint_r                           -- 31:16
                          & temp_r;                            -- 15:0
                snap_count <= snap_count + 1;
            end if;
        end if;
    end process snapshot_proc;

    ----------------------------------------------------------------------------
    -- BSCAN USER2: snapshot read. The snapshot does not change during a
    -- JTAG read, so a clock domain crossing circuit is not necessary.
    ----------------------------------------------------------------------------
    bscan_u2_snapshot : entity work.bscan_interface
      Generic map (
        jtag_chain => 2,
        data_len_r => SNAPSHOT_LEN,
        data_len_w => 1,
        sync       => false
      )
      Port map (
        clk_i            => '0',
        tck_o            => open,
        drck_o           => open,
        data_to_jtag_i   => snapshot,
        data_from_jtag_o => open,
        ux_avail_o       => open,
        ux_ack_o         => open
      );

    data_o <= '0' & heartbeat(heartbeat'high) & alm_sync(7) & ot_sync;

end Behavioral;
