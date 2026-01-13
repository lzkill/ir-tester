#!/usr/bin/env python3
"""
IR Tester - Application for testing Impulse Responses with DI files
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def get_version():
    """Reads version from the VERSION file."""
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IR Tester")
    app.setApplicationVersion(get_version())
    
    # Dark style for the application
    # Modern dark theme
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #121212;
            color: #e0e0e0;
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif;
            font-size: 14px;
        }
        
        QTreeWidget {
            background-color: #1e1e1e;
            border: 1px solid #333333;
            border-radius: 8px;
            color: #d0d0d0;
            padding: 8px;
            outline: none;
        }
        QTreeWidget::item {
            padding: 6px;
            border-radius: 4px;
            margin-bottom: 2px;
        }
        QTreeWidget::item:selected {
            background-color: #3d3d3d;
            border: 1px solid #505050;
            color: #ffffff;
        }
        QTreeWidget::item:hover {
            background-color: #2d2d2d;
        }
        
        QPushButton {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border: 1px solid #3d3d3d;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #3d3d3d;
            border: 1px solid #505050;
        }
        QPushButton:pressed {
            background-color: #1e1e1e;
            border: 1px solid #0078d4;
        }
        QPushButton:checked {
            background-color: #0078d4;
            color: white;
            border: 1px solid #005a9e;
        }
        QPushButton:disabled {
            background-color: #1e1e1e;
            color: #555555;
            border: 1px solid #2d2d2d;
        }
        
        /* Primary Action Buttons (Play) */
        QPushButton#primary_action {
            background-color: #107c10;
            border: 1px solid #0e6b0e;
            color: white;
        }
        QPushButton#primary_action:hover {
            background-color: #138813;
        }
        
        QSlider::groove:horizontal {
            border: 1px solid #333333;
            height: 6px;
            background: #1e1e1e;
            margin: 2px 0;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #0078d4;
            border: 1px solid #0078d4;
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }
        QSlider::handle:horizontal:hover {
            background: #1084d8;
        }
        QSlider::sub-page:horizontal {
            background: #0078d4;
            border-radius: 3px;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 1px solid #333333;
            border-radius: 8px;
            margin-top: 24px;
            padding-top: 16px;
            background-color: #181818;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            color: #a0a0a0;
        }
        
        QProgressBar {
            border: 1px solid #333333;
            border-radius: 4px;
            text-align: center;
            background-color: #1e1e1e;
            color: white;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
        
        QFrame {
            border: none;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
