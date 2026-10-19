// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 SOLIDKOSMOS S.A.
//
// UltraScale naming test for bram_shadow_pass.tcl (UltraScale and
// UltraScale+ parts).
// One instance per case the pass has to recognise; every BRAM output in
// use feeds a register, and each group of registers is XOR-reduced to one
// output pin so nothing is optimised away. No board needed.
//
//   u_tdp    RAMB36E2 TDP x36, DOA_REG = 0, DOB_REG = 1
//            expected: port A shadowed (36 pins), port B DO_REG = 1
//   u_wide   RAMB36E2 72-bit read (READ_WIDTH_A = 72) with ECC, DO_REG = 0
//            expected: SDP read port shadowed (64 data + SBITERR + DBITERR
//            + 9 RDADDRECC = 75 pins)
//   u_r18    RAMB18E2 TDP x18, DOA_REG = 0, port B unused
//            expected: port A shadowed (16 pins), port B no loads
//   u_fifo0  FIFO36E2 REGISTER_MODE = UNREGISTERED
//            expected: read port shadowed (64 pins)
//   u_fifo1  FIFO36E2 REGISTER_MODE = REGISTERED
//            expected: skipped (REGISTER_MODE)
//   u_cas0/1 RAMB36E2 output cascade (CASCADE_ORDER_A = FIRST / LAST)
//            expected: reported, not changed
//   u_shd    RAMB36E2 TDP x36, DOA_REG = 0, source shadow on 8 bits
//            (falling edge, CE = enable registered on the rising edge)
//            expected: already shadowed (8 pins)
//   u_pipe   RAMB36E2 TDP x36, DOA_REG = 0, falling-edge register with
//            CE = 1 on 8 bits
//            expected: shadowed 8 pins, 8 loads on the DO/shadow mux

