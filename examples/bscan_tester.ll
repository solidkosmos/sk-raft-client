Revision 3
; Created by bitgen 2023.2.2 at Mon Nov 10 10:15:28 2025
; Bit lines have the following form:
; <offset> <frame address> <frame offset> <information>
; <information> may be zero or more <kw>=<value> pairs
; Block=<blockname     specifies the block associated with this
;                      memory cell.
;
; Latch=<name>         specifies the latch associated with this memory cell.
;
; Net=<netname>        specifies the user net associated with this
;                      memory cell.
;
; COMPARE=[YES | NO]   specifies whether or not it is appropriate
;                      to compare this bit position between a
;                      "program" and a "readback" bitstream.
;                      If not present the default is NO.
;
; Ram=<ram id>:<bit>   This is used in cases where a CLB function
; Rom=<ram id>:<bit>   generator is used as RAM (or ROM).  <Ram id>
;                      will be either 'F', 'G', or 'M', indicating
;                      that it is part of a single F or G function
;                      generator used as RAM, or as a single RAM
;                      (or ROM) built from both F and G.  <Bit> is
;                      a decimal number.
;
; Info lines have the following form:
; Info <name>=<value>  specifies a bit associated with the LCA
;                      configuration options, and the value of
;                      that bit.  The names of these bits may have
;                      special meaning to software reading the .ll file.
;
Info STARTSEL0=1
Info BoundaryScanEnabled=1
Bit  9914563 0x0040029f   2019 Block=SLICE_X6Y31 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[15]
Bit  9564579 0x0040011f   1091 Block=SLICE_X0Y17 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[29]
Bit  9564582 0x0040011f   1094 Block=SLICE_X0Y17 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[30]
Bit  9564598 0x0040011f   1110 Block=SLICE_X0Y17 Latch=B5FF.Q Net=data_user_reg_data_out_reg_n_0_[32]
Bit  9564604 0x0040011f   1116 Block=SLICE_X0Y17 Latch=BQ Net=data_user_reg_data_out_reg_n_0_[31]
Bit  9564707 0x0040011f   1219 Block=SLICE_X0Y19 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[27]
Bit  9564710 0x0040011f   1222 Block=SLICE_X0Y19 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[28]
Bit  9565123 0x0040011f   1635 Block=SLICE_X0Y25 Latch=AQ Net=data_in_OBUF[10]
Bit  9565124 0x0040011f   1636 Block=SLICE_X1Y25 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[25]
Bit  9565125 0x0040011f   1637 Block=SLICE_X1Y25 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[26]
Bit  9565148 0x0040011f   1660 Block=SLICE_X0Y25 Latch=BQ Net=data_in_OBUF[12]
Bit  9565153 0x0040011f   1665 Block=SLICE_X0Y25 Latch=CQ Net=data_in_OBUF[13]
Bit  9565178 0x0040011f   1690 Block=SLICE_X0Y25 Latch=DQ Net=data_in_OBUF[14]
Bit  9565187 0x0040011f   1699 Block=SLICE_X0Y26 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[10]
Bit  9565188 0x0040011f   1700 Block=SLICE_X1Y26 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[14]
Bit  9565212 0x0040011f   1724 Block=SLICE_X0Y26 Latch=BQ Net=data_user_reg_data_in_reg_n_0_[11]
Bit  9565217 0x0040011f   1729 Block=SLICE_X0Y26 Latch=CQ Net=data_user_reg_data_in_reg_n_0_[12]
Bit  9565242 0x0040011f   1754 Block=SLICE_X0Y26 Latch=DQ Net=data_user_reg_data_in_reg_n_0_[13]
Bit  9565251 0x0040011f   1763 Block=SLICE_X0Y27 Latch=AQ Net=data_in_OBUF[11]
Bit  9565252 0x0040011f   1764 Block=SLICE_X1Y27 Latch=AQ Net=data_in_OBUF[15]
Bit  9565315 0x0040011f   1827 Block=SLICE_X0Y28 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[23]
Bit  9565318 0x0040011f   1830 Block=SLICE_X0Y28 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[24]
Bit  9565699 0x0040011f   2211 Block=SLICE_X0Y34 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[13]
Bit  9565702 0x0040011f   2214 Block=SLICE_X0Y34 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[14]
Bit  9565718 0x0040011f   2230 Block=SLICE_X0Y34 Latch=B5FF.Q Net=data_user_reg_data_out_reg_n_0_[16]
Bit  9565724 0x0040011f   2236 Block=SLICE_X0Y34 Latch=BQ Net=data_user_reg_data_out_reg_n_0_[15]
Bit  9565763 0x0040011f   2275 Block=SLICE_X0Y35 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[17]
Bit  9565766 0x0040011f   2278 Block=SLICE_X0Y35 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[18]
Bit  9565955 0x0040011f   2467 Block=SLICE_X0Y38 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[19]
Bit  9565958 0x0040011f   2470 Block=SLICE_X0Y38 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[20]
Bit  9565974 0x0040011f   2486 Block=SLICE_X0Y38 Latch=B5FF.Q Net=data_user_reg_data_out_reg_n_0_[22]
Bit  9565980 0x0040011f   2492 Block=SLICE_X0Y38 Latch=BQ Net=data_user_reg_data_out_reg_n_0_[21]
Bit  9566083 0x0040011f   2595 Block=SLICE_X0Y40 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[11]
Bit  9566086 0x0040011f   2598 Block=SLICE_X0Y40 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[12]
Bit   334435 0x0000011f   1539 Block=SLICE_X0Y74 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[9]
Bit  3151395 0x00000d9f    195 Block=SLICE_X42Y53 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[1]
Bit  3151398 0x00000d9f    198 Block=SLICE_X42Y53 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[2]
Bit  5292195 0x0002011f   1411 Block=SLICE_X0Y122 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[8]
Bit  5292259 0x0002011f   1475 Block=SLICE_X0Y123 Latch=AQ Net=data_in_OBUF[9]
Bit  5292323 0x0002011f   1539 Block=SLICE_X0Y124 Latch=AQ Net=data_in_OBUF[2]
Bit  5292324 0x0002011f   1540 Block=SLICE_X1Y124 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[2]
Bit  5292325 0x0002011f   1541 Block=SLICE_X1Y124 Latch=A5FF.Q Net=data_user_reg_data_in_reg_n_0_[6]
Bit  5292343 0x0002011f   1559 Block=SLICE_X1Y124 Latch=B5FF.Q Net=data_user_reg_data_in_reg_n_0_[7]
Bit  5292348 0x0002011f   1564 Block=SLICE_X0Y124 Latch=BQ Net=data_in_OBUF[3]
Bit  5292349 0x0002011f   1565 Block=SLICE_X1Y124 Latch=BQ Net=data_user_reg_data_in_reg_n_0_[3]
Bit  5292353 0x0002011f   1569 Block=SLICE_X0Y124 Latch=CQ Net=data_in_OBUF[5]
Bit  5292354 0x0002011f   1570 Block=SLICE_X1Y124 Latch=CQ Net=data_user_reg_data_in_reg_n_0_[4]
Bit  5292378 0x0002011f   1594 Block=SLICE_X0Y124 Latch=DQ Net=data_in_OBUF[7]
Bit  5292379 0x0002011f   1595 Block=SLICE_X1Y124 Latch=DQ Net=data_user_reg_data_in_reg_n_0_[5]
Bit  5292419 0x0002011f   1635 Block=SLICE_X0Y125 Latch=AQ Net=data_in_OBUF[4]
Bit  5292444 0x0002011f   1660 Block=SLICE_X0Y125 Latch=BQ Net=data_in_OBUF[6]
Bit  5292449 0x0002011f   1665 Block=SLICE_X0Y125 Latch=CQ Net=data_in_OBUF[8]
Bit 13934435 0x0040149f   1283 Block=SLICE_X64Y20 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[43]
Bit 13934438 0x0040149f   1286 Block=SLICE_X64Y20 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[44]
Bit 13934454 0x0040149f   1302 Block=SLICE_X64Y20 Latch=B5FF.Q Net=data_user_reg_data_out_reg_n_0_[46]
Bit 13934460 0x0040149f   1308 Block=SLICE_X64Y20 Latch=BQ Net=data_user_reg_data_out_reg_n_0_[45]
Bit 13934563 0x0040149f   1411 Block=SLICE_X64Y22 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[41]
Bit 13934566 0x0040149f   1414 Block=SLICE_X64Y22 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[42]
Bit 13935555 0x0040149f   2403 Block=SLICE_X64Y37 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[33]
Bit 13935558 0x0040149f   2406 Block=SLICE_X64Y37 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[34]
Bit 13935747 0x0040149f   2595 Block=SLICE_X64Y40 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[39]
Bit 13935750 0x0040149f   2598 Block=SLICE_X64Y40 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[40]
Bit 13935939 0x0040149f   2787 Block=SLICE_X64Y43 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[35]
Bit 13935942 0x0040149f   2790 Block=SLICE_X64Y43 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[36]
Bit 13936131 0x0040149f   2979 Block=SLICE_X64Y46 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[37]
Bit 13936134 0x0040149f   2982 Block=SLICE_X64Y46 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[38]
Bit  4704515 0x0000149f   1955 Block=SLICE_X64Y80 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[3]
Bit  4704518 0x0000149f   1958 Block=SLICE_X64Y80 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[4]
Bit  4704534 0x0000149f   1974 Block=SLICE_X64Y80 Latch=B5FF.Q Net=data_user_reg_data_out_reg_n_0_[6]
Bit  4704540 0x0000149f   1980 Block=SLICE_X64Y80 Latch=BQ Net=data_user_reg_data_out_reg_n_0_[5]
Bit  4704545 0x0000149f   1985 Block=SLICE_X64Y80 Latch=CQ Net=data_user_reg_data_out_reg_n_0_[7]
Bit  4704553 0x0000149f   1993 Block=SLICE_X64Y80 Latch=C5FF.Q Net=data_user_reg_data_out_reg_n_0_[8]
Bit 11472323 0x0040099f   1955 Block=SLICE_X28Y30 Latch=AQ Net=TDO
Bit 11472324 0x0040099f   1956 Block=SLICE_X29Y30 Latch=AQ Net=clk_en_OBUF
Bit 11472387 0x0040099f   2019 Block=SLICE_X28Y31 Latch=AQ Net=shift_reg_reg_n_0
Bit 11472388 0x0040099f   2020 Block=SLICE_X29Y31 Latch=AQ Net=wr_en_OBUF
Bit 11472899 0x0040099f   2531 Block=SLICE_X28Y39 Latch=AQ Net=tdo_data_out
Bit  2242691 0x0000099f   2915 Block=SLICE_X28Y95 Latch=AQ Net=data_in_OBUF[0]
Bit  2242755 0x0000099f   2979 Block=SLICE_X28Y96 Latch=AQ Net=tdo_data_in
Bit  2242819 0x0000099f   3043 Block=SLICE_X28Y97 Latch=AQ Net=data_in_OBUF[1]
Bit  2472611 0x00000a9f    131 Block=SLICE_X32Y52 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[10]
Bit  2472614 0x00000a9f    134 Block=SLICE_X32Y52 Latch=A5FF.Q Net=data_user_reg_data_out_reg_n_0_[9]
Bit 13701732 0x0040139f   1284 Block=SLICE_X61Y20 Latch=AQ Net=data_user_reg_data_out_reg_n_0_[47]
Bit  5847075 0x0002039f    387 Block=SLICE_X8Y106 Latch=AQ Net=data_user_reg_data_in_reg_n_0_[1]
