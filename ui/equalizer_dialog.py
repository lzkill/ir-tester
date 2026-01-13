
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton, 
    QGroupBox, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class EqualizerDialog(QDialog):
    # Signal emitted when any gain changes: list of 10 floats (dB)
    gains_changed = pyqtSignal(list)
    # Signal emitted when EQ is enabled/disabled
    eq_toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Graphic Equalizer")
        self.setFixedWidth(600)
        self.setFixedHeight(380) # Increased a bit to fit the checkbox
        
        # Initial gains (flat)
        self.current_gains = [0.0] * 10
        self.sliders = []
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Sliders container
        sliders_layout = QHBoxLayout()
        
        bands = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
        
        for i, freq_label in enumerate(bands):
            band_container = QVBoxLayout()
            
            # Slider
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-12, 12) # +/- 12dB
            slider.setValue(0)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setTickInterval(3)
            # Store band index in slider
            slider.setProperty("band_index", i)
            slider.valueChanged.connect(self.on_slider_changed)
            self.sliders.append(slider)
            
            # Value Label (dB)
            val_label = QLabel("0")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_label.setStyleSheet("color: #0078d4; font-weight: bold;")
            slider.setProperty("label_widget", val_label)
            
            # Frequency Label
            freq_lbl = QLabel(freq_label)
            freq_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            freq_lbl.setStyleSheet("color: #888888; font-size: 10px;")
            
            band_container.addWidget(val_label)
            band_container.addWidget(slider)
            band_container.addWidget(freq_lbl)
            
            sliders_layout.addLayout(band_container)
            
        layout.addLayout(sliders_layout)
        
        # Reset / Flat and Toggle buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 20, 10, 10)
        btn_layout.setSpacing(20)
        
        btn_layout.addStretch()

        # Enable Button (Toggle)
        self.btn_enable = QPushButton("Equalizer: ON")
        self.btn_enable.setCheckable(True)
        self.btn_enable.setChecked(True)
        self.btn_enable.setFixedWidth(150)
        self.btn_enable.toggled.connect(self.on_toggled)
        btn_layout.addWidget(self.btn_enable)
        
        # Reset Button
        btn_reset = QPushButton("Reset (Flat)")
        btn_reset.clicked.connect(self.reset_flat)
        btn_reset.setFixedWidth(150)
        btn_layout.addWidget(btn_reset)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def on_toggled(self, checked):
        # Update button text
        if checked:
            self.btn_enable.setText("Equalizer: ON")
            self.btn_enable.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold;")
        else:
            self.btn_enable.setText("Equalizer: OFF")
            self.btn_enable.setStyleSheet("background-color: #444444; color: #888888;")

        # Enable/Disable sliders visually
        for slider in self.sliders:
            slider.setEnabled(checked)
        self.eq_toggled.emit(checked)
        
    def on_slider_changed(self, value):
        slider = self.sender()
        index = slider.property("band_index")
        label = slider.property("label_widget")
        
        # Update label
        prefix = "+" if value > 0 else ""
        label.setText(f"{prefix}{value}")
        
        # Update internal state
        self.current_gains[index] = float(value)
        
        # Emit signal
        self.gains_changed.emit(self.current_gains)
        
    def reset_flat(self):
        for slider in self.sliders:
            slider.blockSignals(True)
            slider.setValue(0)
            label = slider.property("label_widget")
            label.setText("0")
            slider.blockSignals(False)
            
        self.current_gains = [0.0] * 10
        self.gains_changed.emit(self.current_gains)
