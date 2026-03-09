# -*- coding: utf-8 -*-
import os
import sys
import glob
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QTextEdit, QFileDialog, QMessageBox, QSplitter, QGroupBox,
    QTabWidget, QListWidget, QListWidgetItem, QDialog,
    QDoubleSpinBox, QRadioButton, QScrollArea, QFrame,
    QStyle, QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QIcon

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.parser import get_parser
from src.generator.tb_generator import TestbenchGenerator


# ─── helpers ──────────────────────────────────────────────────────────────────

def _trash_icon() -> QIcon:
    """Return the OS standard trash / delete icon."""
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)


def _make_scrollable(inner: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(inner)
    sa.setFrameShape(QFrame.NoFrame)
    return sa


# ─── Background worker ────────────────────────────────────────────────────────

class GeneratorWorker(QThread):
    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, template_path, parsed_data, config, parent=None):
        super().__init__(parent)
        self.template_path = template_path
        self.parsed_data   = parsed_data
        self.config        = config

    def run(self):
        try:
            gen     = TestbenchGenerator(self.template_path)
            tb_code = gen.generate(self.parsed_data, self.config)
            self.finished.emit(tb_code)
        except Exception as e:
            self.error.emit(str(e))


from src.gui.waveform_widget import WaveformWidget
from src.gui.verilog_highlighter import VerilogHighlighter


# ─── Clock Entry Widget ───────────────────────────────────────────────────────

