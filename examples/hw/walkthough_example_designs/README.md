
## Overview

These examples are meant to serve as a starting testing ground for the various functions provided by the SK-RAFT API. They are meant to be portable between AMD/Xilinx FPGA devices (7 series, Ultrascale and Ultrascale+) so they take into account the inferred primitives via generics, as well as general design customization.

Each example design is followed by a short functional description, specifications and what function(s) it exercises.

## Shared Building Blocks

*An example package is also utilized in these designs to serve as a basic building block of components they share.*
### `examples_utilities_pkg`

  *Contains the following components*:   

**`bscan_interface`** : Top-level JTAG/BSCAN wrapper -- pairs a BSCAN User Register IO instance with a BSCAN Primitive Wrapper, exposing a read/write data path (`data_to_jtag_i`/`data_from_jtag_o`) plus `avail`/`ack` handshake signals (which can be set as synchronous to a set clock reference) to the design.  

**`clk_gen_wrapper`** : Portable, family-selecting PLL passthrough wrapper (7-series / UltraScale / UltraScale+). Auto-computes `CLKFBOUT_MULT` from the input clock period and instantiates the correct native PLL primitive for the target family.

## Examples

### `example_1_adder`

*Static combinational adder (+5) driving LEDs directly from switch inputs -- first example in the get-started series.*

Can be sent out to LEDs to examine the result. If your setup doesn't have switches or LEDs, you can continue to the next example.

Specifications : 
	*Generic* : **added_num_bit_len** : integer range 1 to 13 := 4 -- Max 13 bits, reserved 3 for the static 5 addition 

### `example_2_targeted`

*Two independent heartbeat counters (slow, fast) for targeted fault-injection experiments.*

Similar to the previous example, if no LEDs are available, move to the next example.

Specifications : 
	*Generic*s :    
	    **g_family** : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
	    **clk_freq** : integer range 1 to 400 := 100;   -- Set the clock frequency to make the intervals time accurate (default 100MHz)
		**slow_heartbeat_interval** : integer range 1 to 5*(10**8) := 1*(10**8);    -- Max 5s (500,000,000 cycles) for 100MHz 
		**fast_heartbeat_interval** : integer range 1 to 5*(10**8) := (1*(10**8))/4 -- Set at default a quarter of a second
### `example_3_bscan_adder`

*JTAG/BSCAN-driven adder -- two BSCAN write channels feed two adders, a single and a TMR one, their sums are read back over their respective channel.*

Specifications : 
	*Generic*s :    
		**op_len** : integer range 1 to 32 := 4 -- The length in bits of each additive number (default 4 bits)
	*BSCAN USER Register Mapping* : 
		__USER 1__ : Write a number to be added (op_len bit length)
		__USER 2__ : Write a number to be added (op_len bit length)
		__USER 3__ : Read the result of the single voter (op_len + 1 carry bit length)
		__USER 4__ : Read the result of the TMR voter  (op_len + 1 carry bit length)

!!! (Bug) BSCAN Bit length has to be set to powers of 8 if lengths larger that 8 are needed. Lengths <8 can be set freely inside that range.
### `example_3a_dsp_target`

*Two identical DSP48-signed multiplier instances (clean reference vs. fault-injection target) fed the same JTAG/BSCAN operands, each result read back over its own channel for A/B comparison.*

Specifications : 
	*Generic*s :    
		__g_family__ : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
	    __clk_freq__ : integer range 1 to 400 := 100;   -- Set the clock frequency to set PLL parameters for proper passthrough clock
	    __a_len__ : positive := 18; -- Operand A bit length
	    __b_len__ : positive := 18  -- Operand B bit length 
	*BSCAN USER Register Mapping* : 
		__USER 1__ : Write operand A (__a_len__ bit length)
		__USER 2__ : Write operand B (__b_len__ bit length)
		__USER 3__ : Read the result of the clean DSP instance (__a_len__ + __b_len__ bit length)
		__USER 4__ : Read the result of the targeted DSP instance  (__a_len__ + __b_len__ bit length)
  

### `example_4_ff_lut`

*Free-running FF shift register (JTAG clock-gated) and an address-mapped LUTRAM, both driven over BSCAN.*

Specifications : 
	*Generic*s :    
		**g_family** : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
	    **sr_len**  : integer range 1 to 256 := 8;  -- The lengths of the shift registers, 8 bits by default
	    **lut_data_len** : integer range 1 to 256 := 32;  -- The data length of each LUT data, 4 bits default (2 memory elements = 8 LUTRAMS)
	    **shift_interval** : integer range 1 to 100 := 100; -- Shift every X ms for 100 MHz clock (1000 ms => 1 s)
	    **clk_freq** : integer range 1 to 400 := 100   -- Set the clock frequency to make the intervals time accurate (default 100MHz)
	*BSCAN USER Register Mapping* : 
		__USER 1__ : Clock enable for FF SR (1 bit R/W)
		__USER 2__ : Read FF SR (**sr_len** bit length)
		__USER 3__ : Address Select to LUTRAM (clog2(addr depth = 10))
		__USER 4__ : Read/Write data LUTRAM (**lut_data_len** bit length)

### `example_5_brams`

*Stock and ECC Block RAM instances driven over independent JTAG/BSCAN address and data channels, for A/B fault-injection comparison.*

Specifications : 
	*Generic*s :    
		**g_family** : string  := "7SERIES"; -- "7SERIES", "ULTRASCALE", or "ULTRASCALEPLUS" -- passed straight to clk_gen_wrapper
	    **clk_freq** : integer range 1 to 400 := 100 -- Set the clock frequency to set PLL parameters for proper passthrough clock
	*BSCAN USER Register Mapping* : 
		__USER 1__ : Stock BRAM Address Control R/W (16 bits, effective address space : 9 bits)
		__USER 2__ : ECC BRAM Address Control R/W (16 bits, effective address space : 9 bits)
		__USER 3__ : Stock BRAM Data R/W (64 bits)
		__USER 4__ : ECC BRAM Data R/W (64 bits)