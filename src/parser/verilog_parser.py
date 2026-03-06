import re
from .hdl_parser import HDLParser

class VerilogParser(HDLParser):
    def parse(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {self.filepath}")

        # Remove comments (/* ... */ and // ...)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        content = re.sub(r'//.*', '', content)

        # 1. Extract module name
        module_match = re.search(r'\bmodule\s+([a-zA-Z_][a-zA-Z0-9_]*)\b', content)
        module_name = module_match.group(1) if module_match else "unknown_module"

        inputs = []
        outputs = []
        inouts = []

        # 2. Extract parameters
        parameters = []
        param_pattern = re.compile(r'\bparameter\s+(?:(?:integer|real|time)\s+)?(?:\[.*?\]\s*)?([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^;,)\s]+)')
        for p_match in param_pattern.finditer(content):
            parameters.append({'name': p_match.group(1), 'value': p_match.group(2)})

        # 3. Extract port declarations
        # Matches: input/output/inout [optional width block] port_names...
        port_pattern = re.compile(
            r'\b(input|output|inout)\b'
            r'(?:\s+(?:wire|reg|logic))?'  # match optional types
            r'(?:\s*(\[.*?\]))?'           # match optional width like [7:0]
            r'\s+([a-zA-Z0-9_,\s]+?)\s*[;,)]'
        )

        matches = port_pattern.finditer(content)
        for match in matches:
            dir_type = match.group(1)
            width = match.group(2) if match.group(2) else ""
            signals_str = match.group(3)

            # Clean and split signal names
            signal_names = [s.strip() for s in signals_str.split(',')]
            
            for name in signal_names:
                if not name:
                    continue
                # In case regex picked up trailing words poorly like `reg a`, take the last word as name
                name = name.split()[-1] 
                port_info = {'name': name, 'width': width.strip()}

                if dir_type == 'input':
                    inputs.append(port_info)
                elif dir_type == 'output':
                    outputs.append(port_info)
                elif dir_type == 'inout':
                    inouts.append(port_info)

        return {
            'module_name': module_name,
            'parameters': parameters,
            'inputs': inputs,
            'outputs': outputs,
            'inouts': inouts
        }
