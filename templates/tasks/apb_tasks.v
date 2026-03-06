// ==========================================
// APB Master Utility Tasks
// ==========================================

task apb_write;
    input [31:0] addr;
    input [31:0] data;
begin
    // Setup Phase
    @(posedge clk);
    psel    <= 1'b1;
    pwrite  <= 1'b1;
    paddr   <= addr;
    pwdata  <= data;
    penable <= 1'b0;
    
    // Access Phase
    @(posedge clk);
    penable <= 1'b1;
    
    // Wait for Peripheral Ready
    wait(pready == 1'b1);
    
    // Cleanup
    @(posedge clk);
    psel    <= 1'b0;
    penable <= 1'b0;
end
endtask

task apb_read;
    input  [31:0] addr;
    output [31:0] read_data;
begin
    // Setup Phase
    @(posedge clk);
    psel    <= 1'b1;
    pwrite  <= 1'b0;
    paddr   <= addr;
    penable <= 1'b0;
    
    // Access Phase
    @(posedge clk);
    penable <= 1'b1;
    
    // Wait for Peripheral Ready
    wait(pready == 1'b1);
    read_data = prdata;
    
    // Cleanup
    @(posedge clk);
    psel    <= 1'b0;
    penable <= 1'b0;
end
endtask
