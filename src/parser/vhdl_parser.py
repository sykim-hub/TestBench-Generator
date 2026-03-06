import re
from .hdl_parser import HDLParser

class VHDLParser(HDLParser):
    def parse(self):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {self.filepath}")

        # Remove single line comments (-- ...)
        content = re.sub(r'--.*', '', content)

        # 1. Extract entity block
        entity_block_match = re.search(r'(?i)\bentity\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+is(.*?)\bend\b', content, flags=re.DOTALL)
        
        module_name = "unknown_entity"
        entity_content = ""
        if entity_block_match:
            module_name = entity_block_match.group(1)
            entity_content = entity_block_match.group(2)
        else:
            return {'module_name': module_name, 'inputs': [], 'outputs': [], 'inouts': []}

        inputs = []
        outputs = []
        inouts = []

        # 2. Extract port declarations inside the entity block using paren balancing
        port_block_match = re.search(r'(?i)\bport\s*\(', entity_content)
        
        if port_block_match:
            start_idx = port_block_match.end()
            paren_count = 1
            idx = start_idx
            while idx < len(entity_content):
                if entity_content[idx] == '(':
                    paren_count += 1
                elif entity_content[idx] == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        break
                idx += 1
                
            port_block = entity_content[start_idx:idx]
            # Split declarations by ';' (each port or group of ports)
            port_lines = port_block.split(';')
            
            for line in port_lines:
                line = line.strip()
                if ':' not in line:
                    continue
                
                # Split names and direction/type
                parts = line.split(':')
                names_str = parts[0].strip()
                dir_type_str = parts[1].strip()
                
                # Parse direction (in/out/inout/buffer)
                direction_match = re.search(r'(?i)\b(in|out|inout|in\s+out|buffer)\b', dir_type_str)
                direction = "input" # default
                if direction_match:
                    dir_val = direction_match.group(1).lower().replace(' ', '')
                    if dir_val in ('out', 'buffer'):
                        direction = 'output'
                    elif dir_val == 'inout':
                        direction = 'inout'

                # Extract width loosely. VHDL vectors usually look like `std_logic_vector(7 downto 0)`
                width_match = re.search(r'(?i)\((.*?(?:downto|to).*?)\)', dir_type_str)
                width = f"[{width_match.group(1).strip()}]" if width_match else ""

                # There could be multiple port names before the colon `clk, rst: in std_logic`
                port_names = [n.strip() for n in names_str.split(',')]
                
                for name in port_names:
                    if not name: continue
                    port_info = {'name': name, 'width': width}
                    if direction == 'input':
                        inputs.append(port_info)
                    elif direction == 'output':
                        outputs.append(port_info)
                    elif direction == 'inout':
                        inouts.append(port_info)

        return {
            'module_name': module_name,
            'inputs': inputs,
            'outputs': outputs,
            'inouts': inouts
        }
