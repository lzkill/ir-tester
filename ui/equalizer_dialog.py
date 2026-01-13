
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton, 
    QGroupBox, QWidget, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

class EqualizerDialog(QDialog):
    # Sinal emitido quando qualquer ganho muda: lista de 10 floats (dB)
    gains_changed = pyqtSignal(list)
    # Sinal emitido quando o EQ é ativado/desativado
    eq_toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equalizador Gráfico")
        self.setFixedWidth(600)
        self.setFixedHeight(380) # Aumentei um pouco para caber o checkbox
        
        # Ganhos iniciais (flat)
        self.current_gains = [0.0] * 10
        self.sliders = []
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Container dos sliders
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
            # Armazena índice da banda no slider
            slider.setProperty("band_index", i)
            slider.valueChanged.connect(self.on_slider_changed)
            self.sliders.append(slider)
            
            # Label Valor (dB)
            val_label = QLabel("0")
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_label.setStyleSheet("color: #0078d4; font-weight: bold;")
            slider.setProperty("label_widget", val_label)
            
            # Label Frequência
            freq_lbl = QLabel(freq_label)
            freq_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            freq_lbl.setStyleSheet("color: #888888; font-size: 10px;")
            
            band_container.addWidget(val_label)
            band_container.addWidget(slider)
            band_container.addWidget(freq_lbl)
            
            sliders_layout.addLayout(band_container)
            
        layout.addLayout(sliders_layout)
        
        # Botões Reset / Flat e Toggle
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 20, 10, 10)
        btn_layout.setSpacing(20)
        
        btn_layout.addStretch()

        # Botão Ativar (Toggle)
        self.btn_enable = QPushButton("Equalizador: ON")
        self.btn_enable.setCheckable(True)
        self.btn_enable.setChecked(True)
        self.btn_enable.setFixedWidth(150)
        self.btn_enable.toggled.connect(self.on_toggled)
        btn_layout.addWidget(self.btn_enable)
        
        # Botão Reset
        btn_reset = QPushButton("Reset (Flat)")
        btn_reset.clicked.connect(self.reset_flat)
        btn_reset.setFixedWidth(150)
        btn_layout.addWidget(btn_reset)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def on_toggled(self, checked):
        # Atualiza o texto do botão
        if checked:
            self.btn_enable.setText("Equalizador: ON")
            self.btn_enable.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold;")
        else:
            self.btn_enable.setText("Equalizador: OFF")
            self.btn_enable.setStyleSheet("background-color: #444444; color: #888888;")

        # Habilita/Desabilita sliders visualmente
        for slider in self.sliders:
            slider.setEnabled(checked)
        self.eq_toggled.emit(checked)
        
    def on_slider_changed(self, value):
        slider = self.sender()
        index = slider.property("band_index")
        label = slider.property("label_widget")
        
        # Atualiza label
        prefix = "+" if value > 0 else ""
        label.setText(f"{prefix}{value}")
        
        # Atualiza estado interno
        self.current_gains[index] = float(value)
        
        # Emite sinal
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
