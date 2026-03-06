import os
import os
import sys
import glob
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, 
    QTextEdit, QFileDialog, QMessageBox, QSplitter, QGroupBox, QTabWidget,
    QListWidget, QListWidgetItem, QDialog, QDoubleSpinBox, QRadioButton
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

# Ensure src path is visible so we can import parser and generator
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.parser import get_parser
from src.generator.tb_generator import TestbenchGenerator


class GeneratorWorker(QThread):
    """Background worker so testbench generation never freezes the UI."""
    finished = Signal(str)   # emits generated code
    error = Signal(str)      # emits error message

    def __init__(self, template_path, parsed_data, config, parent=None):
        super().__init__(parent)
        self.template_path = template_path
        self.parsed_data = parsed_data
        self.config = config

    def run(self):
        try:
            generator = TestbenchGenerator(self.template_path)
            tb_code = generator.generate(self.parsed_data, self.config)
            self.finished.emit(tb_code)
        except Exception as e:
            self.error.emit(str(e))
from src.gui.waveform_widget import WaveformWidget
from src.gui.verilog_highlighter import VerilogHighlighter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoSafeX - TestBench Generator")
        self.setMinimumSize(900, 600)
        
        self.parsed_data = None
        self.template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'tb_base.v')

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Left Panel (Settings)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setAlignment(Qt.AlignTop)

        # 1. File Input Group
        file_group = QGroupBox("Design Input")
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select .v, .sv, or .vhd file...")
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(browse_btn)
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)

        # 2. Clock Settings Group
        clk_group = QGroupBox("Clock Configuration")
        clk_layout = QVBoxLayout()
        
        clk_name_layout = QHBoxLayout()
        clk_name_layout.addWidget(QLabel("Clock Name:"))
        self.clk_name_input = QLineEdit("clk")
        clk_name_layout.addWidget(self.clk_name_input)
        
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Frequency (MHz):"))
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.001, 10000.0)
        self.freq_spin.setValue(100.0)
        freq_layout.addWidget(self.freq_spin)
        
        duty_layout = QHBoxLayout()
        duty_layout.addWidget(QLabel("Duty Cycle (%):"))
        self.duty_spin = QDoubleSpinBox()
        self.duty_spin.setRange(1.0, 99.0)
        self.duty_spin.setValue(50.0)
        self.duty_spin.setSingleStep(5.0)
        duty_layout.addWidget(self.duty_spin)
        
        clk_layout.addLayout(clk_name_layout)
        clk_layout.addLayout(freq_layout)
        clk_layout.addLayout(duty_layout)
        clk_group.setLayout(clk_layout)
        left_layout.addWidget(clk_group)

        # 3. Reset Settings Group
        rst_group = QGroupBox("Reset Configuration")
        rst_layout = QVBoxLayout()
        
        self.auto_rst_cb = QCheckBox("Enable Auto Reset Sequence")
        self.auto_rst_cb.setChecked(True)
        
        rst_name_layout = QHBoxLayout()
        rst_name_layout.addWidget(QLabel("Reset Name:"))
        self.rst_name_input = QLineEdit("rst_n")
        rst_name_layout.addWidget(self.rst_name_input)
        
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Reset Delay (ns):"))
        self.rst_delay_spin = QDoubleSpinBox()
        self.rst_delay_spin.setRange(0.1, 100000.0)
        self.rst_delay_spin.setValue(100.0)
        delay_layout.addWidget(self.rst_delay_spin)
        
        polarity_layout = QHBoxLayout()
        polarity_layout.addWidget(QLabel("Active Polarity:"))
        self.radio_low = QRadioButton("Low (0)")
        self.radio_high = QRadioButton("High (1)")
        self.radio_low.setChecked(True)
        polarity_layout.addWidget(self.radio_low)
        polarity_layout.addWidget(self.radio_high)
        
        rst_layout.addWidget(self.auto_rst_cb)
        rst_layout.addLayout(rst_name_layout)
        rst_layout.addLayout(delay_layout)
        rst_layout.addLayout(polarity_layout)
        rst_group.setLayout(rst_layout)
        left_layout.addWidget(rst_group)

        # 4. Stimulus Settings Group
        stim_group = QGroupBox("Stimulus Configuration")
        stim_layout = QVBoxLayout()
        
        self.cb_random_stim = QCheckBox("Apply Random Stimulus")
        self.cb_random_stim.setChecked(True)
        self.cb_random_stim.stateChanged.connect(self.update_preview)
        
        stim_layout.addWidget(self.cb_random_stim)
        
        self.lib_layout = QVBoxLayout()
        self.lib_layout.addWidget(QLabel("Task Library (Select snippets):"))
        self.lib_list = QListWidget()
        self.lib_list.setMaximumHeight(100) # Keep it compact
        
        # Load available snippets from templates/tasks
        self.tasks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'templates', 'tasks')
        if os.path.exists(self.tasks_dir):
            snippets = [os.path.basename(f) for f in glob.glob(os.path.join(self.tasks_dir, "*.v"))]
            for snippet in snippets:
                item = QListWidgetItem(self.lib_list)
                checkbox = QCheckBox(snippet)
                self.lib_list.setItemWidget(item, checkbox)
                # NOTE: Do NOT connect stateChanged to update_preview; task selection doesn't affect waveform
        else:
            self.lib_list.addItem("None Available")
            
        self.lib_layout.addWidget(self.lib_list)
        
        # Add task description label
        self.task_desc_label = QLabel()
        self.task_desc_label.setWordWrap(True)
        self.task_desc_label.setStyleSheet("color: #888888; font-style: italic;")
        
        lib_v_layout = QVBoxLayout()
        lib_v_layout.addLayout(self.lib_layout)
        lib_v_layout.addWidget(self.task_desc_label)
        
        # The library layout widget
        self.lib_widget = QWidget()
        self.lib_widget.setLayout(lib_v_layout)
        # itemClicked fires when user clicks the row — use this to show description
        self.lib_list.itemClicked.connect(self.on_task_clicked)
        
        # Task Snippet Action Buttons
        btn_layout = QHBoxLayout()
        self.create_task_btn = QPushButton("Create")
        self.edit_task_btn = QPushButton("Edit")
        self.delete_task_btn = QPushButton("Delete")
        
        self.create_task_btn.clicked.connect(lambda: self.open_task_creator())
        self.edit_task_btn.clicked.connect(self.edit_task_snippet)
        self.delete_task_btn.clicked.connect(self.delete_task_snippet)
        
        btn_layout.addWidget(self.create_task_btn)
        btn_layout.addWidget(self.edit_task_btn)
        btn_layout.addWidget(self.delete_task_btn)
        lib_v_layout.addLayout(btn_layout)
        
        stim_layout.addWidget(self.lib_widget)
        
        # LLM API Key Input (Commented out for now)
        # self.api_key_layout = QHBoxLayout()
        # self.api_key_layout.addWidget(QLabel("LLM API Key (Optional):"))
        # self.api_key_input = QLineEdit()
        # self.api_key_input.setPlaceholderText("Enter OpenAI API Key for AI Tasks")
        # self.api_key_input.setEchoMode(QLineEdit.Password)
        # self.api_key_layout.addWidget(self.api_key_input)
        
        # self.api_widget = QWidget()
        # self.api_widget.setLayout(self.api_key_layout)
        # self.api_widget.setVisible(False)
        # stim_layout.addWidget(self.api_widget)
        
        stim_group.setLayout(stim_layout)
        left_layout.addWidget(stim_group)

        # Connect settings changes to preview update
        self.freq_spin.valueChanged.connect(self.update_preview)
        self.duty_spin.valueChanged.connect(self.update_preview)
        self.rst_delay_spin.valueChanged.connect(self.update_preview)
        self.rst_name_input.textChanged.connect(self.update_preview)
        self.radio_low.toggled.connect(self.update_preview)
        self.lib_list.itemClicked.connect(self.update_preview)

        # Add stretch so generate button stays at bottom
        left_layout.addStretch()

        # Generate Button
        self.generate_btn = QPushButton("Generate Testbench")
        self.generate_btn.setObjectName("generate_btn")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.clicked.connect(self.generate_code)
        left_layout.addWidget(self.generate_btn)


        # Right Panel (Tabs for Preview and Code)
        self.tabs = QTabWidget()
        
        # Tab 1: Waveform Preview
        self.waveform_widget = WaveformWidget()
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        
        # Descriptive text above waveform
        info_label = QLabel("<h4>Waveform Preview</h4>Live visual representation of Clock and Reset timing configurations.")
        info_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(info_label)
        preview_layout.addWidget(self.waveform_widget)
        preview_layout.addStretch()
        
        self.tabs.addTab(preview_container, "Preview")

        # Tab 2: Generated Code
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setPlaceholderText("Generated Verilog code will appear here...")
        self.code_highlighter = VerilogHighlighter(self.code_edit.document())
        
        code_container = QWidget()
        code_layout = QVBoxLayout(code_container)
        code_layout.setContentsMargins(0,0,0,0)
        
        toolbar_layout = QHBoxLayout()
        save_btn = QPushButton("Save to File")
        save_btn.clicked.connect(self.save_file)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(save_btn)
        
        code_layout.addLayout(toolbar_layout)
        code_layout.addWidget(self.code_edit)
        
        # Add Search Bar layout to Output Tab
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in testbench...")
        search_btn = QPushButton("Find Next")
        search_btn.clicked.connect(self.find_text_in_output)
        self.search_input.returnPressed.connect(self.find_text_in_output)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_btn)
        code_layout.addLayout(search_layout)
        
        self.tabs.addTab(code_container, "Verilog Output")
        
        # Tab 3: Design Source Code
        self.source_edit = QTextEdit()
        self.source_edit.setReadOnly(True)
        self.source_edit.setPlaceholderText("Design source code will appear here after parsing...")
        self.source_highlighter = VerilogHighlighter(self.source_edit.document())
        self.tabs.addTab(self.source_edit, "Design Source")

        # Tab 4: Template Editor
        self.template_edit = QTextEdit()
        # Load content from template file
        if os.path.exists(self.template_path):
            with open(self.template_path, 'r', encoding='utf-8') as f:
                self.template_edit.setPlainText(f.read())
                
        template_container = QWidget()
        template_layout = QVBoxLayout(template_container)
        template_layout.setContentsMargins(0,0,0,0)
        
        tpl_toolbar_layout = QHBoxLayout()
        # Button: Edit Task Snippet instead
        edit_snippets_btn = QPushButton("Refresh Library/Save Task Snippet")
        edit_snippets_btn.clicked.connect(self.refresh_and_save_snippet)
        save_tpl_btn = QPushButton("Save Base Template")
        save_tpl_btn.clicked.connect(self.save_template)
        tpl_toolbar_layout.addWidget(edit_snippets_btn)
        tpl_toolbar_layout.addStretch()
        tpl_toolbar_layout.addWidget(save_tpl_btn)
        
        template_layout.addLayout(tpl_toolbar_layout)
        
        # self.tabs.addTab(template_container, "Template Editor")  # Hidden per user request

        # Splitter to adjust panel sizes
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3) # Give right panel more space

        main_layout.addWidget(splitter)
        
        # Initial update of waveform preview
        self.update_preview()
        if self.lib_list.count() > 0:
            self.on_task_clicked(self.lib_list.item(0))

    def on_stim_type_changed(self, text):
        pass # Deprecated, logic handled by checkboxes now
            
        self.update_preview()
        
    def on_task_clicked(self, item):
        if not item:
            self.task_desc_label.setText("")
            return
            
        checkbox = self.lib_list.itemWidget(item)
        if not checkbox:
            return
            
        task_name = checkbox.text()
        if task_name == "None Available":
            self.task_desc_label.setText("")
            return
            
        task_path = os.path.join(self.tasks_dir, task_name)
        if os.path.exists(task_path):
            try:
                with open(task_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    description = []
                    # Read consecutive comment lines at the top
                    for line in lines:
                        if line.startswith("//"):
                            # Skip separator lines
                            if "=====" in line or "----" in line:
                                continue
                            clean = line.strip().strip("//").strip()
                            if clean:
                                description.append(clean)
                        elif not line.strip(): # blank line
                            continue
                        else:
                            break # stop at first code line
                    if description:
                        self.task_desc_label.setText("\n".join(description))
                    else:
                        self.task_desc_label.setText("No description provided in this snippet.")
            except:
                self.task_desc_label.setText("Failed to load snippet description.")
        else:
            self.task_desc_label.setText("")

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Design File", "", "HDL Files (*.v *.sv *.vhd *.vhdl);;All Files (*)"
        )
        if file_path:
            self.file_input.setText(file_path)
            # Load the source code into the new tab
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.source_edit.setPlainText(f.read())
            except Exception as e:
                self.source_edit.setPlainText(f"Could not load source file:\n{str(e)}")
                
            # Auto parse to check if valid
            try:
                parser = get_parser(file_path)
                self.parsed_data = parser.parse()
                QMessageBox.information(
                    self, "Success", 
                    f"Successfully parsed module: {self.parsed_data.get('module_name')}\n"
                    f"Inputs: {len(self.parsed_data.get('inputs', []))}\n"
                    f"Outputs: {len(self.parsed_data.get('outputs', []))}"
                )
            except Exception as e:
                self.parsed_data = None
                QMessageBox.critical(self, "Error", f"Failed to parse file:\n{str(e)}")
            self.update_preview()

    def update_preview(self):
        # Update the waveform widget based on current UI settings
        input_sigs = None
        if self.parsed_data:
            input_sigs = self.parsed_data.get('inputs', [])
            
        self.waveform_widget.update_params(
            clock_freq=self.freq_spin.value(),
            duty_cycle=self.duty_spin.value(),
            reset_delay=self.rst_delay_spin.value(),
            reset_name=self.rst_name_input.text(),
            active_low=self.radio_low.isChecked(),
            input_signals=input_sigs,
            clock_name=self.clk_name_input.text()
        )

    def get_selected_tasks(self):
        selected = []
        for i in range(self.lib_list.count()):
            item = self.lib_list.item(i)
            checkbox = self.lib_list.itemWidget(item)
            if checkbox and checkbox.isChecked():
                selected.append(checkbox.text())
        return selected

    def generate_code(self):
        if not self.parsed_data:
            QMessageBox.warning(self, "Warning", "Please select a valid design file first.")
            return

        config = {
            'clock_name': self.clk_name_input.text(),
            'frequency_mhz': self.freq_spin.value(),
            'duty_cycle': self.duty_spin.value(),
            'reset_name': self.rst_name_input.text(),
            'auto_reset': self.auto_rst_cb.isChecked(),
            'reset_delay_ns': self.rst_delay_spin.value(),
            'reset_active_low': self.radio_low.isChecked(),
            'enable_random': self.cb_random_stim.isChecked(),
            'library_tasks': self.get_selected_tasks()
        }

        # Disable button and show progress while running in background thread
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")

        self._worker = GeneratorWorker(self.template_path, self.parsed_data, config, parent=self)
        self._worker.finished.connect(self._on_generation_done)
        self._worker.error.connect(self._on_generation_error)
        self._worker.start()

    def _on_generation_done(self, tb_code):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Testbench")
        self.code_edit.setPlainText(tb_code)
        self.tabs.setCurrentIndex(1)

    def _on_generation_error(self, err_msg):
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Testbench")
        QMessageBox.critical(self, "Error", f"Failed to generate testbench:\n{err_msg}")

    def save_file(self):
        tb_code = self.code_edit.toPlainText()
        if not tb_code:
            return
            
        default_name = f"tb_{self.parsed_data.get('module_name', 'unknown')}.v" if self.parsed_data else "tb_out.v"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Testbench", default_name, "Verilog Files (*.v);;All Files (*)"
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(tb_code)
                QMessageBox.information(self, "Saved", f"File saved to:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{str(e)}")
                
    def find_text_in_output(self):
        query = self.search_input.text()
        if not query:
            self.code_edit.setExtraSelections([])
            return
            
        # find(query) returns True if found and highlights it natively, but we can make it more visible
        found = self.code_edit.find(query)
        
        if not found:
            # If not found from current cursor, wrap around and search from start
            self.code_edit.moveCursor(QTextCursor.Start)
            found = self.code_edit.find(query)
            
        if found:
            selection = QTextEdit.ExtraSelection()
            format = QTextCharFormat()
            format.setBackground(QColor("#d19a66"))  # Vibrant orange background
            format.setForeground(QColor("#282c34"))  # Dark text
            selection.format = format
            selection.cursor = self.code_edit.textCursor()
            self.code_edit.setExtraSelections([selection])
        else:
            self.code_edit.setExtraSelections([])
            QMessageBox.information(self, "Search", f"Cannot find '{query}'.")

    def save_template(self):
        tpl_code = self.template_edit.toPlainText()
        try:
            with open(self.template_path, 'w', encoding='utf-8') as f:
                f.write(tpl_code)
            QMessageBox.information(self, "Saved", "Template has been successfully updated!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save template:\n{str(e)}")

    def refresh_and_save_snippet(self):
        # We can write the currently viewed snippet or just reload the dropdown
        if os.path.exists(self.tasks_dir):
            snippets = [os.path.basename(f) for f in glob.glob(os.path.join(self.tasks_dir, "*.v"))]
            self.lib_list.clear()
            if snippets:
                for snippet in snippets:
                    item = QListWidgetItem(self.lib_list)
                    checkbox = QCheckBox(snippet)
                    self.lib_list.setItemWidget(item, checkbox)
                    checkbox.stateChanged.connect(self.update_preview)
                    checkbox.clicked.connect(lambda checked, i=item: self.on_task_clicked(i))
            else:
                self.lib_list.addItem("None Available")
        QMessageBox.information(self, "Refreshed", "Task library snippets reloaded!")
        
    def get_single_selected_task(self):
        tasks = self.get_selected_tasks()
        if len(tasks) != 1:
            QMessageBox.warning(self, "Selection Error", "Please check exactly ONE task snippet checkbox to Edit or Delete.")
            return None
        return tasks[0]

    def edit_task_snippet(self):
        task_name = self.get_single_selected_task()
        if task_name:
            self.open_task_creator(task_name)

    def delete_task_snippet(self):
        task_name = self.get_single_selected_task()
        if not task_name:
            return
            
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete '{task_name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                os.remove(os.path.join(self.tasks_dir, task_name))
                self.refresh_and_save_snippet()
                QMessageBox.information(self, "Deleted", f"'{task_name}' has been deleted.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete file:\n{str(e)}")

    def open_task_creator(self, edit_file_name=None):
        from src.gui.verilog_highlighter import VerilogHighlighter
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Task Snippet" if edit_file_name else "Create Task Snippet")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)
        
        # FileName input
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Snippet File Name:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., custom_axi_task.v")
        file_layout.addWidget(name_input)
        layout.addLayout(file_layout)
        
        # Code Editor
        layout.addWidget(QLabel("Task Code (Verilog):"))
        code_input = QTextEdit()
        code_input.setPlaceholderText("// A brief description of what this task does\n\ntask my_task;\n    input [7:0] my_data;\nbegin\n    // ... sequence ...\nend\nendtask")
        
        # Prepopulate if editing
        if edit_file_name:
            name_input.setText(edit_file_name)
            name_input.setReadOnly(True)  # Prevent renaming while editing to avoid detachment
            file_path = os.path.join(self.tasks_dir, edit_file_name)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        code_input.setPlainText(f.read())
                except Exception as e:
                    QMessageBox.warning(dialog, "Error", f"Could not load file contents:\n{str(e)}")
        highlighter = VerilogHighlighter(code_input.document()) # Apply syntax highlighting here too
        layout.addWidget(code_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        save_btn = QPushButton("Save Snippet")
        
        def save_snippet():
            file_name = name_input.text().strip()
            code = code_input.toPlainText().strip()
            
            if not file_name:
                QMessageBox.warning(dialog, "Error", "Please provide a file name.")
                return
            if not file_name.endswith('.v'):
                file_name += '.v'
            if not code:
                QMessageBox.warning(dialog, "Error", "Task code cannot be empty.")
                return
                
            os.makedirs(self.tasks_dir, exist_ok=True)
            save_path = os.path.join(self.tasks_dir, file_name)
            
            if os.path.exists(save_path):
                reply = QMessageBox.question(dialog, "Overwrite?", f"'{file_name}' already exists. Overwrite?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    return
            
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                QMessageBox.information(dialog, "Saved", f"Task snippet '{file_name}' saved successfully!")
                self.refresh_and_save_snippet() # Reload library list
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Could not save file:\n{str(e)}")
                
        save_btn.clicked.connect(save_snippet)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()
