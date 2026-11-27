-- ========================================================================== --
-- NEORV32 - Test Setup Using The UART-Bootloader To Upload And Run           --
-- Executables                                                                --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --
-- Modified by SolidKosmos S.A. (2026): instantiates the safe-startup PLL     --
-- (clk_gen_wrapper) and the fault-injection test harness (tester), runs the  --
-- NEORV32 on the gated clock of the harness, sends the GPIO output to the    --
-- harness (CRC word) and the LEDs, and adds the HARDEN_EN and                --
-- clock-frequency generics. See THIRD_PARTY_NOTICES.md at the project root.  --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library UNISIM;
use UNISIM.VComponents.all;

library neorv32;
use neorv32.neorv32_package.all;

use work.examples_utilities_pkg.all;


entity neorv32_test_setup_bootloader is
  generic (
    -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS". The value goes directly
    -- to clk_gen_wrapper.
    g_family       : string  := "7SERIES";
    -- adapt these for your setup --
    -- frequency of the board clock clk_i in Hz
    CLK_IN_FREQUENCY : natural := 100000000;
    -- core clock in Hz, made from clk_i by clk_gen_wrapper
    INTERNAL_CLOCK_FREQUENCY  : natural := 40000000;
    -- size of processor-internal instruction memory in bytes
    IMEM_SIZE       : natural := 64*1024;
    -- size of processor-internal data memory in bytes
    DMEM_SIZE       : natural := 17*1024;
    -- Optional hardening: set false to build the unhardened baseline for
    -- fault-injection comparisons (e.g. override via Vivado's synth_1 generic,
    -- or a second run/project with this default flipped) --
    HARDEN_EN       : boolean := true

  );
  port (
    -- Global control --
    clk_i       : in  std_ulogic; -- global clock, rising edge
    -- rstn_i      : in  std_ulogic; -- global reset, low-active, async
    -- GPIO --
    gpio_o      : out std_ulogic_vector(15 downto 0); -- parallel output
    -- UART0 --
    uart0_txd_o : out std_ulogic; -- UART0 send data
    uart0_rxd_i : in  std_ulogic; -- UART0 receive data
    -- BSCAN clk tester debug --
    clk_en_led  : out std_ulogic;
    rst_led     : out std_ulogic

  );
end entity;

architecture neorv32_test_setup_bootloader_rtl
    of neorv32_test_setup_bootloader is

  signal neorv32_gpio_out : std_ulogic_vector(31 downto 0);
  signal bscan_crc_data   : std_ulogic_vector(31 downto 0);

  -- Test signals
  signal clk_to_neo, rst_to_neo : std_ulogic;
  signal check_tx               : std_ulogic;
  
  
  
  -- Safe PLL clk out port 
  signal safe_clk : std_ulogic;

begin
    
   -- IMPORTANT GUIDELINE -- 
   -- We instantitate a Phase Locked Loop --------------------------------------
   -- in safe startup mode to ensure clean clock propagation throughout --------
   -- the circuit during SHUTDOWN and START-UP sequences, preventing metastable
   -- --
   -- initialization sequences. ------------------------------------------------
   safe_pll:clk_gen_wrapper
      generic map (
        g_family          => g_family,
        g_clkin_period_ns => 1.0e9 / real(CLK_IN_FREQUENCY),
        g_clkout_freq_mhz => real(INTERNAL_CLOCK_FREQUENCY) / 1.0e6
      )
      port map (
        clk_i    => clk_i,
        clk_o    => safe_clk,
        locked_o => open
      );


  -- The Core Of The Problem ---------------------------------------------------
  -- ---------------------------------------------------------------------------
  neorv32_top_inst: neorv32_top
      generic map (
        -- Clocking --
        -- core clock frequency in Hz
        CLOCK_FREQUENCY  => INTERNAL_CLOCK_FREQUENCY,
        -- Boot Configuration --
        BOOT_MODE_SELECT => 2,                 -- boot from the IMEM image
        -- RISC-V CPU Extensions --
        -- implement compressed extension?
        RISCV_ISA_C      => true,
        RISCV_ISA_M      => true,              -- implement mul/div extension?
        RISCV_ISA_Zicntr => true,              -- implement base counters?
        -- Internal Instruction memory --
        -- implement processor-internal instruction memory
        IMEM_EN          => true,
        -- size of processor-internal instruction memory in bytes
        IMEM_SIZE        => IMEM_SIZE,
        -- Internal Data memory --
        -- implement processor-internal data memory
        DMEM_EN          => true,
        -- size of processor-internal data memory in bytes
        DMEM_SIZE        => DMEM_SIZE,
        -- Processor peripherals --
        -- number of GPIO input/output pairs (0..32)
        IO_GPIO_NUM      => 32,
        -- implement core local interruptor (CLINT)?
        IO_CLINT_EN      => true,
        -- implement primary universal asynchronous receiver/transmitter
        -- (UART0)?
        IO_UART0_EN      => true,
        -- RX FIFO depth, has to be a power of two, min 1
        IO_UART0_RX_FIFO => 1,
        -- TX FIFO depth, has to be a power of two, min 1
        IO_UART0_TX_FIFO => 2**10,
        -- Hardening --
        -- enable hardening (SECDED/parity/ECC)
        HARDEN_EN        => HARDEN_EN
    
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
         clk_i      => safe_clk,
         clk_out    => clk_to_neo,
         crc_data   => bscan_crc_data,
         rst_out    => rst_to_neo,
         clk_en_out => clk_en_led,
         -- send the signal to the controller to stop gracefully
         check_tx   => check_tx
      );
    
  rst_led <= rst_to_neo;

end architecture;