module us_naming_top (
    input  wire        clk,
    input  wire        en,
    input  wire        we,
    input  wire [14:0] addr,
    output wire        o_tdp_a,
    output wire        o_tdp_b,
    output wire        o_wide,
    output wire        o_r18,
    output wire        o_fifo0,
    output wire        o_fifo1,
    output wire        o_casc,
    output wire        o_shd,
    output wire        o_pipe
);

    wire [63:0] din = {addr, addr, addr, addr, addr[3:0]};

    // ------------------------------------------------------------ u_tdp
    wire [31:0] tdp_a, tdp_b;
    wire [3:0]  tdp_pa, tdp_pb;
    RAMB36E2 #(
        .CLOCK_DOMAINS ("COMMON"),
        .READ_WIDTH_A  (36), .READ_WIDTH_B  (36),
        .WRITE_WIDTH_A (36), .WRITE_WIDTH_B (36),
        .WRITE_MODE_A  ("READ_FIRST"), .WRITE_MODE_B ("READ_FIRST"),
        .DOA_REG       (0), .DOB_REG (1)
    ) u_tdp (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (en),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr), .ADDRBWRADDR (addr),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0),
        .WEA ({4{we}}), .WEBWE (8'b0),
        .DINADIN (din[31:0]), .DINPADINP (4'b0),
        .DINBDIN (32'b0), .DINPBDINP (4'b0),
        .DOUTADOUT (tdp_a), .DOUTPADOUTP (tdp_pa),
        .DOUTBDOUT (tdp_b), .DOUTPBDOUTP (tdp_pb)
    );
    reg [35:0] q_tdp_a, q_tdp_b;
    always @(posedge clk) begin
        q_tdp_a <= {tdp_pa, tdp_a};
        q_tdp_b <= {tdp_pb, tdp_b};
    end
    assign o_tdp_a = ^q_tdp_a;
    assign o_tdp_b = ^q_tdp_b;

    // ----------------------------------------------------------- u_wide
    wire [31:0] wide_a, wide_b;
    wire        wide_sbit, wide_dbit;
    wire [8:0]  wide_addr;
    RAMB36E2 #(
        .CLOCK_DOMAINS ("COMMON"),
        .READ_WIDTH_A  (72), .WRITE_WIDTH_B (72),
        .WRITE_MODE_A  ("READ_FIRST"), .WRITE_MODE_B ("READ_FIRST"),
        .EN_ECC_READ   ("TRUE"), .EN_ECC_WRITE ("TRUE"),
        .DOA_REG       (0), .DOB_REG (0)
    ) u_wide (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (we),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr), .ADDRBWRADDR (addr),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0), .ECCPIPECE (1'b1),
        .INJECTSBITERR (1'b0), .INJECTDBITERR (1'b0),
        // ECC write: WEBWE must be all ones, writes are enabled by ENBWREN
        .WEA (4'b0), .WEBWE (8'hFF),
        .DINADIN (din[31:0]), .DINBDIN (din[63:32]),
        .DINPADINP (4'b0), .DINPBDINP (4'b0),
        .DOUTADOUT (wide_a), .DOUTBDOUT (wide_b),
        .SBITERR (wide_sbit), .DBITERR (wide_dbit),
        .RDADDRECC (wide_addr)
    );
    reg [74:0] q_wide;
    always @(posedge clk)
        q_wide <= {wide_addr, wide_dbit, wide_sbit, wide_b, wide_a};
    assign o_wide = ^q_wide;

    // ------------------------------------------------------------ u_r18
    wire [15:0] r18_a;
    RAMB18E2 #(
        .CLOCK_DOMAINS ("COMMON"),
        .READ_WIDTH_A  (18), .WRITE_WIDTH_A (18),
        .WRITE_MODE_A  ("READ_FIRST"),
        .DOA_REG       (0), .DOB_REG (0)
    ) u_r18 (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (1'b0),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr[13:0]), .ADDRBWRADDR (14'b0),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0),
        .WEA ({2{we}}), .WEBWE (4'b0),
        .DINADIN (din[15:0]), .DINPADINP (2'b0),
        .DINBDIN (16'b0), .DINPBDINP (2'b0),
        .DOUTADOUT (r18_a)
    );
    reg [15:0] q_r18;
    always @(posedge clk) q_r18 <= r18_a;
    assign o_r18 = ^q_r18;

    // -------------------------------------------------- u_fifo0, u_fifo1
    wire [63:0] f0_do, f1_do;
    FIFO36E2 #(
        .CASCADE_ORDER ("NONE"), .CLOCK_DOMAINS ("COMMON"),
        .FIRST_WORD_FALL_THROUGH ("FALSE"),
        .READ_WIDTH (72), .WRITE_WIDTH (72),
        .REGISTER_MODE ("UNREGISTERED")
    ) u_fifo0 (
        .RDCLK (clk), .WRCLK (clk), .RDEN (en), .WREN (we),
        .RST (1'b0), .RSTREG (1'b0), .REGCE (1'b1), .SLEEP (1'b0),
        .DIN (din), .DINP (8'b0),
        .DOUT (f0_do)
    );
    FIFO36E2 #(
        .CASCADE_ORDER ("NONE"), .CLOCK_DOMAINS ("COMMON"),
        .FIRST_WORD_FALL_THROUGH ("FALSE"),
        .READ_WIDTH (72), .WRITE_WIDTH (72),
        .REGISTER_MODE ("REGISTERED")
    ) u_fifo1 (
        .RDCLK (clk), .WRCLK (clk), .RDEN (en), .WREN (we),
        .RST (1'b0), .RSTREG (1'b0), .REGCE (1'b1), .SLEEP (1'b0),
        .DIN (din), .DINP (8'b0),
        .DOUT (f1_do)
    );
    reg [63:0] q_f0, q_f1;
    always @(posedge clk) begin
        q_f0 <= f0_do;
        q_f1 <= f1_do;
    end
    assign o_fifo0 = ^q_f0;
    assign o_fifo1 = ^q_f1;

    // ----------------------------------------------------- u_cas0, u_cas1
    wire [31:0] cas_d, cas1_a;
    wire [3:0]  cas_dp;
    RAMB36E2 #(
        .CLOCK_DOMAINS ("COMMON"), .CASCADE_ORDER_A ("FIRST"),
        .READ_WIDTH_A (36), .WRITE_WIDTH_A (36),
        .DOA_REG (0), .DOB_REG (0)
    ) u_cas0 (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (1'b0),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr), .ADDRBWRADDR (15'b0),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0),
        .WEA ({4{we}}), .WEBWE (8'b0),
        .DINADIN (din[31:0]), .DINPADINP (4'b0),
        .CASDOUTA (cas_d), .CASDOUTPA (cas_dp)
    );
    RAMB36E2 #(
        .CLOCK_DOMAINS ("COMMON"), .CASCADE_ORDER_A ("LAST"),
        .READ_WIDTH_A (36), .WRITE_WIDTH_A (36),
        .DOA_REG (0), .DOB_REG (0)
    ) u_cas1 (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (1'b0),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr), .ADDRBWRADDR (15'b0),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0),
        .WEA ({4{we}}), .WEBWE (8'b0),
        .DINADIN (din[63:32]), .DINPADINP (4'b0),
        .CASDINA (cas_d), .CASDINPA (cas_dp),
        .CASDOMUXA (addr[14]), .CASDOMUXEN_A (1'b1),
        .DOUTADOUT (cas1_a)
    );
    reg [31:0] q_cas;
    always @(posedge clk) q_cas <= cas1_a;
    assign o_casc = ^q_cas;

    // ------------------------------------------------------------ u_shd
    wire [31:0] shd_a;
    RAMB36E2 #(
        .CLOCK_DOMAINS ("COMMON"),
        .READ_WIDTH_A (36), .WRITE_WIDTH_A (36),
        .DOA_REG (0), .DOB_REG (0)
    ) u_shd (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (1'b0),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr), .ADDRBWRADDR (15'b0),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0),
        .WEA (4'b0), .WEBWE (8'b0),
        .DINADIN (din[31:0]), .DINPADINP (4'b0),
        .DOUTADOUT (shd_a)
    );
    // source shadow: falling edge, CE = enable registered on the rising edge
    reg       ren_d;
    reg [7:0] shd_s, q_shd;
    always @(posedge clk) ren_d <= en;
    always @(negedge clk) if (ren_d) shd_s <= shd_a[7:0];
    always @(posedge clk) q_shd <= shd_s;
    assign o_shd = ^q_shd;

    // ----------------------------------------------------------- u_pipe
    wire [31:0] pipe_a;
    RAMB36E2 #(
        .CLOCK_DOMAINS ("COMMON"),
        .READ_WIDTH_A (36), .WRITE_WIDTH_A (36),
        .DOA_REG (0), .DOB_REG (0)
    ) u_pipe (
        .CLKARDCLK (clk), .CLKBWRCLK (clk),
        .ENARDEN (en), .ENBWREN (1'b0),
        .ADDRENA (1'b1), .ADDRENB (1'b1),
        .ADDRARDADDR (addr), .ADDRBWRADDR (15'b0),
        .REGCEAREGCE (1'b1), .REGCEB (1'b1),
        .RSTRAMARSTRAM (1'b0), .RSTRAMB (1'b0),
        .RSTREGARSTREG (1'b0), .RSTREGB (1'b0),
        .SLEEP (1'b0),
        .WEA ({4{we}}), .WEBWE (8'b0),
        .DINADIN (din[31:0]), .DINPADINP (4'b0),
        .DOUTADOUT (pipe_a)
    );
    // not a shadow: falling edge, loads every cycle
    reg [7:0] pipe_r, q_pipe;
    always @(negedge clk) pipe_r <= pipe_a[7:0];
    always @(posedge clk) q_pipe <= pipe_r;
    assign o_pipe = ^q_pipe;

endmodule
