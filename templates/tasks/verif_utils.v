// ==========================================
// Verification Utilities
// Wait with timeout, Edge-case reset injection, Compare
// ==========================================

task wait_with_timeout;
    input integer timeout_cycles;
    integer count;
begin
    count = 0;
    // Wait for 'done' signal to be 1, or timeout
    while ((done !== 1'b1) && (count < timeout_cycles)) begin
        @(posedge clk);
        count = count + 1;
    end
    
    if (count == timeout_cycles) begin
        $display("[TIMEOUT ERROR] 'done' signal did not assert within %0d cycles at time %0t", timeout_cycles, $time);
    end else begin
        $display("[SUCCESS] 'done' asserted after %0d cycles.", count);
    end
end
endtask

task compare_value;
    input [31:0] expected;
    input [31:0] actual;
    input [80*8:1] signal_name; // Up to 80 chars string
begin
    if (expected !== actual) begin
        $display("[MISMATCH ERROR] %0s Expected: %h, Actual: %h at time %0t", signal_name, expected, actual, $time);
    end else begin
        $display("[MATCH] %0s = %h", signal_name, actual);
    end
end
endtask

task apply_async_reset;
    input integer reset_width_ns;
begin
    $display("[INFO] Applying Asynchronous Reset at time %0t", $time);
    rst_n <= 1'b0;
    #(reset_width_ns);
    rst_n <= 1'b1;
    $display("[INFO] Releasing Asynchronous Reset at time %0t", $time);
end
endtask
