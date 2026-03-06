import os
import json
import urllib.request
import urllib.error
import re

class TestbenchGenerator:
    def __init__(self, template_path):
        self.template_path = template_path
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()

    def generate(self, parsed_data, config):
        """
        parsed_data: Output from HDLParser.parse()
        config: Dictionary of user configurations like frequency, auto-reset, etc.
        """
        module_name = parsed_data.get('module_name', 'unknown_dut')
        
        # Helper to format signal declarations
        def format_signals(sig_list, sig_type="reg"):
            lines = []
            for item in sig_list:
                width = item.get('width', '')
                width_str = f" {width}" if width else ""
                lines.append(f"{sig_type}{width_str} {item['name']};")
            return '\n'.join(lines)

        # 1. Signal Declarations
        # Filter out clock and reset from the general input list to avoid double declaration
        general_inputs = []
        clock_name = config.get('clock_name', 'clk')
        reset_name = config.get('reset_name', 'rst_n')

        for item in parsed_data.get('inputs', []):
            if item['name'] not in [clock_name, reset_name]:
                general_inputs.append(item)

        input_signals = format_signals(general_inputs, "reg")
        output_signals = format_signals(parsed_data.get('outputs', []), "wire")
        inout_signals = format_signals(parsed_data.get('inouts', []), "wire")
        
        clock_res_signals = []
        if 'clock_name' in config:
            clock_res_signals.append(f"reg {config['clock_name']} = 0;")
        if 'reset_name' in config:
            clock_res_signals.append(f"reg {config['reset_name']};")
        clock_res_signals_str = '\n'.join(clock_res_signals)

        # 1.5 Parameters
        param_decls = []
        param_maps = []
        parameters = parsed_data.get('parameters', [])
        for param in parameters:
            name = param['name']
            value = param['value']
            param_decls.append(f"parameter {name} = {value};")
            param_maps.append(f".{name}({name})")
            
        param_decl_str = '\n'.join(param_decls)
        param_map_str = f"#({', '.join(param_maps)})" if param_maps else ""

        # 2. Port Map
        port_mapping = []
        for p_type in ['inputs', 'outputs', 'inouts']:
            for item in parsed_data.get(p_type, []):
                name = item['name']
                port_mapping.append(f"    .{name}({name})")
        port_map_str = ',\n'.join(port_mapping)

        # 3. Clock Generation
        clock_gen_str = ""
        if 'clock_name' in config and config.get('frequency_mhz'):
            freq = float(config['frequency_mhz'])
            duty_cycle = float(config.get('duty_cycle', 50.0))
            period_ns = 1000.0 / freq
            
            if duty_cycle == 50.0:
                half_period = period_ns / 2.0
                clock_gen_str = f"always #{half_period:.3f} {config['clock_name']} = ~{config['clock_name']};"
            else:
                high_time = period_ns * (duty_cycle / 100.0)
                low_time = period_ns - high_time
                clock_linhas = [
                    f"always begin",
                    f"    {config['clock_name']} = 1'b1;",
                    f"    #{high_time:.3f};",
                    f"    {config['clock_name']} = 1'b0;",
                    f"    #{low_time:.3f};",
                    f"end"
                ]
                clock_gen_str = '\n'.join(clock_linhas)

        # 4. Initial Block (Reset and Stimulus)
        initial_block_lines = ["initial begin"]
        
        # Reset Sequence
        delay = config.get('reset_delay_ns', 100)
        
        if config.get('auto_reset') and 'reset_name' in config:
            active_low = config.get('reset_active_low', True)
            assert_val = "0" if active_low else "1"
            deassert_val = "1" if active_low else "0"
            
            initial_block_lines.append(f"    // Reset sequence")
            initial_block_lines.append(f"    {config['reset_name']} = {assert_val};")
            initial_block_lines.append(f"    #{delay};")
            initial_block_lines.append(f"    {config['reset_name']} = {deassert_val};")
            initial_block_lines.append(f"    ")
            
        initial_block_lines.append("    // --- Auto-Generated Stimulus ---")
        
        # Initialize other general inputs to 0
        if general_inputs:
            initial_block_lines.append("    // Initialize inputs")
            for item in general_inputs:
                width = item.get('width', '')
                if width:
                    # simplistic heuristic: if vector, set to 0
                    initial_block_lines.append(f"    {item['name']} = 0;")
                else:
                    initial_block_lines.append(f"    {item['name']} = 1'b0;")
            initial_block_lines.append(f"    ")

        initial_block_lines.append(f"    // Wait for reset to finish")
        initial_block_lines.append(f"    #( {delay} + 10 );")
        initial_block_lines.append(f"    ")
        
        # Generate stimulus based on user selection
        enable_random = config.get('enable_random', True)
        lib_tasks = config.get('library_tasks', [])
        
        if general_inputs:
            clock_name = config.get('clock_name', 'clk')
            
            if enable_random:
                initial_block_lines.append("    // Apply random stimulus vectors")
                initial_block_lines.append("    repeat(20) begin")
                initial_block_lines.append(f"        @(posedge {clock_name});")
                for item in general_inputs:
                    initial_block_lines.append(f"        {item['name']} <= $urandom;")
                initial_block_lines.append("    end")
                initial_block_lines.append(f"    ")
                

            if lib_tasks and "None Available" not in lib_tasks:
                initial_block_lines.append("    // Apply Task-based Stimulus")
                initial_block_lines.append("    // NOTE: Call your custom tasks here")
                initial_block_lines.append("    apply_generic_stimulus(32'hDEADBEEF);")
                initial_block_lines.append(f"    ")

        initial_block_lines.append("    // Give some time to observe last changes")
        initial_block_lines.append("    #500;")
        initial_block_lines.append("    $finish;")
        initial_block_lines.append("end")
        
        # -------------------------------------------------------------------------
        # Intelligent Stimulus Task Generation
        # -------------------------------------------------------------------------
        if general_inputs and lib_tasks and "None Available" not in lib_tasks:
            clock_name = config.get('clock_name', 'clk')
            initial_block_lines.append("")
            initial_block_lines.append("// -----------------------------------------------------------------------------")
            
            initial_block_lines.append("// Stimulus Tasks (From Library)")
            initial_block_lines.append("// -----------------------------------------------------------------------------")
            tasks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'templates', 'tasks')
            
            for task_name in lib_tasks:
                task_path = os.path.join(tasks_dir, task_name)
                try:
                    with open(task_path, 'r', encoding='utf-8') as f:
                        raw_task = f.read()
                        
                        # Extremely simple auto-mapping for UART and SPI to reduce user editing
                        port_names = [p['name'] for p in (general_inputs + parsed_data.get('outputs', []))]
                        
                        # Map UART TX
                        uart_rxd_port = next((p for p in port_names if 'rxd' in p.lower() or 'uart_rx' in p.lower()), None)
                        if uart_rxd_port and 'uart_tx' in raw_task:
                            raw_task = re.sub(r'\buart_tx\b', uart_rxd_port, raw_task)
                            initial_block_lines.append(f"    // Auto-mapped 'uart_tx' to '{uart_rxd_port}'")
                            
                        # Map UART RX
                        uart_txd_port = next((p for p in port_names if 'txd' in p.lower() or 'uart_tx' in p.lower()), None)
                        if uart_txd_port and 'uart_rx' in raw_task:
                            raw_task = re.sub(r'\buart_rx\b', uart_txd_port, raw_task)
                            initial_block_lines.append(f"    // Auto-mapped 'uart_rx' to '{uart_txd_port}'")
                            
                        # Map SPI MOSI
                        spi_mosi_port = next((p for p in port_names if 'mosi' in p.lower()), None)
                        if spi_mosi_port and 'mosi' in raw_task:
                            raw_task = re.sub(r'\bmosi\b', spi_mosi_port, raw_task)
                        # Map SPI MISO
                        spi_miso_port = next((p for p in port_names if 'miso' in p.lower()), None)
                        if spi_miso_port and 'miso' in raw_task:
                            raw_task = re.sub(r'\bmiso\b', spi_miso_port, raw_task)
                        # Map SPI CS
                        spi_cs_port = next((p for p in port_names if 'cs' in p.lower() or 'ss' in p.lower()), None)
                        if spi_cs_port and 'cs_n' in raw_task:
                            raw_task = re.sub(r'\bcs_n\b', spi_cs_port, raw_task)

                        initial_block_lines.extend(raw_task.splitlines())
                except Exception as e:
                    initial_block_lines.append(f"// Error loading task {task_name}: {str(e)}")
                    
            # Update the placeholder in the initial block with actual task calls
            call_statements = []
            for task_name in lib_tasks:
                task_path = os.path.join(tasks_dir, task_name)
                if os.path.exists(task_path):
                    with open(task_path, 'r', encoding='utf-8') as f:
                        raw = f.read()
                        # Find task names and inputs
                        task_matches = re.finditer(r'\btask\s+(\w+);([\s\S]*?)\bbegin\b', raw)
                        for match in task_matches:
                            t_name = match.group(1)
                            args_block = match.group(2)
                            # Find inputs
                            inputs = re.findall(r'\binput\s+(?:\[.*?\]\s*)?(\\w+)\s*;', args_block)
                            
                            if inputs:
                                args_str = ", ".join([f"/*{inp}*/ 0" for inp in inputs])
                                call_statements.append(f"    {t_name}({args_str});")
                            else:
                                call_statements.append(f"    {t_name}();")
                                
            # Replace 'apply_generic_stimulus' placeholder with actual task calls
            for i, line in enumerate(initial_block_lines):
                if "apply_generic_stimulus" in line:
                    if call_statements:
                        initial_block_lines[i] = "    // Call your customized library tasks here:\n" + "\n".join(call_statements)
                    else:
                        initial_block_lines[i] = f"    // Call your customized library tasks here: {', '.join(lib_tasks)}"

            # Simple Protocol Detection Heuristics (OUTSIDE the for loop above!)
            port_names_lower = [p['name'].lower() for p in (general_inputs + parsed_data.get('outputs', []))]
            is_axi = any(p.startswith('awaddr') or p.startswith('s_axi_awaddr') or p.endswith('_awaddr') for p in port_names_lower)
            is_apb = any(p == 'paddr' or p.endswith('_paddr') for p in port_names_lower)
            is_i2c = any(p == 'scl' or p == 'sda' for p in port_names_lower)
            
            if is_axi:
                # Add basic AXI-Lite Write/Read Skeletons
                initial_block_lines.extend([
                    "task axi_write;",
                    "    input [31:0] addr;",
                    "    input [31:0] data;",
                    "begin",
                    f"    @(posedge {clock_name}); // AXI Write Address Phase",
                    "    // awvalid <= 1; awaddr <= addr; ... (Add your specific AXI ports here)",
                    f"    @(posedge {clock_name});",
                    "    // awvalid <= 0;",
                    f"    @(posedge {clock_name}); // AXI Write Data Phase",
                    "    // wvalid <= 1; wdata <= data; ...",
                    f"    @(posedge {clock_name});",
                    "    // wvalid <= 0;",
                    "end",
                    "endtask\n",
                    "task axi_read;",
                    "    input [31:0] addr;",
                    "begin",
                    f"    @(posedge {clock_name}); // AXI Read Address Phase",
                    "    // arvalid <= 1; araddr <= addr; ...",
                    f"    @(posedge {clock_name});",
                    "    // arvalid <= 0;",
                    "end",
                    "endtask"
                ])
                # update the initial block placeholder to use axi
                for i, line in enumerate(initial_block_lines):
                    if "apply_generic_stimulus" in line:
                        initial_block_lines[i] = "    // axi_write(32'h1000, 32'hDEADBEEF);"
        
            elif is_apb:
                # Add APB task skeleton
                initial_block_lines.extend([
                    "task apb_write;",
                    "    input [31:0] addr;",
                    "    input [31:0] data;",
                    "begin",
                    f"    @(posedge {clock_name}); // Setup Phase",
                    "    // psel <= 1; pwrite <= 1; paddr <= addr; pwdata <= data;",
                    f"    @(posedge {clock_name}); // Access Phase",
                    "    // penable <= 1;",
                    f"    @(posedge {clock_name}); // Wait for pready etc.",
                    "    // psel <= 0; penable <= 0;",
                    "end",
                    "endtask\n",
                    "task apb_read;",
                    "    input [31:0] addr;",
                    "begin",
                    f"    @(posedge {clock_name});",
                    "    // psel <= 1; pwrite <= 0; paddr <= addr;",
                    f"    @(posedge {clock_name});",
                    "    // penable <= 1;",
                    f"    @(posedge {clock_name});",
                    "    // psel <= 0; penable <= 0;",
                    "end",
                    "endtask"
                ])
                for i, line in enumerate(initial_block_lines):
                    if "apply_generic_stimulus" in line:
                        initial_block_lines[i] = "    // apb_write(32'h1000, 32'hDEADBEEF);"
                
            elif is_i2c:
                # Add I2C task skeleton
                initial_block_lines.extend([
                    "task i2c_start;",
                    "begin",
                    "    // sda <= 0; #5; scl <= 0;",
                    "end",
                    "endtask\n",
                    "task i2c_stop;",
                    "begin",
                    "    // sda <= 0; #5; scl <= 1; #5; sda <= 1;",
                    "end",
                    "endtask\n",
                    "task i2c_write_byte;",
                    "    input [7:0] data;",
                    "begin",
                    "    // for (int i=7; i>=0; i--) begin",
                    "    //    sda <= data[i]; #5; scl <= 1; #5; scl <= 0;",
                    "    // end",
                    "    // // Handle ACK...",
                    "end",
                    "endtask"
                ])
                for i, line in enumerate(initial_block_lines):
                    if "apply_generic_stimulus" in line:
                        initial_block_lines[i] = "    // i2c_start(); // i2c_write_byte(8'hA0); // i2c_stop();"
            else:
                # Fallback to the generic task
                initial_block_lines.append("task apply_generic_stimulus;")
                initial_block_lines.append("    input [31:0] data_val;")
                initial_block_lines.append("begin")
                initial_block_lines.append(f"    @(posedge {clock_name});")
                for item in general_inputs:
                    if 'data' in item['name'].lower() or 'val' in item['name'].lower():
                        initial_block_lines.append(f"    {item['name']} <= data_val;")
                    else: # Control signals like enable / write
                        initial_block_lines.append(f"    {item['name']} <= 1'b1;")
        initial_block_str = '\n'.join(initial_block_lines)

        # Replace placeholders in template
        output_tb = self.template
        output_tb = output_tb.replace("{MODULE_NAME}", module_name)
        output_tb = output_tb.replace("{PARAMETER_DECLARATIONS}", param_decl_str)
        output_tb = output_tb.replace("{PARAMETER_MAP}", param_map_str)
        output_tb = output_tb.replace("{CLOCK_RES_SIGNALS}", clock_res_signals_str)
        output_tb = output_tb.replace("{INPUT_SIGNALS}", input_signals)
        output_tb = output_tb.replace("{OUTPUT_SIGNALS}", output_signals)
        output_tb = output_tb.replace("{INOUT_SIGNALS}", inout_signals)
        output_tb = output_tb.replace("{PORT_MAP}", port_map_str)
        output_tb = output_tb.replace("{CLOCK_GENERATION}", clock_gen_str)
        output_tb = output_tb.replace("{INITIAL_BLOCK}", initial_block_str)

        return output_tb
