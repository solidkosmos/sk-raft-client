// ========================================================================== //
// The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        //
// Copyright (c) NEORV32 contributors.                                        //
// Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            //
// Licensed under the BSD-3-Clause license, see LICENSE for details.          //
// SPDX-License-Identifier: BSD-3-Clause                                      //
// ========================================================================== //
// Modified by SolidKosmos S.A. (2026):  Runs CoreMark and installs           //
// custom fast-interrupt handlers for the DMEM/register-file ECC correction   //
// and CPU-control/frontend FSM-state and PC/RA parity interrupts added by    //
// this project's hardened NEORV32 build. See THIRD_PARTY_NOTICES.md at the   //
// project root.                                                              //
// ========================================================================== //

/**********************************************************************//**
 * @file main.c
 * @brief NEORV32 hardening demo: runs CoreMark while custom fast-interrupt
 * handlers report any SECDED/parity correction triggered by the hardened
 * DMEM, register file, and CPU control/frontend logic.
 **************************************************************************/

#include <neorv32.h>
#include "coremark_runner.h"
#include "core_portme.h"

/**********************************************************************//**
 * @name Hardening fast-interrupt handlers
 *
 * Each handler prints which fault
 * fired and the PC execution resumed at, and returns -- NEORV32 fast
 * interrupts are non-nested and self-clearing, so no explicit acknowledge
 * is needed here.
 *
 * FIRQ channel map for this hardened build:
 *   FIRQ0  - DMEM ECC correction          (neorv32_dmem.vhd)
 *   FIRQ1  - register file ECC correction (neorv32_prim.vhd /
 *                                          neorv32_cpu_regfile.vhd)
 *   FIRQ2  - fetch-engine PC/RA parity    (neorv32_cpu_frontend.vhd)
 *   FIRQ3  - fetch-engine illegal state   (neorv32_cpu_frontend.vhd)
 *   FIRQ14 - execute-engine FSM correction (neorv32_cpu_control.vhd)
 *   FIRQ15 - execute-engine PC/RA parity   (neorv32_cpu_control.vhd)
 **************************************************************************/
/**@{*/
void regf_irq(void) {
  neorv32_uart0_printf("[ALERT] Register file correction. "
                       "Resuming execution at PC: %u\n",
                       neorv32_cpu_csr_read(CSR_MEPC));
}

void dmem_irq(void) {
  neorv32_uart0_printf("[ALERT] Data memory correction. "
                       "Resuming execution at PC: %u\n",
                       neorv32_cpu_csr_read(CSR_MEPC));
}

void exe_eng_irq(void) {
  neorv32_uart0_printf("[ALERT] Execute-engine state correction. "
                       "Resuming execution at PC: %u\n",
                       neorv32_cpu_csr_read(CSR_MEPC));
}

void fe_eng_irq(void) {
  neorv32_uart0_printf("[ALERT] Fetch-engine state error. "
                       "Resuming execution at PC: %u\n",
                       neorv32_cpu_csr_read(CSR_MEPC));
}

void pc_ra_exe_irq(void) {
  neorv32_uart0_printf("[ALERT] Execute-engine PC/RA error. "
                       "Resuming execution at PC: %u\n",
                       neorv32_cpu_csr_read(CSR_MEPC));
}

void pc_ra_fe_irq(void) {
  neorv32_uart0_printf("[ALERT] Fetch-engine PC/RA error. "
                       "Resuming execution at PC: %u\n",
                       neorv32_cpu_csr_read(CSR_MEPC));
}
/**@}*/

/**********************************************************************//**
 * Main function: installs the hardening fast-interrupt handlers, then runs
 * CoreMark. Any SECDED/parity correction reported during the run -- or
 * while idle afterwards, since interrupts stay enabled -- is printed over
 * UART0.
 *
 * @note Requires UART0 to be synthesized (IO_UART0_EN => true).
 * @return 0 on completion (never actually reached -- the CPU sleeps
 * forever after the benchmark finishes).
 **************************************************************************/
int main() {

  neorv32_uart0_setup(BAUD_RATE, 0);
  neorv32_rte_setup(); // install the default runtime trap/exception table

  // -- data memory ECC correction --
  neorv32_cpu_csr_set(CSR_MIE, 1 << CSR_MIE_FIRQ0E);
  neorv32_rte_handler_install(TRAP_CODE_FIRQ_0, dmem_irq);

  // -- register file ECC correction --
  neorv32_cpu_csr_set(CSR_MIE, 1 << CSR_MIE_FIRQ1E);
  neorv32_rte_handler_install(TRAP_CODE_FIRQ_1, regf_irq);

  // -- fetch-engine PC/RA parity error --
  neorv32_cpu_csr_set(CSR_MIE, 1 << CSR_MIE_FIRQ2E);
  neorv32_rte_handler_install(TRAP_CODE_FIRQ_2, pc_ra_fe_irq);

  // -- fetch-engine illegal-state error --
  neorv32_cpu_csr_set(CSR_MIE, 1 << CSR_MIE_FIRQ3E);
  neorv32_rte_handler_install(TRAP_CODE_FIRQ_3, fe_eng_irq);

  // -- execute-engine FSM state correction --
  neorv32_cpu_csr_set(CSR_MIE, 1 << CSR_MIE_FIRQ14E);
  neorv32_rte_handler_install(TRAP_CODE_FIRQ_14, exe_eng_irq);

  // -- execute-engine PC/RA parity error --
  neorv32_cpu_csr_set(CSR_MIE, 1 << CSR_MIE_FIRQ15E);
  neorv32_rte_handler_install(TRAP_CODE_FIRQ_15, pc_ra_exe_irq);


  // globally enable interrupts
  neorv32_cpu_csr_set(CSR_MSTATUS, 1 << CSR_MSTATUS_MIE);

  // run benchmark
  coremark_entry();

  // benchmark done -- stay in a low-power loop with interrupts still
  // enabled, so any correction that fires afterwards is still reported
  neorv32_uart0_printf("Sleeping...\n");
  while (1) {
    neorv32_cpu_sleep();
  }

  return 0;
}