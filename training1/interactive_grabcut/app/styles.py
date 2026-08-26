"""应用级样式。"""

APP_STYLE = """
QMainWindow { background: #f4f6f8; }
QToolBar { background: white; border-bottom: 1px solid #d8dee6; spacing: 6px; padding: 6px; }
QToolButton, QPushButton {
    background: #ffffff; color: #243142; border: 1px solid #cbd4df;
    border-radius: 6px; padding: 7px 10px;
}
QToolButton:hover, QPushButton:hover { border-color: #3978d4; background: #f2f7ff; }
QToolButton:checked, QPushButton:checked { background: #3978d4; color: white; border-color: #3978d4; }
QGroupBox { font-weight: 600; border: 1px solid #d8dee6; border-radius: 8px; margin-top: 10px; padding-top: 10px; background: white; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QComboBox, QSpinBox { background: white; border: 1px solid #cbd4df; border-radius: 5px; padding: 5px; }
QStatusBar { background: #1f2937; color: white; }
QStatusBar QLabel { color: white; padding: 3px 8px; }
QSplitter::handle { background: #d8dee6; width: 2px; }
"""
