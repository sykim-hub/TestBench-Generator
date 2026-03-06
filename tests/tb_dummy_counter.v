// -----------------------------------------------------------------------------
// AutoSafeX Auto-Generated Testbench
// Module: dummy_counter
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module tb_dummy_counter();

// -----------------------------------------------------------------------------
// Parameters
// -----------------------------------------------------------------------------
parameter WIDTH = 8;

// -----------------------------------------------------------------------------
// Signal Declarations
// -----------------------------------------------------------------------------
// Clocks and Resets
reg clk = 0;
reg rst_n;

// DUT Inputs
reg enable;
reg load;
reg [WIDTH-1:0] load_val;

// DUT Outputs
wire [WIDTH-1:0] count;
wire overflow;

// DUT Inouts



// -----------------------------------------------------------------------------
// DUT Instantiation
// -----------------------------------------------------------------------------
dummy_counter #(.WIDTH(WIDTH)) u_dut (
    .clk(clk),
    .rst_n(rst_n),
    .enable(enable),
    .load(load),
    .load_val(load_val),
    .count(count),
    .overflow(overflow)
);

// -----------------------------------------------------------------------------
// Clock Generation Block
// -----------------------------------------------------------------------------
always #5.000 clk = ~clk;

// -----------------------------------------------------------------------------
// Reset and Initial Stimulus Block
// -----------------------------------------------------------------------------
initial begin
    // Reset sequence
    rst_n = 0;
    #100.0;
    rst_n = 1;
    
    // --- Auto-Generated Stimulus ---
    // Initialize inputs
    enable = 1'b0;
    load = 1'b0;
    load_val = 0;
    
    // Wait for reset to finish
    #( 100.0 + 10 );
    
    // Apply Task-based Stimulus
    // NOTE: Call your custom tasks here
    apply_generic_stimulus(32'hDEADBEEF);
    apply_generic_stimulus(32'hCAFEBABE);
    
    // Give some time to observe last changes
    #500;
    $finish;
end

// -----------------------------------------------------------------------------
// Stimulus Tasks
// -----------------------------------------------------------------------------
task apply_generic_stimulus;
    input [31:0] data_val;
begin
    @(posedge clk);
    enable <= 1'b1;
    load <= 1'b1;
    load_val <= data_val;
    @(posedge clk);
    enable <= 1'b0;
    load <= 1'b0;
end
endtask

endmodule
