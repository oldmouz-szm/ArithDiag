// Handwritten arithmetic fixture; not an ArithsGen generated file.
module u_rca16(
 input [15:0] a,
 input [15:0] b,
 output [16:0] u_rca16_out
);
 assign u_rca16_out = a + b;
endmodule
