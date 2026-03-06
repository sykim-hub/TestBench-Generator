// ==========================================
// AXI-Lite Write and Read Tasks
// Assumes standard AXI-Lite port names and a clock named 'clk'
// ==========================================

task axi_lite_write;
    input [31:0] waddr;
    input [31:0] wdata;
begin
    // 1. Write Address Phase
    @(posedge clk);
    s_axi_awaddr  <= waddr;
    s_axi_awvalid <= 1'b1;
    
    // Wait for AWREADY
    wait(s_axi_awready == 1'b1);
    @(posedge clk);
    s_axi_awvalid <= 1'b0;

    // 2. Write Data Phase
    s_axi_wdata   <= wdata;
    s_axi_wstrb   <= 4'hF; // All bytes valid
    s_axi_wvalid  <= 1'b1;
    
    // Wait for WREADY
    wait(s_axi_wready == 1'b1);
    @(posedge clk);
    s_axi_wvalid  <= 1'b0;
    
    // 3. Write Response Phase
    s_axi_bready  <= 1'b1;
    wait(s_axi_bvalid == 1'b1);
    @(posedge clk);
    s_axi_bready  <= 1'b0;
    
    // Check response (optional)
    if (s_axi_bresp != 2'b00) begin
        $display("[AXI ERROR] Write to %h returned error response: %b", waddr, s_axi_bresp);
    end
end
endtask

task axi_lite_read;
    input  [31:0] raddr;
    output [31:0] rdata;
begin
    // 1. Read Address Phase
    @(posedge clk);
    s_axi_araddr  <= raddr;
    s_axi_arvalid <= 1'b1;
    
    // Wait for ARREADY
    wait(s_axi_arready == 1'b1);
    @(posedge clk);
    s_axi_arvalid <= 1'b0;
    
    // 2. Read Data Phase
    s_axi_rready  <= 1'b1;
    wait(s_axi_rvalid == 1'b1);
    rdata = s_axi_rdata;
    
    // Check response (optional)
    if (s_axi_rresp != 2'b00) begin
        $display("[AXI ERROR] Read from %h returned error response: %b", raddr, s_axi_rresp);
    end
    
    @(posedge clk);
    s_axi_rready  <= 1'b0;
end
endtask
