import os

class HDLParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

    def parse(self):
        """
        Parses the HDL file and returns a dictionary with module info.
        Returns:
            dict: {
                'module_name': str,
                'inputs': [{'name': str, 'width': str}, ...],
                'outputs': [{'name': str, 'width': str}, ...],
                'inouts': [{'name': str, 'width': str}, ...]
            }
        """
        raise NotImplementedError("Subclasses must implement parse()")

def get_parser(filepath):
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    
    if ext == '.v':
        from .verilog_parser import VerilogParser
        return VerilogParser(filepath)
    elif ext == '.sv':
        from .sv_parser import SystemVerilogParser
        return SystemVerilogParser(filepath)
    elif ext in ['.vhd', '.vhdl']:
        from .vhdl_parser import VHDLParser
        return VHDLParser(filepath)
    else:
        raise ValueError(f"Unsupported file extension: '{ext}'. Supported extensions are .v, .sv, .vhd, .vhdl")
