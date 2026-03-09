# update plan

## main GUI

- shall set the window title to "TestBench Generator" without AutoSafeX
- shall set the window size to 800x600 is default but possible to fit the content ratio if user changes the window size.
- shall set the default tab to "Generated TestBenches" tab, not the "Verilog Output" tab.
- shall be able to set the testbench name in the interface panel, and the name will be used as the file name of the generated testbench.
- Generate Testbench button is not necessary, the testbench shall be generated automatically when the user clicks or inputs the any button in the interface panel.
- stimulus clocks and resets are not only one, but current this app is only supporting one clock and one reset. shall support multiple clocks and resets. in that case, the user shall be able to add or remove the stimulus clocks and resets in the interface panel and which dut port is connected to the stimulus clock or reset shall be selected in the interface panel.
- current Task library is only generating the example purpose, not actually possible to connect to the dut ports.
- "Apply Random Stimulus" in the Stimulus configuration panel is not necessary. we need user defined task as various way to stimulate the dut. the user task shall be also not only one. 
- the user's tasks and library tasks shall be able to be called at main task or control as fork join or fork join_any or fork join_none at the main inital begin end block.
- "Design Source" tab name shall be "DUT top" 

## 