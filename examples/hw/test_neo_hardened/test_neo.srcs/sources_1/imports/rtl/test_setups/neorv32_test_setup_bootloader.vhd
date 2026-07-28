-- ================================================================================ --
-- NEORV32 - Test Setup Using The UART-Bootloader To Upload And Run Executables     --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library UNISIM;
use UNISIM.VComponents.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_test_setup_bootloader is
  generic (
    -- adapt these for your setup --
    CLOCK_FREQUENCY : natural := 100000000; -- clock frequency of clk_i in Hz
    IMEM_SIZE       : natural := 64*1024;   -- size of processor-internal instruction memory in bytes
    DMEM_SIZE       : natural := 17*1024;   -- size of processor-internal data memory in bytes
    -- Optional hardening: set false to build the unhardened baseline for
    -- fault-injection comparisons (e.g. override via Vivado's synth_1 generic,
    -- or a second run/project with this default flipped) --
    HARDEN_EN       : boolean := true

  );
  port (
    -- Global control --
    clk_i       : in  std_ulogic; -- global clock, rising edge
    rstn_i      : in  std_ulogic; -- global reset, low-active, async
    -- GPIO --
    gpio_o      : out std_ulogic_vector(15 downto 0); -- parallel output
    -- UART0 --
    uart0_txd_o : out std_ulogic; -- UART0 send data
    uart0_rxd_i : in  std_ulogic; -- UART0 receive data
    -- BSCAN clk tester debug --
    clk_en_led  : out std_logic;
    rst_led     : out std_logic

  );
end entity;

architecture neorv32_test_setup_bootloader_rtl of neorv32_test_setup_bootloader is

  signal neorv32_gpio_out : std_ulogic_vector(31 downto 0);
  signal bscan_crc_data   : std_ulogic_vector(31 downto 0);

  -- Test signals
  signal clk_to_neo, rst_to_neo : std_logic;
  signal check_tx               : std_ulogic;
  
  -- MMCM 
  component mmcm_wrapper is
    port (
      -- Clock out ports
      clk_out1 : out std_ulogic;
     -- Clock in ports
      clk_in1  : in std_ulogic
    );
  end component mmcm_wrapper;
  
  -- MMCM clk out port 
  signal clk_to_logic : std_ulogic;

begin
    
   -- IMPORTANT GUIDELINE -- 
   -- We instantitate a Mixed Mode Clock Manager/Phase Locked Loop ---------------
   -- in safe startup mode to ensure clean clock propagation throughout ----------
   -- the circuit during SHUTDOWN and START-UP sequences, preventing metastable --
   -- initialization sequences. ------------------------------------------------ 
   mmcm_safe_startup: mmcm_wrapper
    port map(
      -- Clock out ports
      clk_out1 => clk_to_logic,
     -- Clock in ports
      clk_in1  => clk_i
    );

  

  -- The Core Of The Problem ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_top_inst: neorv32_top
  generic map (
    -- Clocking --
    CLOCK_FREQUENCY  => CLOCK_FREQUENCY,   -- clock frequency of clk_i in Hz
    -- Boot Configuration --
    BOOT_MODE_SELECT => 2,                 -- boot via internal bootloader
    -- RISC-V CPU Extensions --
    RISCV_ISA_C      => true,              -- implement compressed extension?
    RISCV_ISA_M      => true,              -- implement mul/div extension?
    RISCV_ISA_Zicntr => true,              -- implement base counters?
    -- Internal Instruction memory --
    IMEM_EN          => true,              -- implement processor-internal instruction memory
    IMEM_SIZE        => IMEM_SIZE,         -- size of processor-internal instruction memory in bytes
    -- Internal Data memory --
    DMEM_EN          => true,              -- implement processor-internal data memory
    DMEM_SIZE        => DMEM_SIZE,         -- size of processor-internal data memory in bytes
    -- Processor peripherals --
    IO_GPIO_NUM      => 32,                -- number of GPIO input/output pairs (0..32)
    IO_CLINT_EN      => true,              -- implement core local interruptor (CLINT)?
    IO_UART0_EN      => true,              -- implement primary universal asynchronous receiver/transmitter (UART0)?
    IO_UART0_RX_FIFO => 1,                 -- RX FIFO depth, has to be a power of two, min 1
    IO_UART0_TX_FIFO => 2**10,             -- TX FIFO depth, has to be a power of two, min 1
    -- Hardening --
    HARDEN_EN        => HARDEN_EN          -- enable hardening (SECDED/parity/ECC)

  )
  port map (
    -- Global control --
    clk_i       => clk_to_neo,        -- global clock, rising edge
    rstn_i      => rst_to_neo,        -- global reset, low-active, async
    -- GPIO (available if IO_GPIO_NUM > 0) --
    gpio_o      => neorv32_gpio_out,  -- parallel output
    -- primary UART0 (available if IO_UART0_EN = true) --
    uart0_txd_o => uart0_txd_o,       -- UART0 send data
    uart0_rxd_i => uart0_rxd_i,       -- UART0 receive data
    -- CPU interrupts (for chip-internal usage only) --
    --mext_irq_i  =>  gpio_irq,       -- machine external interrupt

    -- Test signals --
    check_tx    => check_tx
   );

  -- GPIO output --
  -- 31 downto 28 / 27 downto 24 / 23 downto 20 / 19 downto 16
  gpio_o <= neorv32_gpio_out(31 downto 16);

  -- Compose the BSCAN read-back word from the full 32-bit GPIO output word.
  bscan_crc_data <= neorv32_gpio_out;

  clk_reset_ctrl: entity work.tester(Behavioral)
  port map(
     clk        => clk_to_logic,
     clk_out    => clk_to_neo,
     crc_data   => std_logic_vector(bscan_crc_data),
     rst_out    => rst_to_neo,
     clk_en_out => clk_en_led,
     check_tx   => check_tx   -- send the signal to the controller to stop gracefully
  );

  rst_led <= rst_to_neo;

end architecture;