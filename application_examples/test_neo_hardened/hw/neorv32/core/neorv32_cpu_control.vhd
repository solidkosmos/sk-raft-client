-- ========================================================================== --
-- NEORV32 CPU - Central Control Unit                                         --
-- -------------------------------------------------------------------------- --
-- + Execute engine:  Multi-cycle execution of instructions ("back-end")      --
-- + Trap controller: Handles interrupts and exceptions                       --
-- + CSR module:      Read/write access to control and status registers       --
-- + Debug module:    CPU debug mode handling (on-chip debugger)              --
-- + Trigger module:  Hardware-assisted breakpoints (on-chip debugger)        --
-- -------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32        --
-- Copyright (c) NEORV32 contributors.                                        --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.            --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.          --
-- SPDX-License-Identifier: BSD-3-Clause                                      --
-- ========================================================================== --
-- Modified by SolidKosmos S.A. (2026): added SECDED protection (secded_enc4b --
-- / secded_dec4b) with automatic recovery for the execute-engine FSM state   --
-- register, and parity generation/checking (parity_generator /               --
-- parity_checker) for the PC, PC2, and RA registers. Gated behind the        --
-- HARDEN_EN generic for hardened-vs- unhardened fault-injection comparisons: --
-- the encode/decode/parity component instances stay physically present       --
-- either way (this logic is fused too tightly into the FSM's combinational   --
-- core to cleanly remove via generate without restructuring), but when       --
-- HARDEN_EN is false, exe_fctv_state bypasses correction entirely (direct    --
-- passthrough of the raw, unprotected state register) and the PC/PC2/RA      --
-- parity-mismatch and state-correction bits are masked out of                --
-- custom_fast_irq, so no self-healing or error reporting actually occurs.    --
-- See THIRD_PARTY_NOTICES.md at the project root for the full list of        --
-- modified files.                                                            --
-- ========================================================================== --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_control is
  generic (
    -- General --
    HART_ID           : natural range 0 to 1023; -- hardware thread ID
    BOOT_ADDR         : std_ulogic_vector(31 downto 0); -- cpu boot address
    -- cpu debug-mode parking loop entry address, 4-byte aligned
    DEBUG_PARK_ADDR   : std_ulogic_vector(31 downto 0);
    -- cpu debug-mode exception entry address, 4-byte aligned
    DEBUG_EXC_ADDR    : std_ulogic_vector(31 downto 0);
    -- RISC-V ISA Extensions --
    RISCV_ISA_A       : boolean; -- atomic memory operations extension
    RISCV_ISA_B       : boolean; -- bit-manipulation extension
    RISCV_ISA_C       : boolean; -- compressed extension
    RISCV_ISA_E       : boolean; -- embedded-class register file extension
    RISCV_ISA_M       : boolean; -- mul/div extension
    RISCV_ISA_U       : boolean; -- user mode extension
    RISCV_ISA_Zaamo   : boolean; -- atomic read-modify-write extension
    RISCV_ISA_Zalrsc  : boolean; -- atomic reservation-set operations extension
    RISCV_ISA_Zcb     : boolean; -- additional code size reduction instructions
    RISCV_ISA_Zba     : boolean; -- shifted-add bit-manipulation extension
    RISCV_ISA_Zbb     : boolean; -- basic bit-manipulation extension
    -- bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkb    : boolean;
    RISCV_ISA_Zbkc    : boolean; -- carry-less multiplication instructions
    RISCV_ISA_Zbkx    : boolean; -- cryptography crossbar permutation extension
    RISCV_ISA_Zbs     : boolean; -- single-bit bit-manipulation extension
    RISCV_ISA_Zfinx   : boolean; -- 32-bit floating-point extension
    RISCV_ISA_Zibi    : boolean; -- branch with immediate
    RISCV_ISA_Zicntr  : boolean; -- base counters
    RISCV_ISA_Zicond  : boolean; -- integer conditional operations
    RISCV_ISA_Zihpm   : boolean; -- hardware performance monitors
    RISCV_ISA_Zimop   : boolean; -- may-be-operations
    RISCV_ISA_Zkn     : boolean; -- NIST algorithm suite
    RISCV_ISA_Zknd    : boolean; -- cryptography NIST AES decryption extension
    RISCV_ISA_Zkne    : boolean; -- cryptography NIST AES encryption extension
    RISCV_ISA_Zknh    : boolean; -- cryptography NIST hash extension
    RISCV_ISA_Zks     : boolean; -- ShangMi algorithm suite
    RISCV_ISA_Zksed   : boolean; -- ShangMi block cipher extension
    RISCV_ISA_Zksh    : boolean; -- ShangMi hash extension
    -- data-independent execution time (for cryptography operations)
    RISCV_ISA_Zkt     : boolean;
    RISCV_ISA_Zmmul   : boolean; -- multiply-only M sub-extension
    RISCV_ISA_Zxcfu   : boolean; -- custom (instr.) functions unit
    RISCV_ISA_Sdext   : boolean; -- external debug mode extension
    RISCV_ISA_Sdtrig  : boolean; -- trigger module extension
    RISCV_ISA_Smpmp   : boolean; -- physical memory protection
    -- Tuning Options --
    CPU_TRACE_EN      : boolean; -- enable CPU execution trace generator
    CPU_CONSTT_BR_EN  : boolean; -- constant-time branches
    CPU_FAST_MUL_EN   : boolean; -- use DSPs for M extension's multiplier
    CPU_FAST_SHIFT_EN : boolean; -- use barrel shifter for shift operations
    CPU_RF_HW_RST_EN  : boolean; -- enable full hardware reset for register file
    -- Hardening --
    -- enable FSM-state SECDED self-correction and PC/PC2/RA parity error
    -- reporting
    HARDEN_EN         : boolean := true
  );
  port (
    -- global control --
    -- global clock, rising edge
    clk_i         : in  std_ulogic;
    -- global reset, low-active, async
    rstn_i        : in  std_ulogic;
    ctrl_o        : out ctrl_bus_t;                         -- main control bus
    -- misc --
    -- front-end status and data
    frontend_i    : in  if_bus_t;
    hwtrig_i      : in  std_ulogic;                         -- hardware trigger
    -- data path interface --
    -- ALU iterative operation done
    alu_cp_done_i : in  std_ulogic;
    alu_cmp_i     : in  std_ulogic_vector(1 downto 0);      -- comparator status
    -- ALU address result
    alu_add_i     : in  std_ulogic_vector(XLEN-1 downto 0);
    rf_rs1_i      : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 1
    csr_rdata_o   : out std_ulogic_vector(XLEN-1 downto 0); -- CSR read data
    -- external CSR read data
    xcsr_rdata_i  : in  std_ulogic_vector(XLEN-1 downto 0);
    -- interrupts --
    -- debug mode (halt) request
    irq_dbg_i     : in  std_ulogic;
    -- risc-v mei, mti, msi
    irq_machine_i : in  std_ulogic_vector(2 downto 0);
    irq_fast_i    : in  std_ulogic_vector(15 downto 0);     -- fast interrupts
    -- load/store unit interface --
    lsu_wait_i    : in  std_ulogic;                         -- wait for data bus
    -- memory address register
    lsu_mar_i     : in  std_ulogic_vector(XLEN-1 downto 0);
    -- alignment/access errors
    lsu_err_i     : in  std_ulogic_vector(3 downto 0);
    
    ack_bram_irq_o     : out std_ulogic;
    ack_fe_eng_o  : out std_ulogic;
    ack_fe_pc_o   : out std_ulogic
  );
end neorv32_cpu_control;

architecture neorv32_cpu_control_rtl of neorv32_cpu_control is

  -- instruction execution engine --