class ClockEntryWidget(QFrame):
    removed = Signal(object)
    changed = Signal()

    def __init__(self, port_list=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("clockEntry")

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(4)

        # ── header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._title = QLabel("Clock")
        self._title.setStyleSheet("font-weight: bold; color: #6a82ff;")
        btn_rm = QPushButton()
        btn_rm.setIcon(_trash_icon())
        btn_rm.setIconSize(QSize(14, 14))
        btn_rm.setFixedSize(24, 24)
        btn_rm.setToolTip("Remove this clock")
        btn_rm.setFlat(True)
        btn_rm.clicked.connect(lambda: self.removed.emit(self))
        hdr.addWidget(self._title)
        hdr.addStretch()
        hdr.addWidget(btn_rm)
        root.addLayout(hdr)

        # ── name + port ──────────────────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit("clk")
        self.name_input.setMaximumWidth(75)
        row1.addWidget(self.name_input)
        row1.addWidget(QLabel("DUT Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port_combo.setToolTip("Which DUT port driven by this clock (all port types shown)")
        self.port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1.addWidget(self.port_combo, stretch=1)
        root.addLayout(row1)

        # ── freq (50 % duty fixed) ───────────────────────────────────────────
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Freq (MHz):"))
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.001, 10000.0)
        self.freq_spin.setValue(100.0)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.freq_spin.setMaximumWidth(100)
        row2.addWidget(self.freq_spin)
        row2.addWidget(QLabel("MHz   (50% duty)"))
        row2.addStretch()
        root.addLayout(row2)

        if port_list:
            self.set_port_list(port_list)

        self.name_input.textChanged.connect(self._on_changed)
        self.port_combo.currentTextChanged.connect(self._on_changed)
        self.freq_spin.valueChanged.connect(self._on_changed)

    def _on_changed(self):
        self._title.setText(f"Clock: {self.name_input.text()}")
        self.changed.emit()

    def set_port_list(self, ports):
        cur = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItems(["(none)"] + ports)
        idx = self.port_combo.findText(cur)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)
        else:
            # Auto-match by tb signal name
            auto = self.port_combo.findText(self.name_input.text())
            if auto > 0:
                self.port_combo.setCurrentIndex(auto)
        self.port_combo.blockSignals(False)

    def get_config(self):
        port = self.port_combo.currentText()
        name = self.name_input.text().strip() or 'clk'
        return {
            'name': name,
            'frequency_mhz': self.freq_spin.value(),
            'duty_cycle':    50.0,   # always 50 %
            'port': port if port != "(none)" else name,
        }


# ─── Reset Entry Widget ───────────────────────────────────────────────────────

class ResetEntryWidget(QFrame):
    removed = Signal(object)
    moved_up = Signal(object)
    moved_down = Signal(object)
    changed = Signal()

    def __init__(self, port_list=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("resetEntry")

        # internal transition state
        self._init_val  = '0'
        self._final_val = '1'

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(4)

        # ── header: title + move up/down + trash ──────────────────────────────
        hdr = QHBoxLayout()
        self._title = QLabel("Signal")
        self._title.setStyleSheet("font-weight: bold; color: #ff8c6a;")

        btn_up = QPushButton()
        btn_up.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        btn_up.setFixedSize(24, 24)
        btn_up.setToolTip("Move up")
        btn_up.clicked.connect(lambda: self.moved_up.emit(self))

        btn_down = QPushButton()
        btn_down.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        btn_down.setFixedSize(24, 24)
        btn_down.setToolTip("Move down")
        btn_down.clicked.connect(lambda: self.moved_down.emit(self))

        btn_rm = QPushButton()
        btn_rm.setIcon(_trash_icon())
        btn_rm.setIconSize(QSize(14, 14))
        btn_rm.setFixedSize(24, 24)
        btn_rm.setToolTip("Remove this entry")
        btn_rm.setFlat(True)
        btn_rm.clicked.connect(lambda: self.removed.emit(self))

        hdr.addWidget(self._title)
        hdr.addStretch()
        hdr.addWidget(btn_up)
        hdr.addWidget(btn_down)
        hdr.addWidget(btn_rm)
        root.addLayout(hdr)


        # ── name + port ───────────────────────────────────────────────
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit("rst_n")
        self.name_input.setMaximumWidth(75)
        row1.addWidget(self.name_input)
        row1.addWidget(QLabel("DUT Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port_combo.setToolTip("Which DUT port driven by this signal (all port types shown)")
        self.port_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row1.addWidget(self.port_combo, stretch=1)
        root.addLayout(row1)

        # ── Transition toggle + delay + reference ────────────────────────────
        row2 = QHBoxLayout()

        # Single-click toggle button for transition direction
        self.trans_btn = QPushButton("0 → 1")
        self.trans_btn.setFixedWidth(64)
        self.trans_btn.setToolTip(
            "Click to flip the transition direction.\n"
            "0→1: signal starts LOW, goes HIGH at the given time\n"
            "1→0: signal starts HIGH, goes LOW at the given time"
        )
        self.trans_btn.setStyleSheet(
            "QPushButton { background:#1e2d40; color:#6af0aa; border:1px solid #2e4a60;"
            " border-radius:4px; font-weight:bold; padding:2px 4px; }"
            "QPushButton:hover { background:#26384d; }"
        )
        self.trans_btn.clicked.connect(self._flip_transition)
        row2.addWidget(self.trans_btn)

        row2.addWidget(QLabel("after"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.0, 100000.0)
        self.delay_spin.setValue(100.0)
        self.delay_spin.setDecimals(1)
        self.delay_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.delay_spin.setMaximumWidth(72)
        row2.addWidget(self.delay_spin)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["ns", "cycles"])
        row2.addWidget(self.unit_combo)

        self.clock_combo = QComboBox()
        self.clock_combo.setVisible(False)
        self.clock_combo.setToolTip("Select reference clock for cycles")
        row2.addWidget(self.clock_combo)

        row2.addStretch()
        root.addLayout(row2)

        row3 = QHBoxLayout()
        self.chk_parallel = QCheckBox("Parallel (bundle with adjacent checked cards)")
        self.chk_parallel.setToolTip(
            "If checked on 2 or more adjacent cards, they will be bundled together\n"
            "into a single fork…join block."
        )
        row3.addWidget(self.chk_parallel)
        row3.addStretch()
        root.addLayout(row3)

        if port_list:
            self.set_port_list(port_list)

        # Connections
        self.name_input.textChanged.connect(self._on_changed)
        self.port_combo.currentTextChanged.connect(self._on_changed)
        self.delay_spin.valueChanged.connect(self._on_changed)
        self.chk_parallel.stateChanged.connect(self._on_changed)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        self.clock_combo.currentTextChanged.connect(self._on_changed)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _on_unit_changed(self, text):
        if text == "cycles":
            self.clock_combo.setVisible(True)
            self.delay_spin.setDecimals(0)
        else:
            self.clock_combo.setVisible(False)
            self.delay_spin.setDecimals(1)
        self._on_changed()

    def _flip_transition(self):
        """One click: swap init↔final."""
        if self._init_val == '0':
            self._init_val, self._final_val = '1', '0'
        else:
            self._init_val, self._final_val = '0', '1'
        self.trans_btn.setText(f"{self._init_val} → {self._final_val}")
        self._on_changed()

    def _on_changed(self):
        name = self.name_input.text()
        self._title.setText(f"Signal: {name}  ({self._init_val}→{self._final_val})")
        self.changed.emit()

    # ── port list ─────────────────────────────────────────────────────────────

    def set_port_list(self, ports):
        cur = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItems(["(none)"] + ports)
        idx = self.port_combo.findText(cur)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)
        else:
            auto = self.port_combo.findText(self.name_input.text())
            if auto > 0:
                self.port_combo.setCurrentIndex(auto)
        self.port_combo.blockSignals(False)

    def set_clock_list(self, clocks):
        cur = self.clock_combo.currentText()
        self.clock_combo.blockSignals(True)
        self.clock_combo.clear()
        self.clock_combo.addItems(clocks)
        idx = self.clock_combo.findText(cur)
        if idx >= 0:
            self.clock_combo.setCurrentIndex(idx)
        self.clock_combo.blockSignals(False)

    def get_config(self):
        port = self.port_combo.currentText()
        name = self.name_input.text().strip() or 'rst_n'
        return {
            'name':      name,
            'sig_type':  'Signal',   # type_combo removed; kept for generator compat
            'init_val':  self._init_val,
            'final_val': self._final_val,
            'delay_ns':  self.delay_spin.value(),
            'delay_unit': self.unit_combo.currentText(),
            'delay_clock': self.clock_combo.currentText() or 'clk',
            'auto':      True,
            'timing':    'parallel' if self.chk_parallel.isChecked() else 'sequential',
            'port':      port if port not in ('', '(none)') else name,
        }


# ─── Task Sequence Entry Widget ───────────────────────────────────────────────

class TaskSeqEntryWidget(QFrame):
    """One row in the task-call sequence: [task combo] [fork type combo] [trash]"""
    removed = Signal(object)
    changed = Signal()

    FORK_TYPES = [
        "sequential",
        "fork...join",
        "fork...join_any",
        "fork...join_none",
    ]

    def __init__(self, task_files=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(4)

        self.task_combo = QComboBox()
        self.task_combo.setToolTip("Task to call")
        if task_files:
            self.task_combo.addItems(task_files)
        lay.addWidget(self.task_combo, stretch=2)

        self.fork_combo = QComboBox()
        self.fork_combo.addItems(self.FORK_TYPES)
        self.fork_combo.setToolTip(
            "sequential  → called one after another\n"
            "fork…join   → parallel, wait for all\n"
            "fork…join_any → parallel, wait for first\n"
            "fork…join_none → fire-and-forget"
        )
        lay.addWidget(self.fork_combo, stretch=1)

        btn_rm = QPushButton()
        btn_rm.setIcon(_trash_icon())
        btn_rm.setIconSize(QSize(14, 14))
        btn_rm.setFixedSize(24, 24)
        btn_rm.setToolTip("Remove this task call")
        btn_rm.setFlat(True)
        btn_rm.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(btn_rm)

        self.task_combo.currentTextChanged.connect(lambda _: self.changed.emit())
        self.fork_combo.currentTextChanged.connect(lambda _: self.changed.emit())

    def set_task_files(self, files):
        cur = self.task_combo.currentText()
        self.task_combo.blockSignals(True)
        self.task_combo.clear()
        self.task_combo.addItems(files)
        idx = self.task_combo.findText(cur)
        if idx >= 0:
            self.task_combo.setCurrentIndex(idx)
        self.task_combo.blockSignals(False)

    def get_config(self):
        return {
            'task_file':  self.task_combo.currentText(),
            'fork_type':  self.fork_combo.currentText(),
        }


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TestBench Generator")
        self.resize(1280, 720)

        self.parsed_data   = None
        self.template_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'templates', 'tb_base.v'
        )
        self.tasks_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'tasks'
        )

        # Debounce timer for auto-generation
        self._regen_timer = QTimer(self)
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(600)
        self._regen_timer.timeout.connect(self._auto_generate)

        # ── Root layout ──────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QHBoxLayout(central)
        root_lay.setContentsMargins(8, 8, 8, 8)
        root_lay.setSpacing(8)

        # ────────────────────────────────────────────────────────────────────
        # LEFT PANEL
        # ────────────────────────────────────────────────────────────────────
        left_outer = QWidget()
        left_outer.setMinimumWidth(320)
        left_top_lay = QVBoxLayout(left_outer)
        left_top_lay.setContentsMargins(0, 0, 0, 0)
        left_top_lay.setSpacing(6)

        # 0a. File Input ──────────────────────────────────────────────────────
        file_group = QGroupBox("Design Input")
        fg_lay = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select .v / .sv / .vhd …")
        self.file_input.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self.browse_file)
        fg_lay.addWidget(self.file_input)
        fg_lay.addWidget(browse_btn)
        file_group.setLayout(fg_lay)
        left_top_lay.addWidget(file_group)

        # 0b. Testbench Name ──────────────────────────────────────────────────
        tb_group = QGroupBox("Testbench Name")
        tb_lay = QHBoxLayout()
        self.tb_name_input = QLineEdit()
        self.tb_name_input.setPlaceholderText("e.g. tb_my_dut  (also used as file name)")
        self.tb_name_input.textChanged.connect(self._schedule_regen)
        tb_lay.addWidget(self.tb_name_input)
        tb_group.setLayout(tb_lay)
        left_top_lay.addWidget(tb_group)

        # ── Left Tab Widget ──────────────────────────────────────────────────
        self._left_tabs = QTabWidget()
        self._left_tabs.setTabPosition(QTabWidget.North)
        left_top_lay.addWidget(self._left_tabs, stretch=1)

        # ── TAB A: Clocks & Resets ───────────────────────────────────────────
        cr_scroll_inner = QWidget()
        cr_scroll_inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self._cr_layout = QVBoxLayout(cr_scroll_inner)
        self._cr_layout.setContentsMargins(4, 4, 4, 4)
        self._cr_layout.setSpacing(6)
        self._cr_layout.setAlignment(Qt.AlignTop)

        # Clock sub-group
        clk_box = QGroupBox("Clocks")
        clk_box_lay = QVBoxLayout(clk_box)
        clk_box_lay.setSpacing(4)
        self._clock_entries: list[ClockEntryWidget] = []
        self._clk_container = QWidget()
        self._clk_cont_lay  = QVBoxLayout(self._clk_container)
        self._clk_cont_lay.setContentsMargins(0, 0, 0, 0)
        self._clk_cont_lay.setSpacing(4)
        clk_box_lay.addWidget(self._clk_container)
        add_clk_btn = QPushButton("＋ Add Clock")
        add_clk_btn.clicked.connect(lambda: self._add_clock())
        clk_box_lay.addWidget(add_clk_btn)
        self._cr_layout.addWidget(clk_box)

        # Reset sub-group
        rst_box = QGroupBox("Resets or Level control")
        rst_box_lay = QVBoxLayout(rst_box)
        rst_box_lay.setSpacing(4)
        self._reset_entries: list[ResetEntryWidget] = []
        self._rst_container = QWidget()
        self._rst_cont_lay  = QVBoxLayout(self._rst_container)
        self._rst_cont_lay.setContentsMargins(0, 0, 0, 0)
        self._rst_cont_lay.setSpacing(4)
        rst_box_lay.addWidget(self._rst_container)

        add_rst_btn = QPushButton("＋ Add control")
        add_rst_btn.clicked.connect(lambda: self._add_reset())
        rst_box_lay.addWidget(add_rst_btn)
        self._cr_layout.addWidget(rst_box)

        cr_scroll = _make_scrollable(cr_scroll_inner)
        self._left_tabs.addTab(cr_scroll, "Clocks && Resets")

        # ── TAB B: Tasks ─────────────────────────────────────────────────────
        task_scroll_inner = QWidget()
        task_scroll_inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        task_lay = QVBoxLayout(task_scroll_inner)
        task_lay.setContentsMargins(4, 4, 4, 4)
        task_lay.setSpacing(6)
        task_lay.setAlignment(Qt.AlignTop)

        # Library sub-group
        lib_box = QGroupBox("Task Library")
        lib_box_lay = QVBoxLayout(lib_box)
        lib_box_lay.setSpacing(4)

        self.lib_list = QListWidget()
        self.lib_list.setMaximumHeight(100)
        self.lib_list.itemClicked.connect(self.on_task_clicked)
        lib_box_lay.addWidget(self.lib_list)

        lib_btn_row = QHBoxLayout()
        for label, slot in [("Create", lambda: self.open_task_creator()),
                             ("Edit",   self.edit_task_snippet),
                             ("Delete", self.delete_task_snippet)]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            lib_btn_row.addWidget(b)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._reload_task_library)
        lib_btn_row.addWidget(refresh_btn)
        lib_box_lay.addLayout(lib_btn_row)

        self.task_desc_label = QLabel()
        self.task_desc_label.setWordWrap(True)
        self.task_desc_label.setStyleSheet("color: #888; font-style: italic;")
        lib_box_lay.addWidget(self.task_desc_label)
        task_lay.addWidget(lib_box)

        # Sequence sub-group
        seq_box = QGroupBox("Task Sequence  (task → execution type)")
        seq_box_lay = QVBoxLayout(seq_box)
        seq_box_lay.setSpacing(3)

        hint = QLabel(
            "Consecutive rows with the same fork type are grouped into\n"
            "a single fork block — tasks run in parallel inside it."
        )
        hint.setStyleSheet("color: #7a8aaa; font-size: 9pt;")
        hint.setWordWrap(True)
        seq_box_lay.addWidget(hint)

        self._task_seq_entries: list[TaskSeqEntryWidget] = []
        self._seq_container = QWidget()
        self._seq_cont_lay  = QVBoxLayout(self._seq_container)
        self._seq_cont_lay.setContentsMargins(0, 0, 0, 0)
        self._seq_cont_lay.setSpacing(3)
        seq_box_lay.addWidget(self._seq_container)

        add_seq_btn = QPushButton("＋ Add Task Call")
        add_seq_btn.clicked.connect(self._add_task_seq_entry)
        seq_box_lay.addWidget(add_seq_btn)
        task_lay.addWidget(seq_box)

        task_scroll = _make_scrollable(task_scroll_inner)
        self._left_tabs.addTab(task_scroll, "Tasks")

        # ────────────────────────────────────────────────────────────────────
        # RIGHT PANEL (tabs)
        # ────────────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()

        # Waveform Preview
        self.waveform_widget = WaveformWidget()
        prev_w = QWidget()
        prev_lay = QVBoxLayout(prev_w)
        info_lbl = QLabel("<h4>Waveform Preview</h4>Live clock & reset timing based on configuration.")
        info_lbl.setAlignment(Qt.AlignCenter)
        prev_lay.addWidget(info_lbl)
        
        wave_scroll = _make_scrollable(self.waveform_widget)
        prev_lay.addWidget(wave_scroll)
        self.tabs.addTab(prev_w, "Preview")

        # Generated TestBenches
        self.code_edit = QTextEdit()
        self.code_edit.setReadOnly(True)
        self.code_edit.setPlaceholderText(
            "Generated SystemVerilog testbench will appear here automatically\n"
            "once a design file is loaded…"
        )
        self.code_highlighter = VerilogHighlighter(self.code_edit.document())

        code_w = QWidget()
        code_lay = QVBoxLayout(code_w)
        code_lay.setContentsMargins(0, 0, 0, 0)
        tb_bar = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setObjectName("autoSaveLabel")
        tb_bar.addWidget(self._status_label)
        tb_bar.addStretch()
        save_btn = QPushButton("Save to File…")
        save_btn.clicked.connect(self.save_file)
        tb_bar.addWidget(save_btn)
        code_lay.addLayout(tb_bar)
        code_lay.addWidget(self.code_edit)

        srch_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search in testbench…")
        find_btn = QPushButton("Find Next")
        find_btn.clicked.connect(self.find_text_in_output)
        self.search_input.returnPressed.connect(self.find_text_in_output)
        srch_bar.addWidget(QLabel("Search:"))
        srch_bar.addWidget(self.search_input)
        srch_bar.addWidget(find_btn)
        code_lay.addLayout(srch_bar)

        self.tabs.addTab(code_w, "Generated TestBenches")

        # DUT Top
        self.source_edit = QTextEdit()
        self.source_edit.setReadOnly(True)
        self.source_edit.setPlaceholderText("Design source code will appear here after parsing…")
        self.source_highlighter = VerilogHighlighter(self.source_edit.document())
        self.tabs.addTab(self.source_edit, "DUT top")

        # Default to Generated TestBenches tab
        self.tabs.setCurrentIndex(1)

        # Splitter – left panel wider by default, both sides freely resizable
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_outer)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([520, 740])   # initial pixel widths (sum ≈ window width)
        root_lay.addWidget(splitter)

        # Defaults
        self._add_clock()
        self._add_reset()
        self._reload_task_library()
        self.update_preview()

    # ─── Clock / Reset helpers ────────────────────────────────────────────────

    def _all_port_names(self):
        """Return every DUT port name (inputs + outputs + inouts) for the combo boxes."""
        if not self.parsed_data:
            return []
        ports = []
        for key in ('inputs', 'outputs', 'inouts'):
            ports.extend(p['name'] for p in self.parsed_data.get(key, []))
        return ports

    def _add_clock(self):
        e = ClockEntryWidget(self._all_port_names(), self)
        e.removed.connect(self._remove_clock)
        e.changed.connect(self.update_preview)
        e.changed.connect(self._schedule_regen)
        e.changed.connect(self._refresh_port_selectors)
        self._clock_entries.append(e)
        self._clk_cont_lay.addWidget(e)
        self._refresh_port_selectors()
        self._schedule_regen()

    def _remove_clock(self, e):
        if len(self._clock_entries) <= 1:
            QMessageBox.information(self, "Info", "At least one clock is required.")
            return
        self._clock_entries.remove(e)
        self._clk_cont_lay.removeWidget(e)
        e.deleteLater()
        self._refresh_port_selectors()
        self._schedule_regen()

    def _get_reset_entries(self):
        return self._reset_entries

    def _add_reset(self):
        e = ResetEntryWidget(self._all_port_names(), self)
        e.removed.connect(self._remove_reset)
        e.moved_up.connect(self._move_reset_up)
        e.moved_down.connect(self._move_reset_down)
        e.changed.connect(self._schedule_regen)
        self._reset_entries.append(e)
        self._rst_cont_lay.addWidget(e)
        self._refresh_port_selectors()
        self._schedule_regen()

    def _move_reset_up(self, e):
        idx = self._reset_entries.index(e)
        if idx > 0:
            self._reset_entries[idx], self._reset_entries[idx-1] = self._reset_entries[idx-1], self._reset_entries[idx]
            self._rst_cont_lay.insertWidget(idx - 1, e)
            self._schedule_regen()

    def _move_reset_down(self, e):
        idx = self._reset_entries.index(e)
        if idx < len(self._reset_entries) - 1:
            self._reset_entries[idx], self._reset_entries[idx+1] = self._reset_entries[idx+1], self._reset_entries[idx]
            self._rst_cont_lay.insertWidget(idx + 1, e)
            self._schedule_regen()

    def _remove_reset(self, e):
        if len(self._reset_entries) <= 1:
            QMessageBox.information(self, "Info", "At least one control is required.")
            return
        self._reset_entries.remove(e)
        self._rst_cont_lay.removeWidget(e)
        e.deleteLater()
        self._refresh_port_selectors()
        self._schedule_regen()

    def _refresh_port_selectors(self):
        ports = self._all_port_names()
        clock_names = [e.get_config()['name'] for e in self._clock_entries]
        for e in self._clock_entries:
            e.set_port_list(ports)
        for e in self._get_reset_entries():
            e.set_port_list(ports)
            e.set_clock_list(clock_names)

    # ─── Task Sequence helpers ────────────────────────────────────────────────

    def _available_task_files(self):
        if os.path.exists(self.tasks_dir):
            return sorted(os.path.basename(f)
                          for f in glob.glob(os.path.join(self.tasks_dir, "*.v")))
        return []

    def _add_task_seq_entry(self):
        files = self._available_task_files()
        if not files:
            QMessageBox.information(self, "No Tasks",
                                    "No task snippets found. Create one in the Task Library first.")
            return
        e = TaskSeqEntryWidget(files, self)
        e.removed.connect(self._remove_task_seq)
        e.changed.connect(self._schedule_regen)
        self._task_seq_entries.append(e)
        self._seq_cont_lay.addWidget(e)
        self._schedule_regen()

    def _remove_task_seq(self, e):
        self._task_seq_entries.remove(e)
        self._seq_cont_lay.removeWidget(e)
        e.deleteLater()
        self._schedule_regen()

    def _reload_task_library(self):
        self.lib_list.clear()
        files = self._available_task_files()
        if files:
            self.lib_list.addItems(files)
        else:
            self.lib_list.addItem("None Available")
        for e in self._task_seq_entries:
            e.set_task_files(files)

    # ─── Auto-generation ──────────────────────────────────────────────────────

    def _schedule_regen(self, *_):
        self.update_preview()
        sender = self.sender()
        if hasattr(sender, 'get_config'):
            self._last_changed_signal = sender.get_config().get('name')
        else:
            self._last_changed_signal = None
        self._regen_timer.start()

    def _auto_generate(self):
        if not self.parsed_data:
            return
        self._status_label.setText("Regenerating…")
        config   = self._build_config()
        self._worker = GeneratorWorker(self.template_path, self.parsed_data, config, parent=self)
        self._worker.finished.connect(self._on_gen_done)
        self._worker.error.connect(self._on_gen_error)
        self._worker.start()

    def _on_gen_done(self, code):
        self.code_edit.setPlainText(code)
        self._status_label.setText("✓ Auto-generated")
        if getattr(self, '_last_changed_signal', None):
            self.code_edit.moveCursor(QTextCursor.Start)
            # Find "initial begin" first to skip over the declarations block
            if not self.code_edit.find("initial begin"):
                self.code_edit.moveCursor(QTextCursor.Start)
            
            # Find the actual signal transition code
            self.code_edit.find(self._last_changed_signal)
            
            # Clear selection so it doesn't look completely blue, but remains scrolled
            cursor = self.code_edit.textCursor()
            cursor.clearSelection()
            self.code_edit.setTextCursor(cursor)

    def _on_gen_error(self, msg):
        self._status_label.setText("⚠ Generation error")
        QMessageBox.critical(self, "Error", f"Failed to generate testbench:\n{msg}")

    # ─── Config builder ───────────────────────────────────────────────────────

    def _build_config(self):
        clocks       = [e.get_config() for e in self._clock_entries]
        resets       = [e.get_config() for e in self._get_reset_entries()]
        task_seq     = [e.get_config() for e in self._task_seq_entries]
        lib_tasks    = list({ts['task_file'] for ts in task_seq}) if task_seq else []

        tb_name = self.tb_name_input.text().strip()
        if not tb_name and self.parsed_data:
            tb_name = f"tb_{self.parsed_data.get('module_name', 'dut')}"

        return {
            'tb_name':       tb_name or 'tb_dut',
            'clocks':        clocks,
            'resets':        resets,
            'task_sequence': task_seq,
            'library_tasks': lib_tasks,
        }

    # ─── Waveform Preview ─────────────────────────────────────────────────────

    def update_preview(self):
        sigs = self.parsed_data.get('inputs', []) if self.parsed_data else None
        config = self._build_config()
        self.waveform_widget.update_from_config(config, sigs)

    # ─── File browsing ────────────────────────────────────────────────────────

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Design File", "",
            "HDL Files (*.v *.sv *.vhd *.vhdl);;All Files (*)"
        )
        if not path:
            return

        self.file_input.setText(path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.source_edit.setPlainText(f.read())
        except Exception as e:
            self.source_edit.setPlainText(f"Could not load source:\n{e}")

        try:
            parser           = get_parser(path)
            self.parsed_data = parser.parse()
            mod              = self.parsed_data.get('module_name', '?')
            if not self.tb_name_input.text():
                self.tb_name_input.setText(f"tb_{mod}")
            QMessageBox.information(
                self, "Parsed",
                f"Module: {mod}\n"
                f"Inputs:  {len(self.parsed_data.get('inputs', []))}\n"
                f"Outputs: {len(self.parsed_data.get('outputs', []))}"
            )
        except Exception as e:
            self.parsed_data = None
            QMessageBox.critical(self, "Parse Error", str(e))

        self._refresh_port_selectors()
        self.update_preview()
        self._schedule_regen()

    # ─── Save ─────────────────────────────────────────────────────────────────

    def save_file(self):
        code = self.code_edit.toPlainText()
        if not code:
            QMessageBox.warning(self, "Empty", "Nothing to save yet.")
            return

        tb  = self.tb_name_input.text().strip()
        mod = self.parsed_data.get('module_name', 'dut') if self.parsed_data else 'dut'
        default = f"{tb or ('tb_' + mod)}.sv"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save SystemVerilog Testbench", default,
            "SystemVerilog Files (*.sv);;Verilog Files (*.v);;All Files (*)"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(code)
                QMessageBox.information(self, "Saved", f"Saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ─── Search ───────────────────────────────────────────────────────────────

    def find_text_in_output(self):
        q = self.search_input.text()
        if not q:
            self.code_edit.setExtraSelections([])
            return
        found = self.code_edit.find(q)
        if not found:
            self.code_edit.moveCursor(QTextCursor.Start)
            found = self.code_edit.find(q)
        if found:
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#d19a66"))
            fmt.setForeground(QColor("#282c34"))
            sel.format  = fmt
            sel.cursor  = self.code_edit.textCursor()
            self.code_edit.setExtraSelections([sel])
        else:
            self.code_edit.setExtraSelections([])
            QMessageBox.information(self, "Search", f"Cannot find '{q}'.")

    # ─── Task library helpers ─────────────────────────────────────────────────

    def on_task_clicked(self, item):
        if not item or item.text() == "None Available":
            self.task_desc_label.setText("")
            return
        path = os.path.join(self.tasks_dir, item.text())
        if not os.path.exists(path):
            self.task_desc_label.setText("")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            desc = []
            for line in lines:
                if line.startswith("//"):
                    if "=====" in line or "----" in line:
                        continue
                    c = line.strip().lstrip("//").strip()
                    if c:
                        desc.append(c)
                elif not line.strip():
                    continue
                else:
                    break
            self.task_desc_label.setText("\n".join(desc) if desc else "No description.")
        except Exception:
            self.task_desc_label.setText("Failed to load description.")

    def _get_single_lib_selection(self):
        sel = self.lib_list.selectedItems()
        if len(sel) != 1 or sel[0].text() == "None Available":
            QMessageBox.warning(self, "Selection", "Select exactly one task snippet.")
            return None
        return sel[0].text()

    def edit_task_snippet(self):
        name = self._get_single_lib_selection()
        if name:
            self.open_task_creator(name)

    def delete_task_snippet(self):
        name = self._get_single_lib_selection()
        if not name:
            return
        if QMessageBox.question(
            self, "Delete", f"Permanently delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            try:
                os.remove(os.path.join(self.tasks_dir, name))
                self._reload_task_library()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def open_task_creator(self, edit_name=None):
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Task Snippet" if edit_name else "Create Task Snippet")
        dialog.setMinimumSize(640, 440)
        lay = QVBoxLayout(dialog)

        row = QHBoxLayout()
        row.addWidget(QLabel("File name:"))
        name_inp = QLineEdit(edit_name or "")
        name_inp.setPlaceholderText("my_task.v")
        if edit_name:
            name_inp.setReadOnly(True)
        row.addWidget(name_inp)
        lay.addLayout(row)

        lay.addWidget(QLabel("Task code (SystemVerilog / Verilog):"))
        code_inp = QTextEdit()
        code_inp.setPlaceholderText(
            "// Brief description\n\ntask my_task;\n    input [7:0] data;\nbegin\n    // ...\nend\nendtask"
        )
        if edit_name:
            fp = os.path.join(self.tasks_dir, edit_name)
            if os.path.exists(fp):
                try:
                    code_inp.setPlainText(open(fp, encoding='utf-8').read())
                except Exception:
                    pass
        VerilogHighlighter(code_inp.document())
        lay.addWidget(code_inp)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        save   = QPushButton("Save Snippet")

        def do_save():
            fn   = name_inp.text().strip()
            code = code_inp.toPlainText().strip()
            if not fn:
                QMessageBox.warning(dialog, "Error", "Provide a file name.")
                return
            if not fn.endswith('.v'):
                fn += '.v'
            if not code:
                QMessageBox.warning(dialog, "Error", "Code cannot be empty.")
                return
            os.makedirs(self.tasks_dir, exist_ok=True)
            sp = os.path.join(self.tasks_dir, fn)
            if os.path.exists(sp) and not edit_name:
                if QMessageBox.question(dialog, "Overwrite?", f"'{fn}' exists. Overwrite?",
                                        QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
                    return
            try:
                open(sp, 'w', encoding='utf-8').write(code)
                QMessageBox.information(dialog, "Saved", f"'{fn}' saved.")
                self._reload_task_library()
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", str(e))

        save.clicked.connect(do_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)
        dialog.exec()
