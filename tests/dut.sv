//------------------------------------------------------------
//   Unpublished work. Copyright 2026 Siemens
//   All Rights Reserved Worldwide
//   
//   Licensed under the Apache License, Version 2.0 (the
//   "License"); you may not use this file except in
//   compliance with the License.  You may obtain a copy of
//   the License at
//   
//       http://www.apache.org/licenses/LICENSE-2.0
//   
//   Unless required by applicable law or agreed to in
//   writing, software distributed under the License is
//   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
//   CONDITIONS OF ANY KIND, either express or implied.  See
//   the License for the specific language governing
//   permissions and limitations under the License.
//------------------------------------------------------------
//pragma coverage block = on, expr = on, fsm = on, toggle = on

// REALLY LONG LINE
//345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678912345678901234567890123456789

module dut(
  input  logic        CLK  ,
  input  logic        VALID,
  output logic        READY,
  input  logic        RW   ,
  input  logic [31:0] ADDR ,
  input  logic [31:0] DATAI, // Input to the DUT.
  output logic [31:0] DATAO  // Output from the DUT.
  );

  bit execute_dollar_display;

  parameter BIT_WIDTH = 8;

  logic [31:0] mem[0:'hfff]; // Only 100-1000 are legal

  reg fast_clk;

  always begin
    #10; fast_clk = 0;
    #10; fast_clk = 1;
  end

  int CLK_count = 0;
  int fast_CLK_count = 0;

  logic rw;
  logic [31:0] addr;
  logic [31:0] data;

  logic [8:0] data_rot13;

  logic [7:0] offset = 'd13;
  logic [BIT_WIDTH-1:0] sum;
  logic co;

  bit secure_hw = 0;

  // -----------------------------------
  logic [3:0]digit;
  logic [3:0]digit2;
  logic [3:0]delayed_digit;
  logic [3:0]delayed_digit2;

  logic [3:0]nibble_index = 0;
  logic [2:0]nibble_index_correct;
  logic nibble_chooser = 0;

  assign nibble_index_correct = nibble_index;

  logic [7:0] n;
  bit [2:0] state;

  always @(posedge CLK)
    fast_CLK_count += 1;

  always @(posedge CLK)
    CLK_count += 1;

  parameter STATE0 = 0;
  parameter STATE1 = 1;
  parameter STATE2 = 2;
  parameter STATE3 = 3;
  parameter STATE4 = 4;
  parameter STATE5 = 5;
  parameter STATE6 = 6;
  parameter STATE7 = 7;

  always @(posedge CLK) begin
    case (state)
     STATE0: begin n = 0; n[0] = 1;  state = STATE1; end
     STATE1: begin n = 0; n[1] = 1;  state = STATE2; end
     STATE2: begin n = 0; n[2] = 1;  state = STATE3; end
     STATE3: begin n = 0; n[3] = 1;  state = STATE4; end
     STATE4: begin n = 0; n[4] = 1;  state = STATE5; end
     STATE5: begin n = 0; n[5] = 1;  state = STATE6; end
     STATE6: begin n = 0; n[6] = 1;  state = STATE7; end
     STATE7: begin n = 0; n[7] = 1;  state = STATE0; end
    endcase
  end

  logic [3:0] o, bv0, bv1, bv2, bv3, bv4, bv5, bv6, bv7, bv8;

  /*
  assign digit = 
    (nibble_chooser) & n[0] & data[ 3: 0] |
    (nibble_chooser) & n[1] & data[ 7: 4] |
    (nibble_chooser) & n[2] & data[11: 8] |
    (nibble_chooser) & n[3] & data[15:12] |
    (nibble_chooser) & n[4] & data[19:16] |
    (nibble_chooser) & n[5] & data[23:20] |
    (nibble_chooser) & n[6] & data[27:24] |
    (nibble_chooser) & n[7] & data[31:28] |
    (!nibble_chooser) & data [3:0];
    */

  /*
  assign digit = (nibble_chooser==1)? 
((nibble_index_correct==0)?data[ 3: 0]: 
  ((nibble_index_correct==1)?data[ 7: 4]: 
    ((nibble_index_correct==2)?data[11: 8]: 
      ((nibble_index_correct==3)?data[15:12]: 
        ((nibble_index_correct==4)?data[19:16]: 
          ((nibble_index_correct==5)?data[23:20]: 
            ((nibble_index_correct==6)?data[27:24]: 
              ((nibble_index_correct==7)?data[31:28]:'x))))))))
                : (data[3:0]);
*/

    and4 a0( bv0, nibble_chooser, n[0], data[ 3: 0]);
    and4 a1( bv1, nibble_chooser, n[1], data[ 7: 4]);
    and4 a2( bv2, nibble_chooser, n[2], data[11: 8]);
    and4 a3( bv3, nibble_chooser, n[3], data[15:12]);
    and4 a4( bv4, nibble_chooser, n[4], data[19:16]);
    and4 a5( bv5, nibble_chooser, n[5], data[23:20]);
    and4 a6( bv6, nibble_chooser, n[6], data[27:24]);
    and4 a7( bv7, nibble_chooser, n[7], data[31:28]);

    and4 a8( bv8, !nibble_chooser, !nibble_chooser, data [3:0]);

    or4 p( o, bv0, bv1, bv2, bv3, bv4, bv5, bv6, bv7);

    or o0 (digit[0], o[0], bv8[0]);
    or o1 (digit[1], o[1], bv8[1]);
    or o2 (digit[2], o[2], bv8[2]);
    or o3 (digit[3], o[3], bv8[3]);

  assign #3 delayed_digit = digit;
  assign #3 delayed_digit2 = digit2;

  always @(posedge CLK) begin
    nibble_chooser = 1;
    if (nibble_chooser==1) begin
      if (nibble_index==0)
        digit2 = data[ 3: 0];
      else if (nibble_index==1)
        digit2 = data[ 7: 4]; 
      else if (nibble_index==2)
        digit2 = data[11: 8]; 
      else if (nibble_index==3)
        digit2 = data[15:12]; 
      else if (nibble_index==4)
        digit2 = data[19:16]; 
      else if (nibble_index==5)
        digit2 = data[23:20]; 
      else if (nibble_index==6)
        digit2 = data[27:24]; 
      else if (nibble_index==7)
        digit2 = data[31:28];
      else
        digit2 = 'x; 
      nibble_index++;
    end
    else
      digit2 = data[3:0];
  end

  assign #2 data_rot13 = {co, sum};

  adder8 add_offset(sum, co, 1'b0, offset, data[7:0]);
  // -----------------------------------

  cube5x5 c1(CLK);

  // -----------------------------------

  ddd ddd1(CLK, d_calc);

  always @(d_calc)
    if (execute_dollar_display) 
      $display(
      "DUT_INFO %s(%0d) @ %0t: %m d_calc=%b", 
      `__FILE__, `__LINE__, $time, d_calc);
    

  // -----------------------------------
  logic [6:0]leds_first;
  logic [6:0]leds_first2;
  logic [6:0]leds_second;
  logic [6:0]leds_second2;
  logic [6:0]leds_last;
  logic [6:0]leds_last2;

  dff_chains chains(CLK, leds_second, leds_last);
  dff_chains chains2(CLK, leds_second2, leds_last2);
  // -----------------------------------

  // -----------------------------------
  logic [31:0] calc;
  logic [31:0] calc2;

  int factorial_calculated;
  int N;
  logic factorial_done;
  logic factorial_go;

  sin_calc m_sin_calc(CLK, calc, calc2);
  // -----------------------------------

  always begin
    N = N + 1; if ( N > 100 ) N = 0;
    factorial_go = 1;
    @(posedge CLK);
    factorial_go = 0;

    wait (factorial_done == 1);
    repeat (100) @(posedge CLK);
  end


  // -----------------------------------
  factorial factorial(CLK, factorial_go, N, factorial_calculated, factorial_done);
  // -----------------------------------

  typedef struct packed {
    logic [2:0] top;
    logic       middle;
    logic [2:0] bottom;
  } led_bv_t;

  led_bv_t led_bv1;
  led_bv_t led_bv2;
  led_bv_t led_bv3;
  led_bv_t led_bv4;

  led_bv_t led_bv12;
  led_bv_t led_bv22;
  led_bv_t led_bv32;
  led_bv_t led_bv42;

  assign #1 led_bv1 = leds_first;
  assign #1 led_bv2 = led_bv1;
  assign #1 led_bv3 = led_bv2;
  assign #1 led_bv4 = led_bv3;
  assign #1 leds_second = led_bv4;

  assign #1 led_bv12 = leds_first2;
  assign #1 led_bv22 = led_bv12;
  assign #1 led_bv32 = led_bv22;
  assign #1 led_bv42 = led_bv32;
  assign #1 leds_second2 = led_bv42;

  // -----------------------------------
  logic mode;

  bcd7 bcd7_inst(leds_first, delayed_digit, mode);
  bcd7 bcd7_inst2(leds_first2, delayed_digit2, mode);
  // -----------------------------------

  bit [2:0] which;
  bit [7:0] b8;
  bit [7:0] o8;

  always @(negedge CLK) begin
    if (which == 0)
      b8 = b8+1;
    which++;
  end
  
  always @(o8)
    if (execute_dollar_display) 
      $display(
      "DUT_INFO %s(%0d) @ %0t: %m o8=%8x", 
      `__FILE__, `__LINE__, $time, o8);

  bits b(CLK, b8, which, o8);

  // -----------------------------------
  logic sign_of_life_r_golden_model;
  logic sign_of_life_r1;
  logic sign_of_life_r2;
  logic sign_of_life_r_noearly;

  logic seti_clk;
  logic seti_rst;
  logic [31:0] seti_addr; // Register
  logic seti_check;       // Enable

  assign seti_clk = fast_clk;
  assign seti_rst = 0;


  seti_streamer ss(seti_rst, seti_clk, 
    seti_check,
    mem,
    seti_addr,
    sign_of_life_r_golden_model,
    sign_of_life_r1,
    sign_of_life_r2,
    sign_of_life_r_noearly);
  // -----------------------------------

  initial begin : RESET
    execute_dollar_display = 0;
    if ($test$plusargs("noisy_dut")) execute_dollar_display = 1;
    READY = 'x;
    rw = 'x;
    addr = 'x;
    data = 'x;
    mode = 1;
    offset = 'd13;
    #1000;
    READY = 1;
    @(posedge CLK);
  end

  always @(fast_CLK_count)
    if (execute_dollar_display) $display(
"DUT_INFO %s(%0d) @ %0t: %m fast_CLK_count=%0d", 
      `__FILE__, `__LINE__, $time, fast_CLK_count);

  always @(CLK_count)
    if (execute_dollar_display) $display(
"DUT_INFO %s(%0d) @ %0t: %m CLK_count=%0d", 
      `__FILE__, `__LINE__, $time, CLK_count);

  always @(leds_first)
    if (execute_dollar_display) $display(
"DUT_INFO %s(%0d) @ %0t: %m calc=%h", 
      `__FILE__, `__LINE__, $time, calc);

  always @(posedge sign_of_life_r_golden_model)
    if (sign_of_life_r_golden_model == 1) begin
      if (execute_dollar_display) 
        $display("Sign Of Life! Golden Model");
      #500;
    end
  always @(posedge sign_of_life_r1)
    if (sign_of_life_r1 == 1) begin
      if (execute_dollar_display) 
        $display("Sign Of Life! R1");
      #500;
    end
  always @(posedge sign_of_life_r2)
    if (sign_of_life_r2 == 1) begin
      if (execute_dollar_display) 
        $display("Sign Of Life! R2");
      #500;
    end
  always @(posedge sign_of_life_r_noearly)
    if (sign_of_life_r_noearly == 1) begin
      if (execute_dollar_display) 
        $display("Sign Of Life! R_NOEARLY");
      #500;
    end

  always @(leds_last)
    if (execute_dollar_display) $display(
      "DUT_INFO %s(%0d) @ %0t: %m leds_last=%7x", 
      `__FILE__, `__LINE__, $time, leds_last);

  always @(negedge VALID) begin
    DATAO = 'z; 
  end

  always @(posedge CLK) begin                //         always (
    if ((READY === 1) && (VALID === 1)) begin// if ready/valid (
      rw = RW;
      addr = ADDR;
      if (rw == 1) begin                     //          READ (
        #3; // Read Delay
        DATAO = mem[addr];

        if (execute_dollar_display) $display(
          "DUT_INFO %s(%0d) @ %0t: %m [%-20s] R(%0x, %0x)", 
          `__FILE__, `__LINE__, $time, "READ", addr, DATAO);

      end                                    //          READ )
      else if (RW == 0) begin                //          WRITE (
        data = DATAI;
        #2;

        if (execute_dollar_display) $display(
          "DUT_INFO %s(%0d) @ %0t: %m [%-20s] W(%0x, %0x)", 
          `__FILE__, `__LINE__, $time, "WRITE", addr, DATAO);

        if ((addr >= 1) && (addr <= 15)) begin//      REGISTER (
          // Register writes....
          if (secure_hw)
            mem[addr] = (data<<8) | (data_rot13);
          else
            mem[addr] = data;

          if (execute_dollar_display) $display(
"INFO: memory register write: mem[%d(0x%x)] = %d (0x%x)", 
            addr, addr, mem[addr], mem[addr]);

          case (addr)
            1: begin
              READY = 0;
              @(negedge CLK);
              seti_addr = data;
              seti_check = 1;
              repeat (128) 
                @(posedge seti_clk);
              seti_check = 0;
              @(negedge CLK);
              READY = 1;
            end
            default: begin
              if (execute_dollar_display) $display(
"INFO: memory register write: register %0d not implemented", 
                addr);
            end
          endcase
        end                                  //       REGISTER )
        // Fancy Command to print if ADDRESS == 0 and DATA == 1
        else if ((addr == 0) && (data == 1)) //        SPECIAL (
          mem_print();                       //        SPECIAL )
        else begin                           //         MEMORY (
          #2; // Write Delay
          // mem[addr] = (data<<8) | (data_rot13&8'hff);
          if (secure_hw)
            mem[addr] = (data<<8) | (data_rot13);
          else
            mem[addr] = data;
          if (execute_dollar_display) $display(
"INFO: memory write: mem[%d(0x%x)] = %d (0x%x)", 
            addr, addr, mem[addr], mem[addr]);
        end                                  //         MEMORY )
      end                                    //          WRITE )
    end                                      // if ready/valid )
  end                                        // always )

  function void mem_print();
    string line;
    logic [31:0] value;
    int j;

    if (execute_dollar_display) begin
      $display("======================");
      $display("Register Contents for %m");
      $display("======================");
      $display(" seti_addr = 0x%8x", seti_addr);
      $display("======================");
      $display("Memory Contents for %m");
      $display("======================");
    end
`ifdef FASTER // FASTER {
    if (execute_dollar_display) begin
    j = 0;
    line = "";
    for (int addr = 'h0000; addr < 'h1000; addr++) begin
      value = mem[addr];

      if (line == "")line=$sformatf("%8x: %8x", addr, value);
      else           line=$sformatf( "%s, %8x", line, value);

      if (++j == 8) begin
        $write("\n %s", line);
        line = "";
        j = 0;
      end
    end
    if (line != "") // flush
      $write("\n %s", line);
    $display("");
    $display("");
    end
`else // } SLOWER {
    j = 0;
    line = "";
    for (int addr = 'h0000; addr < 'h1000; addr++) begin
      value = mem[addr];

      if (line == "")line=$sformatf("%8x: %8x", addr, value);
      else           line=$sformatf( "%s, %8x", line, value);

      if (++j == 8) begin
        if (execute_dollar_display) $write("\n %s", line);
        line = "";
        j = 0;
      end
    end
    if (line != "") // flush
      if (execute_dollar_display) $write("\n %s", line);
    if (execute_dollar_display) $display("");
    if (execute_dollar_display) $display("");
`endif // } SLOWER/FASTER
  endfunction
endmodule

module triple_buffer(output x, y, z, input a, b, c);
  buf #1 (x, a);
  buf #2 (y, b);
  buf #3 (z, c);
endmodule

module ddd(input clk, output d);
  reg a, b, c;
  bit [2:0] i;

  triple_buffer tb1(a1, b1, c1, a, b, c);
  triple_buffer tb2(a2, b2, c2, b, c, a);
  triple_buffer tb3(a3, b3, c3, c, a, b);

  MAJ maj1(d1, a1, b1, c1);
  MAJ maj2(d2, a2, b2, c2);
  MAJ maj3(d3, a3, b3, c3);
  MAJ maj (d,  d1, d2, d3);

`ifdef DELAYED_CHAIN
  always @(posedge clk) i++;
  always @(posedge clk) {a,b,c} = i; 
`else
  always @(posedge clk) {a,b,c} = i; 
  always @(posedge clk) i++;
`endif

endmodule

