#!/usr/bin/env python3
"""
IR Tester - Aplicação para testar Impulse Responses com arquivos DI
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IR Tester")
    app.setApplicationVersion("1.0.0")
    
    # Estilo escuro para a aplicação
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QTreeWidget {
            background-color: #2d2d2d;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            color: #ffffff;
            padding: 5px;
        }
        QTreeWidget::item {
            padding: 4px;
            border-radius: 3px;
        }
        QTreeWidget::item:selected {
            background-color: #0078d4;
        }
        QTreeWidget::item:hover {
            background-color: #3d3d3d;
        }
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings {
            border-image: none;
            image: url(none);
        }
        QTreeWidget::branch:open:has-children:!has-siblings,
        QTreeWidget::branch:open:has-children:has-siblings {
            border-image: none;
            image: url(none);
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: bold;
            min-width: 60px;
        }
        QPushButton:hover {
            background-color: #1084d8;
        }
        QPushButton:pressed {
            background-color: #006cc1;
        }
        QPushButton:disabled {
            background-color: #4d4d4d;
            color: #808080;
        }
        QSlider::groove:horizontal {
            border: 1px solid #3d3d3d;
            height: 8px;
            background: #2d2d2d;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #0078d4;
            border: none;
            width: 16px;
            margin: -4px 0;
            border-radius: 8px;
        }
        QSlider::sub-page:horizontal {
            background: #0078d4;
            border-radius: 4px;
        }
        QLabel {
            color: #ffffff;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #3d3d3d;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QProgressBar {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            text-align: center;
            background-color: #2d2d2d;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
    """)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
