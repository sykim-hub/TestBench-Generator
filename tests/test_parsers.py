import unittest
from src.parser.verilog_parser import VerilogParser
from src.parser.vhdl_parser import VHDLParser

import os
import tempfile

class TestHDLParsers(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()
        
    def test_verilog_parser(self):
        v_code = """
        module my_adder (
            input wire [7:0] a,
            input wire [7:0] b,
            input wire clk,
            output reg [8:0] sum
        );
        endmodule
        """
        file_path = os.path.join(self.test_dir.name, 'test_adder.v')
        with open(file_path, 'w') as f:
            f.write(v_code)
            
        parser = VerilogParser(file_path)
        result = parser.parse()
        
        self.assertEqual(result['module_name'], 'my_adder')
        self.assertEqual(len(result['inputs']), 3)
        self.assertEqual(len(result['outputs']), 1)
        
        input_names = [i['name'] for i in result['inputs']]
        self.assertIn('a', input_names)
        self.assertIn('clk', input_names)
        
    def test_vhdl_parser(self):
        vhdl_code = """
        entity my_counter is
            Port ( clk, rst : in STD_LOGIC;
                   enable : in STD_LOGIC;
                   count : out STD_LOGIC_VECTOR (3 downto 0));
        end my_counter;
        """
        file_path = os.path.join(self.test_dir.name, 'test_counter.vhd')
        with open(file_path, 'w') as f:
            f.write(vhdl_code)
            
        parser = VHDLParser(file_path)
        result = parser.parse()
        
        self.assertEqual(result['module_name'], 'my_counter')
        self.assertEqual(len(result['inputs']), 3)
        self.assertEqual(len(result['outputs']), 1)
        
        input_names = [i['name'] for i in result['inputs']]
        self.assertIn('clk', input_names)
        self.assertIn('rst', input_names)
        self.assertIn('enable', input_names)

if __name__ == '__main__':
    unittest.main()
