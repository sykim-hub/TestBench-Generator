module dummy_counter #(
    parameter WIDTH = 8
)(
    input  wire             clk,      // Clock signal
    input  wire             rst_n,    // Active-low reset
    input  wire             enable,   // Counter enable
    input  wire             load,     // Load enable
    input  wire [WIDTH-1:0] load_val, // Value to load
    output reg  [WIDTH-1:0] count,    // Current count value
    output wire             overflow  // Indicates count reached max
);

    // Increment logic
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= {WIDTH{1'b0}};
        end else if (load) begin
            count <= load_val;
        end else if (enable) begin
            count <= count + 1'b1;
        end
    end

    // Overflow flag logic
    assign overflow = (count == {WIDTH{1'b1}}) ? 1'b1 : 1'b0;

endmodule
