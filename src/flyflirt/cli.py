import sys
from PyQt6.QtWidgets import QApplication
from .app import MainWindow  # your class from app.py

def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())