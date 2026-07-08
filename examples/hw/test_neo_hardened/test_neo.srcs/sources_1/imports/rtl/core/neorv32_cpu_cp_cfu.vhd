-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: Custom (RISC-V Instructions) Functions Unit (CFU)    --
-- -------------------------------------------------------------------------------- --
-- See the CPU's data sheet for more information. Also take a look at the "software --
-- counterpart" of this CFU example in sw/example/demo_cfu.                         --
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

entity neorv32_cpu_cp_cfu is
  port (
    -- global control --
    clk_i    : in  std_ulogic; -- global clock, rising edge
    rstn_i   : in  std_ulogic; -- global reset, low-active, async
    -- operation trigger --
    start_i  : in  std_ulogic; -- start trigger, single-shot
    -- operands --
    type_i   : in  std_ulogic;                     -- instruction type (0 = R-type, 1 = I-type)
    funct3_i : in  std_ulogic_vector(2 downto 0);  -- "funct3" bit-field from instruction word
    funct7_i : in  std_ulogic_vector(6 downto 0);  -- "funct7" bit-field from instruction word (R-type only)
    imm12_i  : in  std_ulogic_vector(11 downto 0); -- "imm12" bit-field from instruction word (I-type only)
    rs1_i    : in  std_ulogic_vector(31 downto 0); -- rf source 1 via "rs1" bit-field from instruction word
    rs2_i    : in  std_ulogic_vector(31 downto 0); -- rf source 2 via "rs2" bit-field from instruction word
    -- result and status --
    result_o : out std_ulogic_vector(31 downto 0); -- operation result
    valid_o  : out std_ulogic                      -- operation done
  );
end neorv32_cpu_cp_cfu;

  -- **********************************************************
  -- CFU Example: XTEA - Extended Tiny Encryption Algorithm
  -- **********************************************************

  -- This CFU example implements the Extended Tiny Encryption Algorithm (XTEA).
  -- The CFU provides five R-type instructions for encryption and decryption.
  -- andfour I-type instruction are used for reading/writing the XTEA key registers.

  -- The RTL code was implemented according to an open-source C reference:
  -- https://de.wikipedia.org/wiki/Extended_Tiny_Encryption_Algorithm

architecture neorv32_cpu_cp_cfu_rtl of neorv32_cpu_cp_cfu is

  -- instruction type identifiers --
  constant r_type_c : std_ulogic := '0'; -- R-type CFU instructions (custom-0 opcode)
  constant i_type_c : std_ulogic := '1'; -- I-type CFU instructions (custom-1 opcode)

  -- instruction identifiers (funct3 bit-field) --
  constant xtea_enc_v0_c : std_ulogic_vector(2 downto 0) := "000";
  constant xtea_enc_v1_c : std_ulogic_vector(2 downto 0) := "001";
  constant xtea_dec_v0_c : std_ulogic_vector(2 downto 0) := "010";
  constant xtea_dec_v1_c : std_ulogic_vector(2 downto 0) := "011";
  constant xtea_init_c   : std_ulogic_vector(2 downto 0) := "100";
  
  constant lowercase     : std_ulogic_vector(2 downto 0) := "110";
  
  constant xorhash       : std_ulogic_vector(6 downto 0) := "0000001";
  constant fletcher      : std_ulogic_vector(6 downto 0) := "0000010";


  -- round-key update --
  constant xtea_delta_c : std_ulogic_vector(31 downto 0) := x"9e3779b9";

  -- key storage (accessed via special r4-type instructions) --
  type key_mem_t is array (0 to 3) of std_ulogic_vector(31 downto 0);
  signal key_mem : key_mem_t;

  -- processing logic --
  type xtea_t is record
    done : std_ulogic_vector(1 downto 0); -- multi-cycle done shift register; 2 stages = 2 cyles latency
    opa  : std_ulogic_vector(31 downto 0); -- input operand a
    opb  : std_ulogic_vector(31 downto 0); -- input operand b
    sum  : std_ulogic_vector(31 downto 0); -- round key buffer
    res  : std_ulogic_vector(31 downto 0); -- operation results
  end record;
  signal xtea : xtea_t;
  
  signal start_opascii, done_ascii, done : std_logic;
  signal reg_mask, maskres  : std_ulogic_vector(31 downto 0);
  signal ascii_lower_res, borrow, xor_res, y_shift : std_ulogic_vector(31 downto 0);
  signal ascii_res : std_ulogic_vector(31 downto 0);
  signal asc_temp, twos_comp : unsigned(31 downto 0);
  -- helpers --
  signal tmp_a, tmp_b, tmp_x, tmp_y, tmp_z, tmp_r : std_ulogic_vector(31 downto 0);

  signal rtmp_a : std_ulogic_vector(63 downto 0);
  signal ftmp_a, ftmp_b, res1, res2, ret : std_ulogic_vector(31 downto 0);
  
  type fletcherfsm is (IDLE, S1, S2, SORES);
  signal fletfsm : fletcherfsm;

