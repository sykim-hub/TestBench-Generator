import argparse
import sys
import os

# Add src to the module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parser import get_parser
from src.generator.tb_generator import TestbenchGenerator

def main():
    parser = argparse.ArgumentParser(description="AutoSafeX - Testbench Generator CLI")
    parser.add_argument("input_file", help="Path to the HDL design file (.v, .sv, .vhd)")
    parser.add_argument("-o", "--output", help="Path to output testbench file", default=None)
    parser.add_argument("--clk-name", help="Clock signal name", default="clk")
    parser.add_argument("--clk-freq", help="Clock frequency in MHz", type=float, default=100.0)
    parser.add_argument("--rst-name", help="Reset signal name", default="rst_n")
    parser.add_argument("--rst-delay", help="Reset delay in ns", type=float, default=100.0)

    args = parser.parse_args()

    print(f"[INFO] Parsing input file: {args.input_file}")
    
    try:
        hdl_parser = get_parser(args.input_file)
        parsed_data = hdl_parser.parse()
    except Exception as e:
        print(f"[ERROR] Failed to parse file: {e}")
        return

    print(f"[INFO] Successfully parsed module: {parsed_data.get('module_name')}")
    print(f"       Inputs: {len(parsed_data.get('inputs', []))}")
    print(f"       Outputs: {len(parsed_data.get('outputs', []))}")
    
    config = {
        'clock_name': args.clk_name,
        'frequency_mhz': args.clk_freq,
        'reset_name': args.rst_name,
        'auto_reset': True,
        'reset_delay_ns': args.rst_delay,
        'reset_active_low': True if args.rst_name.endswith('_n') else False
    }

    template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'tb_base.v')
    
    try:
        generator = TestbenchGenerator(template_path)
        tb_code = generator.generate(parsed_data, config)
    except Exception as e:
        print(f"[ERROR] Failed to generate testbench: {e}")
        return
        
    out_file = args.output
    if not out_file:
        out_file = f"tb_{parsed_data.get('module_name')}.v"

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(tb_code)

    print(f"[SUCCESS] Testbench generated: {out_file}")

if __name__ == "__main__":
    main()
