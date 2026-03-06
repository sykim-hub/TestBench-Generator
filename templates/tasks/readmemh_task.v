// ==========================================
// Apply File-based Stimulus ($readmemh)
// Make sure 'input_vectors.hex' exists in your simulation directory
// ==========================================

// Uncomment and specify the depth and width
// reg [255:0] stimulus_memory [0:1023]; 

task apply_file_stimulus;
    integer i;
begin
    $readmemh("input_vectors.hex", stimulus_memory);
    for (i = 0; i < 20; i = i + 1) begin
        @(posedge clk);
        // Map memory contents to your inputs:
        // { port1, port2, port3 } = stimulus_memory[i];
    end
end
endtask