begin
    
  reg_mask <= x"00000005"; 
    
  maskres <= reg_mask AND rs1_i;
  
  asc_temp <= unsigned(rs1_i);
  
  twos_comp <= not(x"00000020") + 1;
  
  
  
--  --ascii lower--
--  process(clk_i, rstn_i) 
--    begin
--        if rstn_i = '0' then
--            ascii_lower_res  <= (others => '0');
--            borrow           <= (others => '0');
--            xor_res          <= (others => '0');
--            y_shift          <= (others => '0');
--            done_ascii       <= '0';
--            start_opascii    <= '0';
--        elsif rising_edge(clk_i) then 
            
--            if start_i = '1' then 
--                asc_temp <= rs1_i;
--                start_opascii <= '1';
--            end if;
            
--            if start_opascii = '1' then 
--                borrow <= not(asc_temp) and x"00000014";
--                xor_res <= asc_temp xor x"00000014";
--                y_shift <= std_ulogic_vector(shift_left(unsigned(borrow), 1)); 
--                if y_shift = x"00000000" then
--                    ascii_res <= xor_res;
--                    start_opascii <= '0';
--                    done_ascii <= '1';
                                  
--                end if;
                
--            end if;
--       end if;
--  end process;
                    
                
   
  ascii_res <=  std_ulogic_vector(asc_temp + twos_comp);             
                
--xorhash
rtmp_a <= std_ulogic_vector(unsigned(rs1_i xor ((rs2_i(18 downto 0) & "0000000000000") xor ("0000000" & rs2_i(31 downto 7)))) * x"9E3779B1") ;
         
                
--fletcher 
fletcherxor:process(clk_i, rstn_i)
    begin
      if (rstn_i = '0') then
        fletfsm <= IDLE;
        ftmp_a <= (others => '0');
        ftmp_b <= (others => '0');
        done <= '0';
      elsif rising_edge(clk_i) then 
        case fletfsm is 
            when IDLE =>
                done <= '0';
                if start_i = '1' then 
                    fletfsm <= S1;
                    ftmp_a <= rs1_i;
                    ftmp_b <= rs2_i;
                else 
                    fletfsm <= IDLE;  
                end if;
            when S1  => 
                res1 <= std_ulogic_vector(unsigned((ftmp_a AND x"0000FFFF")) + unsigned((x"0000" & ftmp_a(31 downto 16)) AND x"0000FFFF") ); 
                fletfsm <= S2;
            when S2 => 
                res2 <= std_ulogic_vector(((unsigned(res1(15 downto 0)) + unsigned(ftmp_b AND x"0000FFFF")) + unsigned((x"0000" & ftmp_b(31 downto 16)) AND x"0000FFFF"))) ; 
                fletfsm <= SORES;
            when SORES =>
                ret <= res2(15 downto 0) & res1(15 downto 0);
                done <= '1';
                fletfsm <= IDLE;
         end case;
     end if;              
end process fletcherxor;    
            
  
  
  
  
  
            


  -- Function Result Select -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  result_select: process(type_i, funct3_i, funct7_i, imm12_i)
  begin -- no need for a register stage here; the CFU output is registered inside the ALU module anyway
    if (type_i = r_type_c) then -- R-type instructions; function select via "funct3" and ""funct7
    -- ----------------------------------------------------------------------
      case funct3_i is -- just check "funct3" here; "funct7" bit-field is ignored in this example
       when lowercase =>
          result_o <= ascii_res ; -- just output zero
          valid_o  <= '1' ; -- multi-cycle processing done when set
        when others => -- all unspecified operations
          result_o <= (others => '0'); -- no logic implemented
          valid_o  <= '0'; -- this will cause an illegal instruction exception
      end case;
      case funct7_i is 
        when xorhash =>
          result_o <= rtmp_a(31 downto 0) ; 
          valid_o  <= '1' ; 
        when fletcher =>
          result_o <= ret;
          valid_o <= done;
        when others => -- all unspecified operations
          result_o <= (others => '0'); -- no logic implemented
          valid_o  <= '0'; -- this will cause an illegal instruction exception
      
      end case;
    end if;
  end process result_select;


end neorv32_cpu_cp_cfu_rtl;
