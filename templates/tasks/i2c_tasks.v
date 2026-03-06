// ==========================================
// I2C Master Utility Tasks
// Note: sda and scl should be declared as inout, 
// and pulled up via tristate logic in the top level.
// e.g., assign sda = sda_dir ? 1'bz : sda_out;
// ==========================================

// `define I2C_HALF_PERIOD 5000 // 100kHz standard mode at 1ns timescale

task i2c_start;
begin
    scl <= 1'b1; // Assuming open-drain pullups
    sda <= 1'b1;
    #`I2C_HALF_PERIOD;
    sda <= 1'b0; // SDA goes low while SCL is high
    #`I2C_HALF_PERIOD;
    scl <= 1'b0;
end
endtask

task i2c_stop;
begin
    sda <= 1'b0;
    #`I2C_HALF_PERIOD;
    scl <= 1'b1;
    #`I2C_HALF_PERIOD;
    sda <= 1'b1; // SDA goes high while SCL is high
    #`I2C_HALF_PERIOD;
end
endtask

task i2c_write_byte;
    input [7:0] data;
    integer i;
begin
    for (i = 7; i >= 0; i = i - 1) begin
        sda <= data[i];
        #`I2C_HALF_PERIOD;
        scl <= 1'b1; // Clock High
        #`I2C_HALF_PERIOD;
        scl <= 1'b0; // Clock Low
    end
    
    // Wait for ACK from Slave
    sda <= 1'bz; // Release SDA
    #`I2C_HALF_PERIOD;
    scl <= 1'b1;
    #(`I2C_HALF_PERIOD/2);
    if (sda !== 1'b0) begin
        $display("[I2C WARNING] No ACK received!");
    end
    #(`I2C_HALF_PERIOD/2);
    scl <= 1'b0;
end
endtask