--  type exe_engine_state_t is (EX_RESTART, EX_DISPATCH, EX_TRAP_ENTER,
--                              EX_TRAP_EXIT, EX_SLEEP, EX_EXECUTE,
--                              EX_ALU_WAIT, EX_BRANCH, EX_BRANCHED, EX_SYSTEM,
--                              EX_MEM_REQ, EX_MEM_RSP);
  signal ill_state_sig, ill_state  : std_ulogic;
  attribute dont_touch : string;
  
  attribute dont_touch of ill_state : signal is "true";

  subtype exe_engine_state_t is std_ulogic_vector(3 downto 0);
    constant EX_RESTART    : exe_engine_state_t := "0000";
    constant EX_DISPATCH   : exe_engine_state_t := "0001";
    constant EX_TRAP_ENTER : exe_engine_state_t := "0010";
    constant EX_TRAP_EXIT  : exe_engine_state_t := "0011"; 
    constant EX_SLEEP 	   : exe_engine_state_t := "0100"; 
    constant EX_EXECUTE    : exe_engine_state_t := "0101";
    constant EX_ALU_WAIT   : exe_engine_state_t := "0110"; 
    constant EX_BRANCH 	   : exe_engine_state_t := "0111"; 
    constant EX_BRANCHED   : exe_engine_state_t := "1000"; 
    constant EX_SYSTEM     : exe_engine_state_t := "1001"; 
    constant EX_MEM_REQ    : exe_engine_state_t := "1010"; 
    constant EX_MEM_RSP    : exe_engine_state_t := "1011";
 
  attribute dont_touch of exe_engine_state_t : subtype is "true";


  type exe_engine_t is record
    state : exe_engine_state_t;
    -- instruction word being executed right now
    ir    : std_ulogic_vector(31 downto 0);
    ci    : std_ulogic; -- current instruction is de-compressed instruction
    -- current PC (current instruction)
    pc    : std_ulogic_vector(XLEN-1 downto 0);
    -- next PC (next linear instruction)
    pc2   : std_ulogic_vector(XLEN-1 downto 0);
    ra    : std_ulogic_vector(XLEN-1 downto 0); -- return address
  end record;
  signal exe_engine, exe_engine_nxt : exe_engine_t;
  signal exe_corr_state, exe_fctv_state : exe_engine_state_t;
  
  -- parities for the most vulnerable registers --
  -- to catch erroneus program counter and return address transitions --
  -- may be cool to combine with checkpointing --
  type parities is record
    -- sync registers --
    pc_reg  : std_ulogic;
    pc2_reg : std_ulogic;
    ra_reg  : std_ulogic;
    -- comb signals --
    pc    : std_ulogic;
    alu_pc2    : std_ulogic;
    trap_ent_pc2   : std_ulogic;
    trap_ext_pc2   : std_ulogic;
    ra    : std_ulogic;
  end record;
  signal par : parities;
  signal check_ra, check_pc, check_pc2, nxt_pc_par : std_ulogic;
  signal nxt_pc : std_ulogic_vector(XLEN - 1 downto 0);
    

  -- trap controller --
  -- synchronous exception buffer (one bit per exception)
  type trap_ctrl_t is record exc_buf :
      std_ulogic_vector(exc_width_c-1 downto 0);
    -- set if there is a valid source in the exception buffer
    exc_fire    : std_ulogic;
    -- pending interrupt
    irq_pnd     : std_ulogic_vector(irq_width_c-1 downto 0);
    -- asynchronous exception/interrupt buffer (one bit per interrupt source)
    irq_buf     : std_ulogic_vector(irq_width_c-1 downto 0);
    -- set if an interrupt is actually kicking in
    irq_fire    : std_ulogic_vector(1 downto 0);
    -- trap ID for mcause CSR & debug-mode entry identifier
    cause       : std_ulogic_vector(6 downto 0);
    pc          : std_ulogic_vector(XLEN-1 downto 0); -- trap program counter
    --
    env_pending : std_ulogic; -- pending start of trap environment
    env_enter   : std_ulogic; -- enter trap environment
    env_exit    : std_ulogic; -- leave trap environment
    --
    instr_be    : std_ulogic; -- instruction fetch bus error
    instr_ma    : std_ulogic; -- instruction fetch misaligned address
    instr_il    : std_ulogic; -- illegal instruction
    ecall       : std_ulogic; -- ecall instruction
    ebreak      : std_ulogic; -- ebreak instruction
  end record;
  signal trap_ctrl : trap_ctrl_t;

  -- CPU control bus --
  signal ctrl, ctrl_nxt : ctrl_bus_t;

  -- control and status registers (CSRs) --
  type csr_t is record
    addr          : std_ulogic_vector(11 downto 0); -- physical access address
    we, we_nxt    : std_ulogic; -- write enable
    re, re_nxt    : std_ulogic; -- read enable
    operand       : std_ulogic_vector(XLEN-1 downto 0); -- write operand
    wdata         : std_ulogic_vector(XLEN-1 downto 0); -- write data
    rdata         : std_ulogic_vector(XLEN-1 downto 0); -- read data
    --
    mstatus_mie   : std_ulogic; -- machine-mode IRQ enable
    mstatus_mpie  : std_ulogic; -- previous machine-mode IRQ enable
    mstatus_mpp   : std_ulogic; -- machine previous privilege mode
    mstatus_mprv  : std_ulogic; -- effective privilege level for load/stores
    -- do not allow user mode to execute WFI instruction when set
    mstatus_tw    : std_ulogic;
    --
    mie_msi       : std_ulogic; -- machine software interrupt enable
    mie_mei       : std_ulogic; -- machine external interrupt enable
    mie_mti       : std_ulogic; -- machine timer interrupt enable
    mie_firq      : std_ulogic_vector(15 downto 0); -- fast interrupt enable
    --
    prv_level     : std_ulogic; -- current privilege level
    prv_level_eff : std_ulogic; -- current *effective* privilege level
    --
    mepc          : std_ulogic_vector(XLEN-1 downto 0); -- machine exception PC
    mcause        : std_ulogic_vector(5 downto 0); -- machine trap cause
    -- machine trap-handler base address
    mtvec         : std_ulogic_vector(XLEN-1 downto 0);
    -- machine bad address or instruction
    mtval         : std_ulogic_vector(XLEN-1 downto 0);
    -- machine trap instruction
    mtinst        : std_ulogic_vector(XLEN-1 downto 0);
    -- machine scratch register
    mscratch      : std_ulogic_vector(XLEN-1 downto 0);
    mcounteren_cy : std_ulogic; -- machine counter access enable: cycle counter
    -- machine counter access enable: instruction counter
    mcounteren_ir : std_ulogic;
    --
    dcsr_ebreakm  : std_ulogic; -- behavior of ebreak instruction in m-mode
    dcsr_ebreaku  : std_ulogic; -- behavior of ebreak instruction in u-mode
    dcsr_step     : std_ulogic; -- single-step mode
    -- current privilege level when entering debug mode
    dcsr_prv      : std_ulogic;
    dcsr_cause    : std_ulogic_vector(2 downto 0); -- why was debug mode entered
    -- debug mode control and status register
    dcsr_rd       : std_ulogic_vector(XLEN-1 downto 0);
    dpc           : std_ulogic_vector(XLEN-1 downto 0); -- mode program counter
    -- debug mode scratch register 0
    dscratch0     : std_ulogic_vector(XLEN-1 downto 0);
  end record;
  signal csr : csr_t;

  -- debug-mode controller --
  type debug_ctrl_t is record
    run, trig_hw, trig_break, trig_halt, trig_step : std_ulogic;
  end record;
  signal debug_ctrl : debug_ctrl_t;

  -- misc/helpers --
  signal if_reset     : std_ulogic; -- reset instruction fetch (front-end)
  -- fulfilled branch condition or unconditional jump
  signal branch_taken : std_ulogic;
  -- execution monitor cycle counter
  signal monitor_cnt  : std_ulogic_vector(alu_cp_tmo_c downto 0);
  signal monitor_exc  : std_ulogic; -- execution monitor timeout exception
  -- simplified opcode (2 LSBs hardwired to "11" to indicate rv32)
  signal opcode       : std_ulogic_vector(6 downto 0);
  -- instruction's immediate
  signal immediate    : std_ulogic_vector(XLEN-1 downto 0);
  signal illegal_cmd  : std_ulogic; -- illegal instruction check
  -- CSR access: [2] implemented, [1] r/w access, [0] privilege
  signal csr_valid    : std_ulogic_vector(2 downto 0);
  signal cnt_event    : std_ulogic_vector(11 downto 0); -- counter events
  signal ebreak_trig  : std_ulogic; -- environment break exception trigger
  
  
  -- COMPONENT SECTION --
  
  -- ECC enc/dec --
  component secded_enc4b
      Generic(
        data_len     : integer := 4;
        parities_len : integer := 3
      );
      Port ( 
            data_i       : in  std_ulogic_vector(data_len - 1 downto 0);
            par_o        : out std_ulogic_vector(parities_len - 1 downto 0);
            ded_par_o 	 : out std_ulogic
      );
  end component secded_enc4b;
  
  
  component secded_dec4b
      Generic(
        data_len     : integer := 4;
        parities_len : integer := 3
      );
      Port ( 
            data_i      : in std_ulogic_vector(data_len - 1  downto 0);
            ecc_pars_i  : in std_ulogic_vector(parities_len - 1  downto 0);  
            par_i       : in std_ulogic;
            dec_o       : out std_ulogic_vector(data_len - 1 downto 0);
            corr_bit_o  : out std_ulogic;
            uncorr      : out std_ulogic
       
      );
  end component secded_dec4b;
  
  
  -- Parity generator/checker --
  component parity_generator
      Generic(
            data_len : integer := 8
      );
      Port (
            data_i      : in std_ulogic_vector(data_len - 1 downto 0);
            par_o  : out std_ulogic
       );
   end component parity_generator;
   
   component parity_checker
      Generic(
        data_len : integer := 8
      );
      Port (
            data_i      : in std_ulogic_vector(data_len - 1 downto 0);
            par_i       : in std_ulogic;
            check_o      : out std_logic
       );
    end component parity_checker;
  
  attribute dont_touch of secded_enc4b, secded_dec4b, parity_checker,
      parity_generator : component is "true";
  
  -- ECC signals --
  signal ecc_parities, ecc_parities_reg : std_ulogic_vector(2 downto 0);
  signal ded_par, ded_par_reg : std_ulogic;
  signal corr_exe_eng_sig, corr_exe_eng_reg_irq : std_ulogic;
  
  
  signal check_exe_pc_ra : std_ulogic; -- pc ra parity reg
  -- '1' <=> HARDEN_EN, used to mask hardening-related IRQ bits
  signal harden_sig : std_ulogic;
  -- ACKNOWLEDGE SIGNALS --
  signal ack_bram_irq, ack_fe_eng, ack_fe_pc, ack_exe_eng,
      ack_exe_pc_ra : std_ulogic;
    
  signal custom_fast_irq : std_ulogic_vector(15 downto 0);
  
  -- signals for the trap assignments to pass throught to parity gens --
  -- trap enter/exit pcs
  signal trap_ent_pc, trap_ext_pc : std_ulogic_vector(XLEN - 1 downto 0);
  signal trap_en_par, trap_ex_par : std_ulogic; -- trap enter/exit pc parities
  
  -- fault injector sigs --
  signal countdown : unsigned(31 downto 0);
  signal fault_prev, fault_curr, fault : std_ulogic;
  
  attribute dont_touch of fault: signal is "true";
