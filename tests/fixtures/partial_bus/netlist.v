module partial_bus(
 input [7:0] a,
 input [7:0] b,
 input [0:0] c,
 output [16:0] y
);
 wire [8:0] u;
 wire [8:0] alias;
 assign alias[0] = a[0];
 assign alias[8:1] = u[8:1];
 u_rca8 A0 (.a(a), .b(b), .u_rca8_out(u));
 u_rca16 A1 (.a({7'b0, alias}), .b({15'b0, c}), .u_rca16_out(y));
endmodule
