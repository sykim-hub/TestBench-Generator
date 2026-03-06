import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from src.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Load stylesheet
    style_path = os.path.join(os.path.dirname(__file__), 'gui', 'styles.qss')
    try:
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"[Warning] Could not load stylesheet: {e}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
