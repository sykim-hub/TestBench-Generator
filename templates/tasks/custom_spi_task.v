// ==========================================
// Custom SPI Transfer Task Example
// ==========================================
task spi_transfer;
    input [7:0] data_in;
begin
    // Cs low
    @(posedge clk);
    cs_n <= 1'b0;
    
    // Send 8 bits
    for (int i=7; i>=0; i=i-1) begin
        @(negedge clk);
        mosi <= data_in[i];
    end
    
    // Cs high
    @(posedge clk);
    cs_n <= 1'b1;
end
endtask
