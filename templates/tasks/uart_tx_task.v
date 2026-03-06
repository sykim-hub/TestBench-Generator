// ==========================================
// UART Transmit (TX) Task
// Assumes a defined Baud Rate period (e.g., `define BAUD_PERIOD 8681 for 115200bps @ 1ns)
// ==========================================

// Uncomment and define these in your main TB if not defined
// `define BAUD_PERIOD 8681 // 115200 at 1ns timescale

task uart_send_byte;
    input [7:0] data_in;
    integer i;
begin
    // Start bit (Low)
    uart_tx <= 1'b0;
    #`BAUD_PERIOD;
    
    // Data bits (LSB first)
    for (i = 0; i < 8; i = i + 1) begin
        uart_tx <= data_in[i];
        #`BAUD_PERIOD;
    end
    
    // Stop bit (High)
    uart_tx <= 1'b1;
    #`BAUD_PERIOD;
    
    // Optional: Inter-byte delay
    #(`BAUD_PERIOD * 2);
end
endtask