begin

  harden_sig <= '1' when HARDEN_EN else '0';

  -- Override the fast irq with our own signals for the execution engine --
  -- (both bits forced low when HARDEN_EN = false, so a disabled build reports
  --  no FSM-state corrections or PC/PC2/RA parity errors, matching stock
  --  NEORV32) --
  custom_fast_irq <= (check_exe_pc_ra and harden_sig)
      & (corr_exe_eng_reg_irq and harden_sig) & irq_fast_i(13 downto 0);

  -- ***************************************************************************
  -- Instruction Execution
  -- ***************************************************************************

  -- Immediate Generator -------------------------------------------------------
  -- ---------------------------------------------------------------------------
  imm_gen: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      immediate <= (others => '0');
    elsif rising_edge(clk_i) then
      -- prepare update of next PC (using ALU's PC + IMM in EX_EXECUTE state)
      if (exe_fctv_state = EX_DISPATCH) then
        -- is decompressed C instruction?
        if RISCV_ISA_C and (frontend_i.compr = '1') then
          immediate <= x"00000002";
        else
          immediate <= x"00000004";
        end if;
      else
        case opcode is
          when opcode_store_c => -- S-immediate
            immediate <= replicate_f(exe_engine.ir(31), 21)
                & exe_engine.ir(30 downto 25) & exe_engine.ir(11 downto 7);
          when opcode_branch_c => -- B-immediate
            immediate <= replicate_f(exe_engine.ir(31), 20) & exe_engine.ir(7)
                & exe_engine.ir(30 downto 25)
                & exe_engine.ir(11 downto 8) & '0';
          when opcode_lui_c | opcode_auipc_c => -- U-immediate
            immediate <= exe_engine.ir(31 downto 12) & x"000";
          when opcode_jal_c => -- J-immediate
            immediate <= replicate_f(exe_engine.ir(31), 12)
                & exe_engine.ir(19 downto 12) & exe_engine.ir(20)
                & exe_engine.ir(30 downto 21) & '0';
          when opcode_amo_c => -- atomic memory access
            immediate <= (others => '0');
          when others => -- I-immediate
            immediate <= replicate_f(exe_engine.ir(31), 21)
                & exe_engine.ir(30 downto 21) & exe_engine.ir(20);
        end case;
      end if;
    end if;
  end process imm_gen;


  -- Branch Condition Check ----------------------------------------------------
  -- ---------------------------------------------------------------------------
  branch_check: process(exe_engine, alu_cmp_i)
  begin
    if (exe_engine.ir(instr_opcode_lsb_c+2) = '0') then -- conditional branch
      if (exe_engine.ir(instr_funct3_msb_c) = '0') then -- beq / bne
        branch_taken <= alu_cmp_i(cmp_equal_c)
            xor exe_engine.ir(instr_funct3_lsb_c);
      else -- blt(u) / bge(u)
        branch_taken <= alu_cmp_i(cmp_less_c)
            xor exe_engine.ir(instr_funct3_lsb_c);
      end if;
    else -- unconditional branch
      branch_taken <= '1';
    end if;
  end process branch_check;
  
  
  -- Execute Engine FSM (Micro Sequencer) Sync ---------------------------------
  -- ---------------------------------------------------------------------------
  execute_engine_fsm_sync: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl             <= ctrl_bus_zero_c;
      exe_engine.state <= EX_RESTART;
      exe_engine.ir    <= (others => '0');
      exe_engine.ci    <= '0';
      -- 32-bit-aligned boot address
      exe_engine.pc    <= BOOT_ADDR(XLEN-1 downto 2) & "00";
      -- 32-bit-aligned boot address
      exe_engine.pc2   <= BOOT_ADDR(XLEN-1 downto 2) & "00";
      exe_engine.ra    <= (others => '0');
      
      ecc_parities_reg <= (others => '0');
      ded_par_reg      <= '0';
      
      par.pc_reg  <= '0';
      par.pc2_reg <= '0';
      par.ra_reg  <= '0';
      
      ill_state        <= '0';
      
      corr_exe_eng_reg_irq <= '0';
      check_exe_pc_ra      <= '0';
      
    elsif rising_edge(clk_i) then
      ctrl       <= ctrl_nxt;
      exe_engine <= exe_engine_nxt;

      -- ecc and parities sampling to registers --
      ecc_parities_reg <= ecc_parities;
      ded_par_reg      <= ded_par;
      -- parity registers for pc and ra --
      par.pc_reg  <= par.pc;
      par.pc2_reg <= nxt_pc_par; -- pass the valid pc2 par 
      par.ra_reg  <= par.ra;
      -- illegal state check --
      
      ill_state  <= ill_state_sig;
      
      -- exe engine ecc correction --
      if corr_exe_eng_sig = '1' then
        corr_exe_eng_reg_irq <= '1'; --latch the interrupt
      elsif ack_exe_eng = '1' then 
        corr_exe_eng_reg_irq <= '0'; -- ack and release
      end if;
      
      -- pc ra exe engine par irq --
      if check_pc = '1' or check_pc2 = '1' or check_ra = '1' then
        check_exe_pc_ra <= '1'; 
      elsif ack_exe_pc_ra = '1' then
        check_exe_pc_ra <= '0';
      end if;
      
    end if;
  end process execute_engine_fsm_sync;

  -- simplified rv32 opcode --
  opcode <= exe_engine.ir(instr_opcode_msb_c downto instr_opcode_lsb_c+2)
      & "11";
  
  
  -- decode the current state and clear any SEUs --
  curr_state_decorer:secded_dec4b
    generic map(
        data_len => 4,
        parities_len => 3
    )
    port map(
        data_i     => exe_engine.state,
        ecc_pars_i => ecc_parities_reg,
        par_i      => ded_par_reg,
        dec_o      => exe_corr_state,
        corr_bit_o => corr_exe_eng_sig,
        uncorr     => ill_state_sig -- double-bit (uncorrectable) state error
    );

   -- Effective FSM state: the corrected state, or EX_RESTART on an
   -- uncorrectable (double-bit) state error. EX_RESTART flushes and restarts
   -- instruction fetch. when HARDEN_EN = false, bypass SECDED correction
   -- entirely: the FSM runs directly off the raw, unprotected state register
   -- (stock NEORV32 behavior) --
   exe_fctv_state <= exe_engine.state when not HARDEN_EN else
                      EX_RESTART when ill_state_sig = '1' else exe_corr_state;
    
   -- check parities --
   pc_par_check:parity_checker
     generic map(
        data_len => XLEN
     )
     port map(
        data_i  => exe_engine.pc,
        par_i   => par.pc_reg,
        check_o => check_pc
     );
   
   pc2_par_check:parity_checker
     generic map(
        data_len => XLEN
     )
     port map(
        data_i  => exe_engine.pc2,
        par_i   => par.pc2_reg,
        check_o => check_pc2
     );
     
   ra_par_check:parity_checker
     generic map(
        data_len => XLEN
     )
     port map(
        data_i  => exe_engine.ra,
        par_i   => par.ra_reg,
        check_o => check_ra
     );

  
  -- Execute Engine FSM (Micro Sequencer) Comb ---------------------------------
  -- ---------------------------------------------------------------------------
  execute_engine_fsm_comb: process(exe_engine, debug_ctrl, trap_ctrl, hwtrig_i,
                                   opcode, frontend_i, csr, ctrl, alu_cp_done_i,
                                   lsu_wait_i, alu_add_i, branch_taken,
                                   exe_fctv_state, par, trap_ent_pc,
                                   trap_ext_pc, nxt_pc)
    variable funct3_v : std_ulogic_vector(2 downto 0);
    variable funct7_v : std_ulogic_vector(6 downto 0);
  begin
    -- shortcuts --
    funct3_v := exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c);
    funct7_v := exe_engine.ir(instr_funct7_msb_c downto instr_funct7_lsb_c);

    -- arbiter defaults --
    exe_engine_nxt.state <= exe_fctv_state;
    exe_engine_nxt.ir    <= exe_engine.ir;
    exe_engine_nxt.ci    <= exe_engine.ci;
    exe_engine_nxt.pc    <= exe_engine.pc;
    exe_engine_nxt.pc2   <= exe_engine.pc2;
    -- output zero if not a branch instruction
    exe_engine_nxt.ra    <= (others => '0');
    if_reset             <= '0';
    trap_ctrl.env_enter  <= '0';
    trap_ctrl.env_exit   <= '0';
    trap_ctrl.instr_be   <= '0';
    trap_ctrl.instr_ma   <= '0';
    trap_ctrl.ecall      <= '0';
    trap_ctrl.ebreak     <= '0';
    csr.we_nxt           <= '0';
    csr.re_nxt           <= '0';
    -- all zero/off by default (ALU operation = ZERO, ALU.adder_out = ADD)
    ctrl_nxt             <= ctrl_bus_zero_c;
    
    -- constant pc2 jumps to get parities from and pass to the checks --
    nxt_pc <= alu_add_i(XLEN-1 downto 1) & '0';
    nxt_pc_par <= par.pc2_reg;
    
    -- get trap_ent_pc constantly and pass the value when in trap enter state --
    if (trap_ctrl.cause(5) = '1') and RISCV_ISA_Sdext then -- debug mode entry
      -- start at "parking loop" <normal_entry>
      trap_ent_pc <= DEBUG_PARK_ADDR(XLEN-1 downto 2) & "00";
    -- any other trap INSIDE debug mode
    elsif (debug_ctrl.run = '1') and RISCV_ISA_Sdext then
      -- start at "parking loop" <exception_entry>
      trap_ent_pc <= DEBUG_EXC_ADDR(XLEN-1 downto 2) & "00";
    -- M-mode trap: vectored mode and interrupt
    elsif (csr.mtvec(0) = '1') and (trap_ctrl.cause(6) = '1') then
      -- PC = mtvec + 4 * mcause
      trap_ent_pc <= csr.mtvec(XLEN-1 downto 7)
          & trap_ctrl.cause(4 downto 0) & "00";
    else -- M-mode trap: direct mode
      trap_ent_pc <= csr.mtvec(XLEN-1 downto 2) & "00"; -- PC = mtvec
    end if;
    
    -- get trap_ext_pc constantly and pass the value when in trap enter state --
    if (debug_ctrl.run = '1') and RISCV_ISA_Sdext then -- debug mode exit
      trap_ext_pc <= csr.dpc(XLEN-1 downto 1) & '0';
    else -- normal end of trap
      trap_ext_pc <= csr.mepc(XLEN-1 downto 1) & '0';
    end if;
    
    
    
    
    -- ALU sign control --
    if (opcode(4) = '1') then -- ALU ops
      -- unsigned ALU operation? (SLTIU, SLTU)
      ctrl_nxt.alu_unsigned <= funct3_v(0);
    else -- branches
      ctrl_nxt.alu_unsigned <= funct3_v(1); -- unsigned branches? (BLTU, BGEU)
    end if;

    -- ALU operand A: is PC? --
    case opcode is
      when opcode_auipc_c | opcode_jal_c | opcode_branch_c =>
        ctrl_nxt.alu_opa_mux <= '1';
      when others =>
        ctrl_nxt.alu_opa_mux <= '0';
    end case;

    -- ALU operand B: is immediate? --
    case opcode is
      when opcode_alui_c | opcode_lui_c | opcode_auipc_c | opcode_load_c
          | opcode_store_c | opcode_amo_c | opcode_branch_c | opcode_jal_c
          | opcode_jalr_c =>
        ctrl_nxt.alu_opb_mux <= '1';
      when others =>
        ctrl_nxt.alu_opb_mux <= '0';
    end case;

    -- (atomic) memory read/write access --
    -- atomic read-modify-write operation
    if RISCV_ISA_Zaamo and (opcode(2) = opcode_amo_c(2))
        and (exe_engine.ir(instr_funct5_lsb_c+1) = '0') then
      ctrl_nxt.lsu_rmw <= '1'; -- read-modify-write
      ctrl_nxt.lsu_rvs <= '0';
      -- executed as single load for the CPU control logic
      ctrl_nxt.lsu_rw  <= '0';
    -- atomic reservation-set operation
    elsif RISCV_ISA_Zalrsc and (opcode(2) = opcode_amo_c(2))
        and (exe_engine.ir(instr_funct5_lsb_c+1) = '1') then
      ctrl_nxt.lsu_rmw <= '0';
      ctrl_nxt.lsu_rvs <= '1'; -- reservation-set
      ctrl_nxt.lsu_rw  <= exe_engine.ir(instr_funct5_lsb_c);
    else -- normal load/store
      ctrl_nxt.lsu_rmw <= '0';
      ctrl_nxt.lsu_rvs <= '0';
      ctrl_nxt.lsu_rw  <= exe_engine.ir(instr_opcode_lsb_c+5);
    end if;
    
   
    
    -- state machine --
    case exe_fctv_state is

      when EX_RESTART => -- reset and restart instruction fetch at next PC
      -- ------------------------------------------------------------
        -- house keeping: force writing zero to x0 if it's a phys. register
        ctrl_nxt.rf_zero_we  <= not bool_to_ulogic_f(CPU_RF_HW_RST_EN);
        if_reset             <= '1';
        exe_engine_nxt.state <= EX_BRANCHED; -- delay cycle to restart front-end

        

      -- wait for ISSUE ENGINE to emit a valid instruction word
      when EX_DISPATCH =>
      -- ------------------------------------------------------------
        -- prepare update of next PC in EX_EXECUTE (opa = current PC)
        ctrl_nxt.alu_opa_mux <= '1';
        -- prepare update of next PC in EX_EXECUTE (opb = imm = +2/4)
        ctrl_nxt.alu_opb_mux <= '1';
        --
        -- pending trap or pending exception (fast)
        if (trap_ctrl.env_pending = '1') or (trap_ctrl.exc_fire = '1') then
          exe_engine_nxt.state <= EX_TRAP_ENTER;
        -- new instruction word available and no pending HW trigger
        elsif (frontend_i.valid = '1') and (hwtrig_i = '0') then
          -- access fault during instruction fetch
          trap_ctrl.instr_be   <= frontend_i.fault;
          -- this is a de-compressed instruction
          exe_engine_nxt.ci    <= frontend_i.compr;
          exe_engine_nxt.ir    <= frontend_i.instr; -- instruction word
          -- PC <= next PC
          exe_engine_nxt.pc    <= exe_engine.pc2(XLEN-1 downto 1) & '0';
          exe_engine_nxt.state <= EX_EXECUTE; -- start executing new instruction
        end if;

      when EX_TRAP_ENTER => -- enter trap environment and jump to trap vector
      -- ------------------------------------------------------------
        exe_engine_nxt.pc2 <= trap_ent_pc; -- pass the trap pc
        nxt_pc_par <= par.trap_ent_pc2; -- and the parity 
        trap_ctrl.env_enter  <= '1';
        exe_engine_nxt.state <= EX_RESTART; -- restart instruction fetch
        
        
     
      when EX_TRAP_EXIT => -- return from trap environment and jump to trap PC
      -- ------------------------------------------------------------        
        exe_engine_nxt.pc2 <= trap_ext_pc; -- pass the trap pc
        nxt_pc_par <= par.trap_ext_pc2; -- and the parity 
        trap_ctrl.env_exit   <= '1';
        exe_engine_nxt.state <= EX_RESTART; -- restart instruction fetch

      -- decode and prepare execution (FSM will be here for exactly 1 cycle in
      -- any case)
      when EX_EXECUTE =>
      -- ------------------------------------------------------------
        exe_engine_nxt.pc2 <= nxt_pc; -- next PC = PC + immediate
        -- pass the parity when in valid state
        nxt_pc_par         <= par.alu_pc2;

        -- decode instruction class/type; [NOTE] register file is read in THIS
        -- stage; due to the sync read data will be available in the NEXT state
        -- --
        case opcode is

          -- register/immediate ALU operation --
          when opcode_alu_c | opcode_alui_c =>

            -- ALU core operation --
            case funct3_v is
              -- ADD(I), SUB
              when funct3_sadd_c => ctrl_nxt.alu_op <= alu_op_add_c;
              when funct3_slt_c  => ctrl_nxt.alu_op <= alu_op_slt_c; -- SLT(I)
              when funct3_sltu_c => ctrl_nxt.alu_op <= alu_op_slt_c; -- SLTU(I)
              when funct3_xor_c  => ctrl_nxt.alu_op <= alu_op_xor_c; -- XOR(I)
              when funct3_or_c   => ctrl_nxt.alu_op <= alu_op_or_c;  -- OR(I)
              when funct3_and_c  => ctrl_nxt.alu_op <= alu_op_and_c; -- AND(I)
              when others        => ctrl_nxt.alu_op <= alu_op_zero_c;
            end case;

            -- addition/subtraction control --
            -- SLT(I), SLTU(I)
            -- SUB
            if (funct3_v(2 downto 1) = funct3_slt_c(2 downto 1))
                or ((funct3_v = funct3_sadd_c) and (opcode(5) = '1')
                    and (exe_engine.ir(instr_funct7_msb_c-1) = '1')) then
              ctrl_nxt.alu_sub <= '1';
            end if;

            -- is base rv32i/e ALU[I] instruction (excluding shifts)? --
            -- base ALUI instruction (excluding SLLI, SRLI, SRAI)
            -- base ALU instruction (excluding SLL, SRL, SRA)
            if ((opcode(5) = '0') and (funct3_v /= funct3_sll_c) and
                (funct3_v /= funct3_sr_c)) or
               ((opcode(5) = '1') and
                (((funct3_v = funct3_sadd_c) and (funct7_v = "0000000")) or
                 ((funct3_v = funct3_sadd_c) and (funct7_v = "0100000")) or
                 ((funct3_v = funct3_slt_c)  and (funct7_v = "0000000")) or
                 ((funct3_v = funct3_sltu_c) and (funct7_v = "0000000")) or
                 ((funct3_v = funct3_xor_c)  and (funct7_v = "0000000")) or
                 ((funct3_v = funct3_or_c)   and (funct7_v = "0000000")) or
                 ((funct3_v = funct3_and_c)  and (funct7_v = "0000000")))) then
              -- valid RF write-back (won't happen if exception)
              ctrl_nxt.rf_wb_en    <= '1';
              exe_engine_nxt.state <= EX_DISPATCH;
            -- [NOTE] illegal ALU[I] instructions are handled as multi-cycle
            -- operations that will time-out as no ALU co-processor responds
            else
              -- trigger ALU[I] opcode-space co-processor
              ctrl_nxt.alu_cp_alu  <= '1';
              exe_engine_nxt.state <= EX_ALU_WAIT;
            end if;

          -- load upper immediate --
          when opcode_lui_c =>
            ctrl_nxt.alu_op      <= alu_op_movb_c; -- pass immediate
            -- valid RF write-back (won't happen if exception)
            ctrl_nxt.rf_wb_en    <= '1';
            exe_engine_nxt.state <= EX_DISPATCH;

          -- add upper immediate to PC --
          when opcode_auipc_c =>
            ctrl_nxt.alu_op      <= alu_op_add_c; -- add PC and immediate
            -- valid RF write-back (won't happen if exception)
            ctrl_nxt.rf_wb_en    <= '1';
            exe_engine_nxt.state <= EX_DISPATCH;

          -- memory access --
          when opcode_load_c | opcode_store_c | opcode_amo_c =>
            exe_engine_nxt.state <= EX_MEM_REQ;

          -- branch / jump-and-link (with register) --
          when opcode_branch_c | opcode_jal_c | opcode_jalr_c =>
            exe_engine_nxt.state <= EX_BRANCH;

          -- memory fence operations --
          when opcode_fence_c =>
            if (exe_engine.ir(instr_funct3_lsb_c) = '0') then -- data fence
              ctrl_nxt.lsu_fence <= '1';
            else -- instruction fence
              ctrl_nxt.if_fence <= '1';
            end if;
            -- reset instruction fetch + IPB via branch to PC+4 (actually only
            -- required for fence.i)
            exe_engine_nxt.state <= EX_RESTART;

          -- FPU: floating-point operations --
          when opcode_fpu_c =>
            ctrl_nxt.alu_cp_fpu  <= '1'; -- trigger FPU co-processor
            -- will be aborted via monitor timeout if FPU is not implemented
            exe_engine_nxt.state <= EX_ALU_WAIT;

          -- CFU: custom RISC-V instructions --
          when opcode_cust0_c | opcode_cust1_c =>
            ctrl_nxt.alu_cp_cfu  <= '1'; -- trigger CFU co-processor
            -- will be aborted via monitor timeout if CFU is not implemented
            exe_engine_nxt.state <= EX_ALU_WAIT;

          -- environment/CSR operation or ILLEGAL opcode --
          when others =>
            if (funct3_v = funct3_env_c) or (funct3_v = funct3_zimop_c)
                or (((funct3_v = funct3_csrrw_c)
                     or (funct3_v = funct3_csrrwi_c))
                    and (exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c)
                         = "00000")) then
              -- no read if CSRRW[I] and rd = 0 OR if environment instruction OR
              -- if may-be-operation
              csr.re_nxt <= '0';
            else
              csr.re_nxt <= '1';
            end if;
            exe_engine_nxt.state <= EX_SYSTEM;

        end case; -- /EX_EXECUTE

      -- wait for multi-cycle ALU co-processor operation to finish or trap
      when EX_ALU_WAIT =>
      -- ------------------------------------------------------------
        ctrl_nxt.alu_op   <= alu_op_cp_c;
        -- valid RF write-back (won't happen if exception)
        ctrl_nxt.rf_wb_en <= alu_cp_done_i;
        if (alu_cp_done_i = '1')
            or (or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                              exc_iaccess_c)) = '1') then
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when EX_BRANCH => -- update next PC on taken branches and jumps
      -- ------------------------------------------------------------
        -- output return address
        exe_engine_nxt.ra <= exe_engine.pc2(XLEN-1 downto 1) & '0';
        -- save return address if link operation (won't happen if exception)
        ctrl_nxt.rf_wb_en <= exe_engine.ir(instr_opcode_lsb_c+2);
        if (branch_taken = '1') then -- taken/unconditional branch
          -- reset instruction fetch to restart at modified PC
          if_reset             <= '1';
          -- branch destination misaligned?
          trap_ctrl.instr_ma   <= alu_add_i(1)
              and bool_to_ulogic_f(not RISCV_ISA_C);
          exe_engine_nxt.pc2   <= nxt_pc;
          -- pass the parity when in valid state
          nxt_pc_par           <= par.alu_pc2;
          -- shortcut (faster than going to EX_RESTART)
          exe_engine_nxt.state <= EX_BRANCHED;
        elsif CPU_CONSTT_BR_EN then -- constant-time branches
          if_reset             <= '1';
          exe_engine_nxt.state <= EX_BRANCHED;
        else
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      -- delay cycle to wait for reset of front-end (instruction fetch)
      when EX_BRANCHED =>
      -- ------------------------------------------------------------
        exe_engine_nxt.state <= EX_DISPATCH;

      when EX_MEM_REQ => -- trigger memory request
      -- ------------------------------------------------------------
        -- memory request if no instruction exception
        if (or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                          exc_iaccess_c)) = '0') then
          ctrl_nxt.lsu_req     <= '1';
          exe_engine_nxt.state <= EX_MEM_RSP;
        else
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when EX_MEM_RSP => -- wait for memory response
      -- ------------------------------------------------------------
        -- bus system has completed the transaction (if there was any)
        -- load/store exception
        if (lsu_wait_i = '0')
            or (or_reduce_f(trap_ctrl.exc_buf(exc_laccess_c downto
                                              exc_salign_c)) = '1') then
          -- write-back to RF if read operation (won't happen in case of
          -- exception)
          ctrl_nxt.rf_wb_en    <= (not ctrl.lsu_rw) or ctrl.lsu_rvs
              or ctrl.lsu_rmw;
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when EX_SLEEP => -- sleep mode
      -- ------------------------------------------------------------
        -- enabled pending IRQ, debug-mode, single-step
        if (or_reduce_f(trap_ctrl.irq_buf) = '1') or (debug_ctrl.run = '1')
            or (csr.dcsr_step = '1') then
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      -- CSR/ENVIRONMENT operation; no effect if illegal instruction
      when EX_SYSTEM =>
      -- ------------------------------------------------------------
        exe_engine_nxt.state <= EX_DISPATCH; -- default
        -- non-illegal ENV instruction
        if (funct3_v = funct3_env_c)
            and (or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                               exc_iaccess_c)) = '0') then
          -- three LSBs are sufficient here
          case exe_engine.ir(instr_imm12_lsb_c+2 downto instr_imm12_lsb_c) is
            when "000"  => trap_ctrl.ecall      <= '1'; -- ecall
            when "001"  => trap_ctrl.ebreak     <= '1'; -- ebreak
            when "010"  => exe_engine_nxt.state <= EX_TRAP_EXIT; -- xret
            when "101"  => exe_engine_nxt.state <= EX_SLEEP; -- wfi
            -- illegal or CSR operation
            when others => exe_engine_nxt.state <= EX_DISPATCH;
          end case;
        end if;
        -- write to CSR if not environment OR ma-be-operation --
        if (funct3_v /= funct3_env_c) and (funct3_v /= funct3_zimop_c)
            and (((funct3_v = funct3_csrrw_c) or (funct3_v = funct3_csrrwi_c))
                 or (exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c)
                     = "00000")) then
          -- CSRRW[I]: always write CSR; CSRR[S/C][I]: write CSR if rs1/imm5 is
          -- NOT zero; won't happen if exception
          csr.we_nxt <= '1';
        end if;
        -- always write to RF (even if csr.re = 0, but then we have rd = 0);
        -- ENVIRONMENT operations have rd = zero so this does not hurt --
        ctrl_nxt.rf_wb_en <= '1'; -- won't happen if exception

      when others => -- undefined
      -- ------------------------------------------------------------
        exe_engine_nxt.state <= EX_TRAP_ENTER;

    end case;
    
  end process execute_engine_fsm_comb;
  
  -- encode before sending to sync fsm --
  next_state_encoder:secded_enc4b
        generic map(
           data_len     => 4,
           parities_len => 3 
        )
        port map(
            data_i    => exe_engine_nxt.state,
            par_o     => ecc_parities,
            ded_par_o => ded_par
        );
  
  
  -- generate parities --
   pc_par_gen:parity_generator
     generic map(
        data_len => XLEN
     )
     port map(
        data_i => exe_engine_nxt.pc,
        par_o  => par.pc
        
     );
     
   pc2_alu_par_gen:parity_generator
     generic map(
        data_len => XLEN
     )
     port map(
        data_i => nxt_pc,
        par_o  => par.alu_pc2
        
     );
     
   pc2_trap_en_par_gen:parity_generator
     generic map(
        data_len => XLEN
     )
     port map(
        data_i => trap_ent_pc,
        par_o  => par.trap_ent_pc2
        
     );
     
   pc2_trap_ex_par_gen:parity_generator
    generic map(
       data_len => XLEN
    )
    port map(
       data_i => trap_ext_pc,
       par_o  => par.trap_ext_pc2
        
    );
     
   ra_par_gen:parity_generator 
     generic map(
        data_len => XLEN
     )
     port map(
        data_i  => exe_engine_nxt.ra,
        par_o   => par.ra
     );
  
    -- Acknowledge clearance --
    ack_clear:process(rstn_i, clk_i)
        begin
            if rstn_i = '0' then
                ack_bram_irq_o <= '0';
                ack_exe_eng    <= '0';
                ack_exe_pc_ra  <= '0';
                ack_fe_eng_o   <= '0';
                ack_fe_pc_o    <= '0';
                  
            elsif rising_edge(clk_i) then
                -- Default states
                ack_bram_irq_o <= '0';
                ack_fe_eng_o   <= '0';   
                ack_fe_pc_o    <= '0';
                ack_exe_pc_ra  <= '0';
                ack_exe_eng    <= '0';
                
                -- ONLY ACKNOWLEDGE WHEN THE CPU ENTERS THE TRAP --
                if trap_ctrl.env_enter = '1' then
                    case trap_ctrl.cause is 
                        when trap_firq0_c  => ack_bram_irq_o <= '1';
                        when trap_firq1_c  => ack_bram_irq_o <= '1';
                        when trap_firq2_c  => ack_fe_pc_o    <= '1'; 
                        when trap_firq3_c  => ack_fe_eng_o   <= '1';
                        when trap_firq14_c => ack_exe_eng    <= '1'; 
                        when trap_firq15_c => ack_exe_pc_ra  <= '1';
                        when others => null;
                    end case;
                end if;
                   
                
            end if;
    end process ack_clear;
    

  -- CPU Control Bus Output ----------------------------------------------------
  -- ---------------------------------------------------------------------------
  -- instruction fetch --
  ctrl_o.if_fence     <= ctrl.if_fence;
  ctrl_o.if_reset     <= if_reset;
  ctrl_o.if_ready     <= '1' when (exe_fctv_state = EX_DISPATCH) else '0';
  -- program counter --
  ctrl_o.pc_cur       <= exe_engine.pc(XLEN-1 downto 1) & '0';
  ctrl_o.pc_nxt       <= exe_engine.pc2(XLEN-1 downto 1) & '0';
  ctrl_o.pc_ret       <= exe_engine.ra(XLEN-1 downto 1) & '0';
  ctrl_o.pc_cur_par   <= par.pc_reg ;
  ctrl_o.pc_nxt_par   <= par.pc2_reg;
  ctrl_o.pc_ret_par   <= par.ra_reg ;
  -- register file --
  -- write-back only if ...
  -- no instruction exception
  -- no data exception
  ctrl_o.rf_wb_en <= ctrl.rf_wb_en
      and (not or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                             exc_iaccess_c)))
      and (not or_reduce_f(trap_ctrl.exc_buf(exc_laccess_c downto
                                             exc_salign_c)));
  ctrl_o.rf_rs1       <= exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c);
  ctrl_o.rf_rs2       <= exe_engine.ir(instr_rs2_msb_c downto instr_rs2_lsb_c);
  ctrl_o.rf_rd        <= exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c);
  ctrl_o.rf_zero_we   <= ctrl.rf_zero_we;
  -- alu --
  ctrl_o.alu_op       <= ctrl.alu_op;
  ctrl_o.alu_sub      <= ctrl.alu_sub;
  ctrl_o.alu_opa_mux  <= ctrl.alu_opa_mux;
  ctrl_o.alu_opb_mux  <= ctrl.alu_opb_mux;
  ctrl_o.alu_unsigned <= ctrl.alu_unsigned;
  ctrl_o.alu_imm      <= immediate;
  -- trigger if no instruction exception
  ctrl_o.alu_cp_alu   <= ctrl.alu_cp_alu
      and (not or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                             exc_iaccess_c)));
  -- trigger if no instruction exception
  ctrl_o.alu_cp_cfu   <= ctrl.alu_cp_cfu
      and (not or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                             exc_iaccess_c)));
  -- trigger if no instruction exception
  ctrl_o.alu_cp_fpu   <= ctrl.alu_cp_fpu
      and (not or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                             exc_iaccess_c)));
  -- load/store unit --
  ctrl_o.lsu_req      <= ctrl.lsu_req;
  ctrl_o.lsu_rw       <= ctrl.lsu_rw;
  ctrl_o.lsu_rmw      <= ctrl.lsu_rmw;
  ctrl_o.lsu_rvs      <= ctrl.lsu_rvs;
  -- write memory output registers (data & address)
  ctrl_o.lsu_mo_we    <= '1' when (exe_fctv_state = EX_MEM_REQ) else '0';
  ctrl_o.lsu_fence    <= ctrl.lsu_fence;
  -- effective privilege level for loads/stores in M-mode
  ctrl_o.lsu_priv     <= csr.mstatus_mpp when (csr.mstatus_mprv = '1')
      else csr.prv_level_eff;
  -- control and status registers --
  ctrl_o.csr_we       <= csr.we;
  ctrl_o.csr_re       <= csr.re;
  ctrl_o.csr_addr     <= csr.addr;
  ctrl_o.csr_wdata    <= csr.wdata;
  -- counter events --
  ctrl_o.cnt_event    <= cnt_event;
  -- instruction word bit fields --
  ctrl_o.ir_funct3    <=
      exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c);
  ctrl_o.ir_funct12   <=
      exe_engine.ir(instr_imm12_msb_c downto instr_imm12_lsb_c);
  ctrl_o.ir_opcode    <=
      exe_engine.ir(instr_opcode_msb_c downto instr_opcode_lsb_c);
  -- status --
  ctrl_o.cpu_priv     <= csr.prv_level_eff;
  ctrl_o.cpu_trap     <= trap_ctrl.env_enter;
  ctrl_o.cpu_sync_exc <= trap_ctrl.exc_fire;
  ctrl_o.cpu_debug    <= debug_ctrl.run;


  -- CPU (Counter) Events ------------------------------------------------------
  -- ---------------------------------------------------------------------------
  -- active cycle
  cnt_event(cnt_event_cy_c)       <= '0' when (exe_fctv_state = EX_SLEEP)
      else '1';
  -- time: not available
  cnt_event(cnt_event_tm_c)       <= '0';
  -- retired (=executed) instruction
  cnt_event(cnt_event_ir_c)       <= '1' when (exe_fctv_state = EX_EXECUTE)
      else '0';
  -- executed compressed instruction
  cnt_event(cnt_event_compr_c)    <= '1' when (exe_fctv_state = EX_EXECUTE)
      and (exe_engine.ci = '1') else '0';
  -- instruction dispatch wait cycle
  cnt_event(cnt_event_wait_dis_c) <= '1' when (exe_fctv_state = EX_DISPATCH)
      and (frontend_i.valid = '0') else '0';
  -- multi-cycle ALU wait cycle
  cnt_event(cnt_event_wait_alu_c) <= '1' when (exe_fctv_state = EX_ALU_WAIT)
      else '0';
  -- executed branch instruction
  cnt_event(cnt_event_branch_c)   <= '1' when (exe_fctv_state = EX_BRANCH)
      else '0';
  -- control flow transfer
  cnt_event(cnt_event_branched_c) <= '1' when (exe_fctv_state = EX_BRANCHED)
      else '0';
  -- executed load operation
  cnt_event(cnt_event_load_c)     <= '1' when (ctrl.lsu_req = '1')
      and ((ctrl.lsu_rw = '0') or (ctrl.lsu_rmw = '1')) else '0';
  -- executed store operation
  cnt_event(cnt_event_store_c)    <= '1' when (ctrl.lsu_req = '1')
      and ((ctrl.lsu_rw = '1') or (ctrl.lsu_rmw = '1')) else '0';
  -- load/store memory wait cycle
  cnt_event(cnt_event_wait_lsu_c) <= '1' when (ctrl.lsu_req = '0')
      and (exe_fctv_state = EX_MEM_RSP) else '0';
  -- entered trap
  cnt_event(cnt_event_trap_c)     <= '1' when (trap_ctrl.env_enter = '1')
      else '0';


  -- ***************************************************************************
  -- Illegal Instruction Detection
  -- ***************************************************************************

  -- Instruction Execution Monitor (trap if multi-cycle instruction does not
  -- complete) -----------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  multi_cycle_monitor: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      monitor_cnt <= (others => '0');
    elsif rising_edge(clk_i) then
      if (exe_fctv_state = EX_ALU_WAIT) then
        monitor_cnt <= std_ulogic_vector(unsigned(monitor_cnt) + 1);
      else
        monitor_cnt <= (others => '0');
      end if;
    end if;
  end process multi_cycle_monitor;

  -- raise illegal instruction exception if a multi-cycle instruction takes
  -- longer than a bound amount of time --
  monitor_exc <= monitor_cnt(monitor_cnt'left);


  -- CSR Access Check ----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  csr_check: process(exe_engine, csr, debug_ctrl)
    variable csr_addr_v : std_ulogic_vector(11 downto 0);
  begin
    -- shortcut: CSR address right from the instruction word --
    csr_addr_v := exe_engine.ir(instr_imm12_msb_c downto instr_imm12_lsb_c);

    -- ------------------------------------------------------------
    -- Available at all
    -- ------------------------------------------------------------
    case csr_addr_v is

      -- floating-point-unit CSRs --
      when csr_fflags_c | csr_frm_c | csr_fcsr_c =>
        -- available if FPU implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zfinx);

      -- machine trap setup/handling, environment/information registers, etc. --
      when csr_mstatus_c | csr_mstatush_c | csr_misa_c | csr_mie_c | csr_mtvec_c
          | csr_mscratch_c | csr_mepc_c | csr_mcause_c | csr_mip_c | csr_mtval_c
          | csr_mtinst_c | csr_mcountinhibit_c | csr_mvendorid_c | csr_marchid_c
          | csr_mimpid_c | csr_mhartid_c | csr_mconfigptr_c | csr_mxcsr_c
          | csr_mxisa_c =>
        csr_valid(2) <= '1'; -- always implemented

      -- machine-controlled user-mode CSRs --
      when csr_mcounteren_c | csr_menvcfg_c | csr_menvcfgh_c =>
        -- available if U-mode implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_U);

      -- physical memory protection (PMP) --
      -- lowest 4 configuration registers only
      -- lowest 16 address registers only
      when csr_pmpcfg0_c | csr_pmpcfg1_c | csr_pmpcfg2_c | csr_pmpcfg3_c
          | csr_pmpaddr0_c | csr_pmpaddr1_c | csr_pmpaddr2_c | csr_pmpaddr3_c
          | csr_pmpaddr4_c | csr_pmpaddr5_c | csr_pmpaddr6_c | csr_pmpaddr7_c
          | csr_pmpaddr8_c | csr_pmpaddr9_c | csr_pmpaddr10_c | csr_pmpaddr11_c
          | csr_pmpaddr12_c | csr_pmpaddr13_c | csr_pmpaddr14_c
          | csr_pmpaddr15_c =>
        -- available if PMP implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Smpmp);

      -- hardware performance monitors (HPM) --
      -- machine counters LOW
      -- machine counters HIGH
      -- machine event configuration
      when csr_mhpmcounter3_c | csr_mhpmcounter4_c | csr_mhpmcounter5_c
          | csr_mhpmcounter6_c | csr_mhpmcounter7_c | csr_mhpmcounter8_c
          | csr_mhpmcounter9_c | csr_mhpmcounter10_c | csr_mhpmcounter11_c
          | csr_mhpmcounter12_c | csr_mhpmcounter13_c | csr_mhpmcounter14_c
          | csr_mhpmcounter15_c | csr_mhpmcounter3h_c | csr_mhpmcounter4h_c
          | csr_mhpmcounter5h_c | csr_mhpmcounter6h_c | csr_mhpmcounter7h_c
          | csr_mhpmcounter8h_c | csr_mhpmcounter9h_c | csr_mhpmcounter10h_c
          | csr_mhpmcounter11h_c | csr_mhpmcounter12h_c | csr_mhpmcounter13h_c
          | csr_mhpmcounter14h_c | csr_mhpmcounter15h_c | csr_mhpmevent3_c
          | csr_mhpmevent4_c | csr_mhpmevent5_c | csr_mhpmevent6_c
          | csr_mhpmevent7_c | csr_mhpmevent8_c | csr_mhpmevent9_c
          | csr_mhpmevent10_c | csr_mhpmevent11_c | csr_mhpmevent12_c
          | csr_mhpmevent13_c | csr_mhpmevent14_c | csr_mhpmevent15_c =>
        -- available if Zihpm implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zihpm);

      -- counter and timer CSRs --
      when csr_cycle_c | csr_mcycle_c | csr_instret_c | csr_minstret_c
          | csr_cycleh_c | csr_mcycleh_c | csr_instreth_c | csr_minstreth_c =>
        -- available if Zicntr implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zicntr);

      -- debug-mode CSRs --
      when csr_dcsr_c | csr_dpc_c | csr_dscratch0_c =>
        -- available if debug-mode implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Sdext);

      -- trigger module CSRs --
      when csr_tselect_c | csr_tdata1_c | csr_tdata2_c | csr_tinfo_c =>
        -- available if trigger module implemented
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Sdtrig);

      -- undefined / not implemented --
      when others =>
        csr_valid(2) <= '0'; -- invalid access

    end case;

    -- ------------------------------------------------------------
    -- R/W capabilities
    -- ------------------------------------------------------------
    -- CSR is read-only
    -- will always write to CSR
    -- will always write to CSR
    -- clear/set instructions: write to CSR only if rs1/imm5 is NOT zero
    if (csr_addr_v(11 downto 10) = "11")
        and ((exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) =
              funct3_csrrw_c)
             or (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) =
                 funct3_csrrwi_c)
             or (exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c)
                 /= "00000")) then
      csr_valid(1) <= '0'; -- invalid access
    else
      csr_valid(1) <= '1'; -- access granted
    end if;

    -- ------------------------------------------------------------
    -- Privilege level
    -- ------------------------------------------------------------
    -- debug-mode-only CSR?
    -- debug-mode implemented and not running?
    if (csr_addr_v(11 downto 4) = csr_dcsr_c(11 downto 4)) and RISCV_ISA_Sdext
        and (debug_ctrl.run = '0') then
      csr_valid(0) <= '0'; -- invalid access
    -- any user-mode counters available and in user-mode?
    -- user-mode counter access
    -- illegal access to cycle
    -- illegal access to instret
    elsif RISCV_ISA_Zicntr and RISCV_ISA_U and (csr.prv_level_eff = '0')
        and (csr_addr_v(11 downto 8) = csr_cycle_c(11 downto 8))
        and (((csr_addr_v(1 downto 0) = csr_cycle_c(1 downto 0))
              and (csr.mcounteren_cy = '0'))
             or ((csr_addr_v(1 downto 0) = csr_instret_c(1 downto 0))
                 and (csr.mcounteren_ir = '0'))) then
      csr_valid(0) <= '0'; -- invalid access
    -- invalid privilege level
    elsif (csr_addr_v(9 downto 8) /= "00") and (csr.prv_level_eff = '0') then
      csr_valid(0) <= '0'; -- invalid access
    else
      csr_valid(0) <= '1'; -- access granted
    end if;

  end process csr_check;


  -- Illegal Instruction Check -------------------------------------------------
  -- ---------------------------------------------------------------------------
  illegal_check: process(exe_engine, csr, csr_valid, debug_ctrl)
  begin
    illegal_cmd <= '1'; -- default: illegal
    -- check entire opcode
    case exe_engine.ir(instr_opcode_msb_c downto instr_opcode_lsb_c) is

      when opcode_lui_c | opcode_auipc_c | opcode_jal_c => -- U-instruction type
        illegal_cmd <= '0'; -- all encodings are valid

      when opcode_jalr_c => -- unconditional jump-and-link
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = "000")
            then
          illegal_cmd <= '0';
        end if;

      when opcode_branch_c => -- conditional branch
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c+1) /=
            "01") or RISCV_ISA_Zibi then
          illegal_cmd <= '0';
        end if;

      when opcode_load_c => -- memory load
        case exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_lb_c | funct3_lh_c | funct3_lw_c | funct3_lbu_c
              | funct3_lhu_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      when opcode_store_c => -- memory store
        case exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_sb_c | funct3_sh_c | funct3_sw_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      when opcode_amo_c => -- atomic memory operation
        -- word-quantity only
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = "010")
            then
          case exe_engine.ir(instr_funct5_msb_c downto instr_funct5_lsb_c) is
            when "00001" | "00000" | "00100" | "01100" | "01000" | "10000"
                | "10100" | "11000" | "11100" => illegal_cmd <=
                not bool_to_ulogic_f(RISCV_ISA_Zaamo);
            when "00010" | "00011" => illegal_cmd <=
                not bool_to_ulogic_f(RISCV_ISA_Zalrsc);
            when others => illegal_cmd <= '1';
          end case;
        end if;

      -- ALU[I] / FPU / custom operations
      when opcode_alu_c | opcode_alui_c | opcode_fpu_c | opcode_cust0_c
          | opcode_cust1_c =>
        -- [NOTE] valid if not terminated/invalidated by the "instruction
        -- execution monitor"
        illegal_cmd <= '0';

      when opcode_fence_c => -- memory ordering
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c+1) =
            funct3_fence_c(2 downto 1)) then
          illegal_cmd <= '0';
        end if;

      -- system instruction / may-be-operations / CSR access
      when opcode_system_c =>
        -- system environment
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) =
            funct3_env_c) then
          if (exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c) = "00000")
              and (exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c) =
                   "00000") then
            case exe_engine.ir(instr_imm12_msb_c downto instr_imm12_lsb_c) is
              -- ecall is always allowed
              when funct12_ecall_c  => illegal_cmd <= '0';
              -- ebreak is always allowed
              when funct12_ebreak_c => illegal_cmd <= '0';
              -- mret allowed in (real/non-debug) M-mode only
              when funct12_mret_c   => illegal_cmd <= (not csr.prv_level)
                  or debug_ctrl.run;
              -- dret allowed in debug mode only
              when funct12_dret_c   => illegal_cmd <= not debug_ctrl.run;
              -- wfi allowed in M-mode or if TW is zero
              when funct12_wfi_c    => illegal_cmd <= (not csr.prv_level)
                  and csr.mstatus_tw;
              when others           => illegal_cmd <= '1'; -- undefined
            end case;
          end if;
        elsif (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) =
               funct3_zimop_c) then
          illegal_cmd <= not bool_to_ulogic_f(RISCV_ISA_Zimop);
        elsif (csr_valid = "111") then -- valid CSR operation
          illegal_cmd <= '0';
        end if;

      when others => -- undefined/unimplemented/illegal opcode
        illegal_cmd <= '1';

    end case;
  end process illegal_check;


  -- Illegal Operation Check ---------------------------------------------------
  -- ---------------------------------------------------------------------------
  -- check in execution states only
  -- instruction timeout or illegal instruction
  trap_ctrl.instr_il <= '1'
      when ((exe_fctv_state = EX_EXECUTE) or (exe_fctv_state = EX_ALU_WAIT))
      and ((monitor_exc = '1') or (illegal_cmd = '1')) else '0';


  -- ***************************************************************************
  -- Trap Controller
  -- ***************************************************************************

  -- Trap Buffer ---------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  trap_buffer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap_ctrl.irq_pnd <= (others => '0');
      trap_ctrl.irq_buf <= (others => '0');
      trap_ctrl.exc_buf <= (others => '0');
    elsif rising_edge(clk_i) then

      -- Interrupt-Pending Buffer ---------------------------------------------
      -- Once triggered the interrupt line should stay active until explicitly
      -- cleared by a mechanism specific to the interrupt-causing source.
      -- ----------------------------------------------------------------------
      -- RISC-V machine interrupts
      trap_ctrl.irq_pnd(irq_mei_irq_c downto irq_msi_irq_c) <= irq_machine_i;
      -- NEORV32-specific fast interrupts
      trap_ctrl.irq_pnd(irq_firq_15_c downto irq_firq_0_c)  <=
          custom_fast_irq(15 downto 0);
      -- unused debug-mode entry
      trap_ctrl.irq_pnd(irq_db_halt_c)                      <= '0';

      -- Interrupt Buffer -----------------------------------------------------
      -- Masking of interrupt request lines. Additionally, this buffer ensures
      -- that an active interrupt request line stays active (even when
      -- disabled via MIE) if the trap environment is already starting.
      -- ----------------------------------------------------------------------

      -- RISC-V machine interrupts --
      trap_ctrl.irq_buf(irq_msi_irq_c) <=
          (trap_ctrl.irq_pnd(irq_msi_irq_c) and csr.mie_msi)
          or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_msi_irq_c));
      trap_ctrl.irq_buf(irq_mei_irq_c) <=
          (trap_ctrl.irq_pnd(irq_mei_irq_c) and csr.mie_mei)
          or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_mei_irq_c));
      trap_ctrl.irq_buf(irq_mti_irq_c) <=
          (trap_ctrl.irq_pnd(irq_mti_irq_c) and csr.mie_mti)
          or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_mti_irq_c));

      -- NEORV32-specific fast interrupts --
      for i in 0 to 15 loop
        trap_ctrl.irq_buf(irq_firq_0_c+i) <=
            (trap_ctrl.irq_pnd(irq_firq_0_c+i) and csr.mie_firq(i))
            or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_firq_0_c+i));
      end loop;

      -- debug-mode entry (external halt request) --
      trap_ctrl.irq_buf(irq_db_halt_c) <= debug_ctrl.trig_halt
          or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_db_halt_c));

      -- Exception Buffer -----------------------------------------------------
      -- All requests stay pending until the trap environment is started. Only
      -- the highest-priority exception will kick in; others are discarded.
      -- ----------------------------------------------------------------------
      -- instruction access error
      trap_ctrl.exc_buf(exc_iaccess_c)  <=
          (trap_ctrl.exc_buf(exc_iaccess_c) or trap_ctrl.instr_be)
          and (not trap_ctrl.env_enter);
      -- illegal instruction
      trap_ctrl.exc_buf(exc_illegal_c)  <=
          (trap_ctrl.exc_buf(exc_illegal_c) or trap_ctrl.instr_il)
          and (not trap_ctrl.env_enter);
      -- instruction misaligned
      trap_ctrl.exc_buf(exc_ialign_c)   <=
          (trap_ctrl.exc_buf(exc_ialign_c) or trap_ctrl.instr_ma)
          and (not trap_ctrl.env_enter);
      -- environment call
      trap_ctrl.exc_buf(exc_ecall_c)    <=
          (trap_ctrl.exc_buf(exc_ecall_c) or trap_ctrl.ecall)
          and (not trap_ctrl.env_enter);
      -- environment break
      trap_ctrl.exc_buf(exc_ebreak_c)   <=
          (trap_ctrl.exc_buf(exc_ebreak_c) or ebreak_trig)
          and (not trap_ctrl.env_enter);
      -- store address misaligned
      trap_ctrl.exc_buf(exc_salign_c)   <=
          (trap_ctrl.exc_buf(exc_salign_c) or lsu_err_i(2))
          and (not trap_ctrl.env_enter);
      -- load address misaligned
      trap_ctrl.exc_buf(exc_lalign_c)   <=
          (trap_ctrl.exc_buf(exc_lalign_c) or lsu_err_i(0))
          and (not trap_ctrl.env_enter);
      -- store access error
      trap_ctrl.exc_buf(exc_saccess_c)  <=
          (trap_ctrl.exc_buf(exc_saccess_c) or lsu_err_i(3))
          and (not trap_ctrl.env_enter);
      -- load access error
      trap_ctrl.exc_buf(exc_laccess_c)  <=
          (trap_ctrl.exc_buf(exc_laccess_c) or lsu_err_i(1))
          and (not trap_ctrl.env_enter);
      -- debug-entry: break
      trap_ctrl.exc_buf(exc_db_break_c) <=
          (trap_ctrl.exc_buf(exc_db_break_c) or debug_ctrl.trig_break)
          and (not trap_ctrl.env_enter);
      -- debug-entry: trigger
      trap_ctrl.exc_buf(exc_db_trig_c)  <=
          (trap_ctrl.exc_buf(exc_db_trig_c) or debug_ctrl.trig_hw)
          and (not trap_ctrl.env_enter);
      -- debug-entry: single step
      trap_ctrl.exc_buf(exc_db_step_c)  <=
          (trap_ctrl.exc_buf(exc_db_step_c) or debug_ctrl.trig_step)
          and (not trap_ctrl.env_enter);

    end if;
  end process trap_buffer;

  -- environment break exception trigger --
  -- M-mode trap when in M-mode
  -- M-mode trap when in U-mode
  ebreak_trig <= (trap_ctrl.ebreak and ( csr.prv_level)
                  and (not csr.dcsr_ebreakm) and (not debug_ctrl.run))
      or (trap_ctrl.ebreak and (not csr.prv_level) and (not csr.dcsr_ebreaku)
          and (not debug_ctrl.run));


  -- Trap Priority Logic -------------------------------------------------------
  -- ---------------------------------------------------------------------------
  trap_priority: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap_ctrl.cause <= (others => '0');
    elsif rising_edge(clk_i) then
      trap_ctrl.cause <= (others => '0'); -- default
      -- standard RISC-V synchronous exceptions --
      -- instruction access fault
      if    (trap_ctrl.exc_buf(exc_iaccess_c)  = '1') then
          trap_ctrl.cause <= trap_iaf_c;
      -- illegal instruction
      elsif (trap_ctrl.exc_buf(exc_illegal_c)  = '1') then
          trap_ctrl.cause <= trap_iil_c;
      -- instruction address misaligned
      elsif (trap_ctrl.exc_buf(exc_ialign_c)   = '1') then
          trap_ctrl.cause <= trap_ima_c;
      -- environment call
      elsif (trap_ctrl.exc_buf(exc_ecall_c)    = '1') then trap_ctrl.cause <=
          trap_env_c(6 downto 2) & replicate_f(csr.prv_level, 2);
      -- environment breakpoint
      elsif (trap_ctrl.exc_buf(exc_ebreak_c)   = '1') then
          trap_ctrl.cause <= trap_brk_c;
      -- store address misaligned
      elsif (trap_ctrl.exc_buf(exc_salign_c)   = '1') then
          trap_ctrl.cause <= trap_sma_c;
      -- load address misaligned
      elsif (trap_ctrl.exc_buf(exc_lalign_c)   = '1') then
          trap_ctrl.cause <= trap_lma_c;
      -- store access fault
      elsif (trap_ctrl.exc_buf(exc_saccess_c)  = '1') then
          trap_ctrl.cause <= trap_saf_c;
      -- load access fault
      elsif (trap_ctrl.exc_buf(exc_laccess_c)  = '1') then
          trap_ctrl.cause <= trap_laf_c;
      -- standard RISC-V debug mode synchronous exceptions and interrupts --
      -- external halt request
      elsif (trap_ctrl.irq_buf(irq_db_halt_c)  = '1') then
          trap_ctrl.cause <= trap_db_halt_c;
      -- hardware trigger
      elsif (trap_ctrl.exc_buf(exc_db_trig_c)  = '1') then
          trap_ctrl.cause <= trap_db_trig_c;
      -- breakpoint
      elsif (trap_ctrl.exc_buf(exc_db_break_c) = '1') then trap_ctrl.cause <=
          trap_db_break_c;
      -- single stepping
      elsif (trap_ctrl.exc_buf(exc_db_step_c)  = '1') then
          trap_ctrl.cause <= trap_db_step_c;
      -- NEORV32-specific fast interrupts --
      -- fast interrupt channel 0
      elsif (trap_ctrl.irq_buf(irq_firq_0_c)   = '1') then
          trap_ctrl.cause <= trap_firq0_c;
      -- fast interrupt channel 1
      elsif (trap_ctrl.irq_buf(irq_firq_1_c)   = '1') then
          trap_ctrl.cause <= trap_firq1_c;
      -- fast interrupt channel 2
      elsif (trap_ctrl.irq_buf(irq_firq_2_c)   = '1') then
          trap_ctrl.cause <= trap_firq2_c;
      -- fast interrupt channel 3
      elsif (trap_ctrl.irq_buf(irq_firq_3_c)   = '1') then
          trap_ctrl.cause <= trap_firq3_c;
      -- fast interrupt channel 4
      elsif (trap_ctrl.irq_buf(irq_firq_4_c)   = '1') then
          trap_ctrl.cause <= trap_firq4_c;
      -- fast interrupt channel 5
      elsif (trap_ctrl.irq_buf(irq_firq_5_c)   = '1') then
          trap_ctrl.cause <= trap_firq5_c;
      -- fast interrupt channel 6
      elsif (trap_ctrl.irq_buf(irq_firq_6_c)   = '1') then
          trap_ctrl.cause <= trap_firq6_c;
      -- fast interrupt channel 7
      elsif (trap_ctrl.irq_buf(irq_firq_7_c)   = '1') then
          trap_ctrl.cause <= trap_firq7_c;
      -- fast interrupt channel 8
      elsif (trap_ctrl.irq_buf(irq_firq_8_c)   = '1') then
          trap_ctrl.cause <= trap_firq8_c;
      -- fast interrupt channel 9
      elsif (trap_ctrl.irq_buf(irq_firq_9_c)   = '1') then
          trap_ctrl.cause <= trap_firq9_c;
      -- fast interrupt channel 10
      elsif (trap_ctrl.irq_buf(irq_firq_10_c)  = '1') then
          trap_ctrl.cause <= trap_firq10_c;
      -- fast interrupt channel 11
      elsif (trap_ctrl.irq_buf(irq_firq_11_c)  = '1') then
          trap_ctrl.cause <= trap_firq11_c;
      -- fast interrupt channel 12
      elsif (trap_ctrl.irq_buf(irq_firq_12_c)  = '1') then
          trap_ctrl.cause <= trap_firq12_c;
      -- fast interrupt channel 13
      elsif (trap_ctrl.irq_buf(irq_firq_13_c)  = '1') then
          trap_ctrl.cause <= trap_firq13_c;
      -- fast interrupt channel 14
      elsif (trap_ctrl.irq_buf(irq_firq_14_c)  = '1') then
          trap_ctrl.cause <= trap_firq14_c;
      -- fast interrupt channel 15
      elsif (trap_ctrl.irq_buf(irq_firq_15_c)  = '1') then
          trap_ctrl.cause <= trap_firq15_c;
      -- standard RISC-V interrupts --
      -- machine external interrupt (MEI)
      elsif (trap_ctrl.irq_buf(irq_mei_irq_c)  = '1') then
          trap_ctrl.cause <= trap_mei_c;
      -- machine software interrupt (MSI)
      elsif (trap_ctrl.irq_buf(irq_msi_irq_c)  = '1') then
          trap_ctrl.cause <= trap_msi_c;
      -- machine timer interrupt (MTI)
      elsif (trap_ctrl.irq_buf(irq_mti_irq_c)  = '1') then
          trap_ctrl.cause <= trap_mti_c;
      end if;
    end if;
  end process trap_priority;

  -- exception program counter: async. interrupt or sync. exception? --
  trap_ctrl.pc <= exe_engine.pc2
      when (trap_ctrl.cause(trap_ctrl.cause'left) = '1') else exe_engine.pc;


  -- Trap Controller -----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  trap_controller: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap_ctrl.env_pending <= '0';
    elsif rising_edge(clk_i) then
      -- trap triggered
      if (trap_ctrl.env_pending = '0')
          and ((trap_ctrl.exc_fire = '1')
               or (or_reduce_f(trap_ctrl.irq_fire) = '1')) then
        trap_ctrl.env_pending <= '1';
      -- start of trap environment acknowledged by execute engine
      elsif (trap_ctrl.env_pending = '1') and (trap_ctrl.env_enter = '1') then
        trap_ctrl.env_pending <= '0';
      end if;
    end if;
  end process trap_controller;

  -- any exception? --
  -- sync. exceptions cannot be masked
  trap_ctrl.exc_fire <= '1'
      when ((or_reduce_f(trap_ctrl.exc_buf) = '1') or ill_state = '1') else '0';

  -- any system interrupt? --
  -- trigger system IRQ only in EX_EXECUTE state or in sleep mode
  -- pending system IRQ
  -- IRQ only when in M-mode and MIE=1 OR when in U-mode
  -- no system IRQs when in debug-mode / during single-stepping
  trap_ctrl.irq_fire(0) <= '1'
      when ((exe_fctv_state = EX_EXECUTE) or (exe_fctv_state = EX_SLEEP))
      and (or_reduce_f(trap_ctrl.irq_buf(irq_firq_15_c downto irq_msi_irq_c)) =
           '1') and ((csr.mstatus_mie = '1') or (csr.prv_level = priv_mode_u_c))
      and (debug_ctrl.run = '0') and (csr.dcsr_step = '0') else '0';

  -- debug-entry halt interrupt? --
  -- allow halt also after "reset" (#879)
  trap_ctrl.irq_fire(1) <= trap_ctrl.irq_buf(irq_db_halt_c)
      when (exe_fctv_state = EX_EXECUTE) or (exe_fctv_state = EX_SLEEP)
      or (exe_fctv_state = EX_BRANCHED) else '0';


  -- ***************************************************************************
  -- Control and Status Registers (CSRs)
  -- ***************************************************************************

  -- CSR Address Register ------------------------------------------------------
  -- ---------------------------------------------------------------------------
  csr_addr_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.addr <= (others => '0');
    elsif rising_edge(clk_i) then
      -- update only for actual CSR operations to reduce switching activity on
      -- csr.addr net
      if (opcode = opcode_system_c) then
        csr.addr <= exe_engine.ir(instr_imm12_msb_c downto instr_imm12_lsb_c);
      end if;
    end if;
  end process csr_addr_reg;


  -- CSR Write-Data ALU --------------------------------------------------------
  -- ---------------------------------------------------------------------------
  csr.operand <= rf_rs1_i when (exe_engine.ir(instr_funct3_msb_c) = '0')
      else (x"000000" & "000" & exe_engine.ir(19 downto 15));

  -- tiny ALU to compute CSR write data --
  -- set
  -- clear
  -- write
  with exe_engine.ir(instr_funct3_msb_c-1 downto instr_funct3_lsb_c) select
      csr.wdata <= csr.rdata or csr.operand when "10", csr.rdata
      and (not csr.operand) when "11", csr.operand when others;


  -- CSR Write Access ----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  csr_write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.we            <= '0';
      csr.prv_level     <= priv_mode_m_c;
      csr.mstatus_mie   <= '0';
      csr.mstatus_mpie  <= '0';
      csr.mstatus_mpp   <= '0';
      csr.mstatus_mprv  <= '0';
      csr.mstatus_tw    <= '0';
      csr.mie_msi       <= '0';
      csr.mie_mei       <= '0';
      csr.mie_mti       <= '0';
      csr.mie_firq      <= (others => '0');
      csr.mtvec         <= (others => '0');
      csr.mscratch      <= (others => '0');
      csr.mepc          <= (others => '0');
      csr.mcause        <= (others => '0');
      csr.mtval         <= (others => '0');
      csr.mtinst        <= (others => '0');
      csr.mcounteren_cy <= '0';
      csr.mcounteren_ir <= '0';
      csr.dcsr_ebreakm  <= '0';
      csr.dcsr_ebreaku  <= '0';
      csr.dcsr_step     <= '0';
      csr.dcsr_prv      <= '0';
      csr.dcsr_cause    <= (others => '0');
      csr.dpc           <= (others => '0');
      csr.dscratch0     <= (others => '0');
    elsif rising_edge(clk_i) then

      -- ***********************************************************************
      -- Software CSR access
      -- ***********************************************************************
      -- write if no instruction exception
      csr.we <= csr.we_nxt
          and (not or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                                 exc_iaccess_c)));
      if (csr.we = '1') then
        case csr.addr is

          -- machine status register --
          when csr_mstatus_c =>
            csr.mstatus_mie  <= csr.wdata(3);
            csr.mstatus_mpie <= csr.wdata(7);
            if RISCV_ISA_U then
              -- everything /= U will fall back to M
              csr.mstatus_mpp  <= csr.wdata(11) or csr.wdata(12);
              csr.mstatus_mprv <= csr.wdata(17);
              csr.mstatus_tw   <= csr.wdata(21);
            end if;

          -- machine interrupt enable register --
          when csr_mie_c =>
            csr.mie_msi  <= csr.wdata(3);
            csr.mie_mti  <= csr.wdata(7);
            csr.mie_mei  <= csr.wdata(11);
            csr.mie_firq <= csr.wdata(31 downto 16);

          -- machine trap-handler base address --
          when csr_mtvec_c =>
            -- base + mode (vectored/direct)
            csr.mtvec <= csr.wdata(XLEN-1 downto 2) & '0' & csr.wdata(0);

          -- machine counter access enable --
          when csr_mcounteren_c =>
            if RISCV_ISA_U and RISCV_ISA_Zicntr then
              csr.mcounteren_cy <= csr.wdata(0);
              csr.mcounteren_ir <= csr.wdata(2);
            end if;

          -- machine scratch register --
          when csr_mscratch_c =>
            csr.mscratch <= csr.wdata;

          -- machine exception program counter --
          when csr_mepc_c =>
            csr.mepc <= csr.wdata(XLEN-1 downto 1) & '0';
            -- RISC-V priv. spec.: MEPC[1] is masked when IALIGN = 32
            if not RISCV_ISA_C then
              csr.mepc(1) <= '0';
            end if;

          -- debug mode control and status register --
          when csr_dcsr_c =>
            if (csr.addr = csr_dcsr_c) and RISCV_ISA_Sdext then
              csr.dcsr_step    <= csr.wdata(2);
              csr.dcsr_ebreakm <= csr.wdata(15);
              if RISCV_ISA_U then
                -- everything /= U will fall back to M
                csr.dcsr_prv     <= csr.wdata(1) or csr.wdata(0);
                csr.dcsr_ebreaku <= csr.wdata(12);
              end if;
            end if;

          -- debug mode program counter --
          when csr_dpc_c =>
            if RISCV_ISA_Sdext then
              csr.dpc <= csr.wdata(XLEN-1 downto 1) & '0';
              -- RISC-V priv. spec.: DPC[1] is masked when IALIGN = 32
              if not RISCV_ISA_C then
                csr.dpc(1) <= '0';
              end if;
            end if;

          -- debug mode scratch register 0 --
          when csr_dscratch0_c =>
            if (csr.addr = csr_dscratch0_c) and RISCV_ISA_Sdext then
              csr.dscratch0 <= csr.wdata;
            end if;

          -- undefined or implemented somewhere else --
          when others => NULL;

        end case;

      -- ***********************************************************************
      -- Hardware CSR access: TRAP ENTER
      -- ***********************************************************************
      elsif (trap_ctrl.env_enter = '1') then

        -- trap to machine-mode - no CSR update when in debug-mode! --
        if (not RISCV_ISA_Sdext)
            or ((trap_ctrl.cause(5) = '0') and (debug_ctrl.run = '0')) then
          -- trap type & identifier
          csr.mcause <= trap_ctrl.cause(trap_ctrl.cause'left)
              & trap_ctrl.cause(4 downto 0);
          csr.mepc   <= trap_ctrl.pc(XLEN-1 downto 1) & '0'; -- trap PC
          -- trap value (load/store trap address only, permitted by RISC-V priv.
          -- spec.) --
          -- load/store misaligned/access fault
          if (trap_ctrl.cause(6) = '0') and (trap_ctrl.cause(2) = '1') then
            csr.mtval <= lsu_mar_i; -- faulting data access address
          else -- everything else including all interrupts
            csr.mtval <= (others => '0');
          end if;
          -- trap instruction --
          csr.mtinst <= exe_engine.ir;
          if (exe_engine.ci = '1') and RISCV_ISA_C then
            -- RISC-V priv. spec: clear bit 1 if compressed instruction
            csr.mtinst(1) <= '0';
          end if;
          -- update privilege level and interrupt-enable stack --
          csr.prv_level    <= priv_mode_m_c; -- execute trap in machine mode
          csr.mstatus_mie  <= '0'; -- disable interrupts
          csr.mstatus_mpie <= csr.mstatus_mie; -- backup previous mie state
          csr.mstatus_mpp  <= csr.prv_level; -- backup previous privilege level
        end if;

        -- trap to debug-mode - no CSR update when already in debug-mode! --
        if RISCV_ISA_Sdext and (trap_ctrl.cause(5) = '1')
            and (debug_ctrl.run = '0') then
          csr.dcsr_cause <= trap_ctrl.cause(2 downto 0); -- trap cause
          -- current privilege level when debug mode was entered
          csr.dcsr_prv   <= csr.prv_level;
          csr.dpc        <= trap_ctrl.pc(XLEN-1 downto 1) & '0'; -- trap PC
        end if;

      -- ***********************************************************************
      -- Hardware CSR access: TRAP EXIT
      -- ***********************************************************************
      elsif (trap_ctrl.env_exit = '1') then

        -- return from debug-mode --
        if RISCV_ISA_Sdext and (debug_ctrl.run = '1') then
          if RISCV_ISA_U then
            csr.prv_level <= csr.dcsr_prv;
            if (csr.dcsr_prv /= priv_mode_m_c) then
              -- clear if return to priv. level less than M
              csr.mstatus_mprv <= '0';
            end if;
          end if;
        -- return from machine-mode trap --
        else
          if RISCV_ISA_U then
            -- restore previous privilege level
            csr.prv_level   <= csr.mstatus_mpp;
            -- set to least-privileged level that is supported
            csr.mstatus_mpp <= priv_mode_u_c;
            if (csr.mstatus_mpp /= priv_mode_m_c) then
              -- clear if return to priv. level less than M
              csr.mstatus_mprv <= '0';
            end if;
          end if;
          -- restore machine-mode IRQ enable flag
          csr.mstatus_mie  <= csr.mstatus_mpie;
          csr.mstatus_mpie <= '1';
        end if;

      end if;

      -- ***********************************************************************
      -- Override: terminate unavailable registers and bits
      -- ***********************************************************************

      -- no base counters --
      if not RISCV_ISA_Zicntr then
        csr.mcounteren_cy <= '0';
        csr.mcounteren_ir <= '0';
      end if;

      -- no user mode --
      if not RISCV_ISA_U then
        csr.prv_level     <= priv_mode_m_c;
        csr.mstatus_mpp   <= priv_mode_m_c;
        csr.mstatus_mprv  <= '0';
        csr.mstatus_tw    <= '0';
        csr.dcsr_ebreaku  <= '0';
        csr.dcsr_prv      <= '0';
        csr.mcounteren_cy <= '0';
        csr.mcounteren_ir <= '0';
      end if;

      -- no debug mode --
      if not RISCV_ISA_Sdext then
        csr.dcsr_ebreakm <= '0';
        csr.dcsr_step    <= '0';
        csr.dcsr_ebreaku <= '0';
        csr.dcsr_prv     <= priv_mode_m_c;
        csr.dcsr_cause   <= (others => '0');
        csr.dpc          <= (others => '0');
        csr.dscratch0    <= (others => '0');
      end if;

    end if;
  end process csr_write_access;

  -- effective privilege level is MACHINE when in debug mode --
  csr.prv_level_eff <= priv_mode_m_c when (debug_ctrl.run = '1')
      else csr.prv_level;


  -- CSR Read Access -----------------------------------------------------------
  -- ---------------------------------------------------------------------------
  csr_read_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.re    <= '0';
      csr.rdata <= (others => '0');
    elsif rising_edge(clk_i) then
      -- read if no instruction exception
      csr.re    <= csr.re_nxt
          and (not or_reduce_f(trap_ctrl.exc_buf(exc_ialign_c downto
                                                 exc_iaccess_c)));
      -- default; output all-zero if there is no explicit CSR read operation
      csr.rdata <= (others => '0');
      if (csr.re = '1') then
        case csr.addr is

          -- -------------------------------------------------------------------
          -- machine trap setup
          -- -------------------------------------------------------------------
          when csr_mstatus_c => -- machine status register, low word
            csr.rdata(3)  <= csr.mstatus_mie;
            csr.rdata(7)  <= csr.mstatus_mpie;
            csr.rdata(11) <= csr.mstatus_mpp;
            csr.rdata(12) <= csr.mstatus_mpp;
            csr.rdata(17) <= csr.mstatus_mprv;
            csr.rdata(21) <= csr.mstatus_tw and bool_to_ulogic_f(RISCV_ISA_U);

          when csr_misa_c => -- ISA and extensions
            csr.rdata(0)  <= bool_to_ulogic_f(RISCV_ISA_A);
            csr.rdata(1)  <= bool_to_ulogic_f(RISCV_ISA_B);
            csr.rdata(2)  <= bool_to_ulogic_f(RISCV_ISA_C);
            csr.rdata(4)  <= bool_to_ulogic_f(RISCV_ISA_E);
            csr.rdata(8)  <= bool_to_ulogic_f(not RISCV_ISA_E);
            csr.rdata(12) <= bool_to_ulogic_f(RISCV_ISA_M);
            csr.rdata(20) <= bool_to_ulogic_f(RISCV_ISA_U);
            -- X CPU extension (non-standard / NEORV32-specific)
            csr.rdata(23) <= '1';
            csr.rdata(31 downto 30) <= "01"; -- MXL = 32

          when csr_mie_c => -- machine interrupt-enable register
            csr.rdata(3)  <= csr.mie_msi;
            csr.rdata(7)  <= csr.mie_mti;
            csr.rdata(11) <= csr.mie_mei;
            csr.rdata(31 downto 16) <= csr.mie_firq;

          when csr_mtvec_c => -- machine trap-handler base address
            csr.rdata <= csr.mtvec;

          when csr_mcounteren_c => -- machine counter enable register
            if RISCV_ISA_U and RISCV_ISA_Zicntr then
              csr.rdata(0) <= csr.mcounteren_cy;
              csr.rdata(2) <= csr.mcounteren_ir;
            end if;

          -- -------------------------------------------------------------------
          -- machine trap handling
          -- -------------------------------------------------------------------
          when csr_mscratch_c => -- machine scratch register
            csr.rdata <= csr.mscratch;

          when csr_mepc_c => -- machine exception program counter
            csr.rdata <= csr.mepc(XLEN-1 downto 1) & '0';

          when csr_mcause_c => -- machine trap cause
            csr.rdata(31)         <= csr.mcause(5);
            csr.rdata(4 downto 0) <= csr.mcause(4 downto 0);

          when csr_mtval_c => -- machine trap value
            csr.rdata <= csr.mtval;

          when csr_mip_c => -- machine interrupt pending
            csr.rdata(3)            <= trap_ctrl.irq_pnd(irq_msi_irq_c);
            csr.rdata(7)            <= trap_ctrl.irq_pnd(irq_mti_irq_c);
            csr.rdata(11)           <= trap_ctrl.irq_pnd(irq_mei_irq_c);
            csr.rdata(31 downto 16) <=
                trap_ctrl.irq_pnd(irq_firq_15_c downto irq_firq_0_c);

          when csr_mtinst_c => -- machine trap instruction
            csr.rdata <= csr.mtinst;

          -- -------------------------------------------------------------------
          -- machine information
          -- -------------------------------------------------------------------
          -- architecture ID - official RISC-V open-source arch ID
          when csr_marchid_c => csr.rdata(4 downto 0) <= "10011";
          -- implementation ID -- NEORV32 hardware version
          when csr_mimpid_c  => csr.rdata <= hw_version_c;
          -- hardware thread ID
          when csr_mhartid_c => csr.rdata(9 downto 0) <=
              std_ulogic_vector(to_unsigned(HART_ID, 10));

          -- -------------------------------------------------------------------
          -- debug-mode
          -- -------------------------------------------------------------------
          -- debug mode control and status
          when csr_dcsr_c      => if RISCV_ISA_Sdext then csr.rdata <=
              csr.dcsr_rd; end if;
          -- debug mode program counter
          when csr_dpc_c       => if RISCV_ISA_Sdext then csr.rdata <=
              csr.dpc; end if;
          -- debug mode scratch register 0
          when csr_dscratch0_c => if RISCV_ISA_Sdext then csr.rdata <=
              csr.dscratch0; end if;

          -- -------------------------------------------------------------------
          -- NEORV32-specific
          -- -------------------------------------------------------------------
          when csr_mxcsr_c => -- machine control and status register
            csr.rdata(25 downto 0) <= (others => '0');            -- reserved
            -- execution trace generator
            csr.rdata(26) <= bool_to_ulogic_f(CPU_TRACE_EN);
            -- constant-time branches
            csr.rdata(27) <= bool_to_ulogic_f(CPU_CONSTT_BR_EN);
            -- full hardware reset of register file
            csr.rdata(28) <= bool_to_ulogic_f(CPU_RF_HW_RST_EN);
            -- DSP-based multiplication (M extensions only)
            csr.rdata(29) <= bool_to_ulogic_f(CPU_FAST_MUL_EN);
            -- parallel logic for shifts (barrel shifters)
            csr.rdata(30) <= bool_to_ulogic_f(CPU_FAST_SHIFT_EN);
            -- is this a simulation?
            csr.rdata(31) <= bool_to_ulogic_f(is_simulation_c);

          when csr_mxisa_c => -- machine extended ISA extensions information
            -- Zicsr: CSR access (always enabled)
            csr.rdata(0)  <= '1';
            -- Zifencei: instruction stream sync. (always enabled)
            csr.rdata(1)  <= '1';
            -- Zmmul: mul/div
            csr.rdata(2)  <= bool_to_ulogic_f(RISCV_ISA_Zmmul);
            -- Zxcfu: custom instructions
            csr.rdata(3)  <= bool_to_ulogic_f(RISCV_ISA_Zxcfu);
            -- Zkt: data independent execution latency
            csr.rdata(4)  <= bool_to_ulogic_f(RISCV_ISA_Zkt);
            -- Zfinx: FPU using x registers
            csr.rdata(5)  <= bool_to_ulogic_f(RISCV_ISA_Zfinx);
            -- Zicond: integer conditional operations
            csr.rdata(6)  <= bool_to_ulogic_f(RISCV_ISA_Zicond);
            -- Zicntr: base counters
            csr.rdata(7)  <= bool_to_ulogic_f(RISCV_ISA_Zicntr);
            -- Smpmp: physical memory protection
            csr.rdata(8)  <= bool_to_ulogic_f(RISCV_ISA_Smpmp);
            -- Zihpm: hardware performance monitors
            csr.rdata(9)  <= bool_to_ulogic_f(RISCV_ISA_Zihpm);
            -- Sdext: external debug
            csr.rdata(10) <= bool_to_ulogic_f(RISCV_ISA_Sdext);
            -- Sdtrig: trigger module
            csr.rdata(11) <= bool_to_ulogic_f(RISCV_ISA_Sdtrig);
            -- Zbkx: cryptography crossbar permutation
            csr.rdata(12) <= bool_to_ulogic_f(RISCV_ISA_Zbkx);
            -- Zknd: cryptography NIST AES decryption
            csr.rdata(13) <= bool_to_ulogic_f(RISCV_ISA_Zknd);
            -- Zkne: cryptography NIST AES encryption
            csr.rdata(14) <= bool_to_ulogic_f(RISCV_ISA_Zkne);
            -- Zknh: cryptography NIST hash functions
            csr.rdata(15) <= bool_to_ulogic_f(RISCV_ISA_Zknh);
            -- Zbkb: bit manipulation instructions for cryptography
            csr.rdata(16) <= bool_to_ulogic_f(RISCV_ISA_Zbkb);
            -- Zbkc: carry-less multiplication for cryptography
            csr.rdata(17) <= bool_to_ulogic_f(RISCV_ISA_Zbkc);
            -- Zkn: NIST algorithm suite
            csr.rdata(18) <= bool_to_ulogic_f(RISCV_ISA_Zkn);
            -- Zksh: ShangMi hash functions
            csr.rdata(19) <= bool_to_ulogic_f(RISCV_ISA_Zksh);
            -- Zksed: ShangMi block ciphers
            csr.rdata(20) <= bool_to_ulogic_f(RISCV_ISA_Zksed);
            -- Zks: ShangMi algorithm suite
            csr.rdata(21) <= bool_to_ulogic_f(RISCV_ISA_Zks);
            -- Zba: shifted-add bit-manipulation
            csr.rdata(22) <= bool_to_ulogic_f(RISCV_ISA_Zba);
            -- Zbb: basic bit-manipulation
            csr.rdata(23) <= bool_to_ulogic_f(RISCV_ISA_Zbb);
            -- Zbs: single-bit bit-manipulation
            csr.rdata(24) <= bool_to_ulogic_f(RISCV_ISA_Zbs);
            -- Zaamo: atomic memory operations
            csr.rdata(25) <= bool_to_ulogic_f(RISCV_ISA_Zaamo);
            -- Zalrsc: reservation-set operations
            csr.rdata(26) <= bool_to_ulogic_f(RISCV_ISA_Zalrsc);
            -- Zcb: additional code size reduction instructions
            csr.rdata(27) <= bool_to_ulogic_f(RISCV_ISA_Zcb);
            -- Zca: C without floating-point
            csr.rdata(28) <= bool_to_ulogic_f(RISCV_ISA_C);
            -- Zibi: branch with immediate-comparison
            csr.rdata(29) <= bool_to_ulogic_f(RISCV_ISA_Zibi);
            -- Zimop: may-be-operations
            csr.rdata(30) <= bool_to_ulogic_f(RISCV_ISA_Zimop);
            csr.rdata(31) <= '0';                                -- reserved

          -- -------------------------------------------------------------------
          -- undefined/unavailable or implemented externally
          -- -------------------------------------------------------------------
          when others => -- FPU, CFU, PMP, HPM, base counters, trigger module
            -- return zero if accessing invalid external CSR
            csr.rdata <= xcsr_rdata_i;

        end case;
      end if;
    end if;
  end process csr_read_access;

  -- CSR read data output (to register file mux) --
  csr_rdata_o <= csr.rdata;


  -- ***************************************************************************
  -- CPU Debug Mode
  -- ***************************************************************************

  -- Debug Control -------------------------------------------------------------
  -- ---------------------------------------------------------------------------
  debug_mode_enable:
  if RISCV_ISA_Sdext generate

    debug_control: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        debug_ctrl.run <= '0';
      elsif rising_edge(clk_i) then
        if (debug_ctrl.run = '0') then -- debug mode OFFLINE
          -- waiting for entry event
          if (trap_ctrl.env_enter = '1') and (trap_ctrl.cause(5) = '1') then
            debug_ctrl.run <= '1';
          end if;
        else -- debug mode ONLINE
          if (trap_ctrl.env_exit = '1') then -- waiting for exit event
            debug_ctrl.run <= '0';
          end if;
        end if;
      end if;
    end process debug_control;

    -- debug mode entry triggers --
    -- enter debug-mode by HW trigger module
    debug_ctrl.trig_hw    <= hwtrig_i and (not debug_ctrl.run);
    -- re-enter debug mode
    -- enabled goto-debug-mode in machine mode on "ebreak"
    -- enabled goto-debug-mode in user mode on "ebreak"
    debug_ctrl.trig_break <= trap_ctrl.ebreak
        and (debug_ctrl.run or (( csr.prv_level) and csr.dcsr_ebreakm)
             or ((not csr.prv_level) and csr.dcsr_ebreaku));
    -- external halt request (if not halted already)
    debug_ctrl.trig_halt  <= irq_dbg_i     and (not debug_ctrl.run);
    -- single-step mode
    debug_ctrl.trig_step  <= csr.dcsr_step and (not debug_ctrl.run)
        and cnt_event(cnt_event_ir_c);

  end generate;

  -- Sdext ISA extension not enabled --
  debug_mode_disable:
  if not RISCV_ISA_Sdext generate
    debug_ctrl.run        <= '0';
    debug_ctrl.trig_hw    <= '0';
    debug_ctrl.trig_break <= '0';
    debug_ctrl.trig_halt  <= '0';
    debug_ctrl.trig_step  <= '0';
  end generate;


  -- Debug Control and Status Register (dcsr) - Read-Back ----------------------
  -- ---------------------------------------------------------------------------
  -- xdebugver: external debug support compatible to spec. version 1.0
  csr.dcsr_rd(31 downto 28) <= "0100";
  csr.dcsr_rd(27 downto 16) <= (others => '0'); -- reserved
  -- ebreakm: what happens on ebreak in m-mode? (normal trap OR debug-enter)
  csr.dcsr_rd(15)           <= csr.dcsr_ebreakm;
  csr.dcsr_rd(14)           <= '0'; -- reserved
  csr.dcsr_rd(13)           <= '0'; -- ebreaks: supervisor mode not implemented
  -- ebreaku: what happens on ebreak in u-mode? (normal trap OR debug-enter)
  csr.dcsr_rd(12)           <= csr.dcsr_ebreaku when RISCV_ISA_U else '0';
  -- stepie: interrupts are disabled during single-stepping
  csr.dcsr_rd(11)           <= '0';
  -- stopcount: standard counters and HPMs are stopped when in debug mode
  csr.dcsr_rd(10)           <= '1';
  csr.dcsr_rd(9)            <= '0'; -- stoptime: timers increment as usual
  csr.dcsr_rd(8 downto 6)   <= csr.dcsr_cause; -- debug mode entry cause
  csr.dcsr_rd(5)            <= '0'; -- reserved
  -- mprven: mstatus.mprv is also evaluated in debug mode
  csr.dcsr_rd(4)            <= '1';
  csr.dcsr_rd(3)            <= '0'; -- nmip: no pending non-maskable interrupt
  csr.dcsr_rd(2)            <= csr.dcsr_step; -- step: single-step mode
  -- prv: privilege level when debug mode was entered
  csr.dcsr_rd(1 downto 0)   <= (others => csr.dcsr_prv);


end neorv32_cpu_control_rtl;