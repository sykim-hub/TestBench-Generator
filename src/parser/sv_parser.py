from .verilog_parser import VerilogParser

class SystemVerilogParser(VerilogParser):
    def parse(self):
        # For now, SystemVerilog structures (like logic, arrays, interfaces) can be very complex.
        # As a starting point, we leverage the same regex logic as VerilogParser
        # since basic SystemVerilog module definitions often match standard Verilog syntax.
        # Future enhancements can add SV-specific parsing logic here.
        return super().parse()
