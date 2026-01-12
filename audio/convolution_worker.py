"""
Worker thread para processamento de convolução
"""

from PyQt6.QtCore import QThread, pyqtSignal
import numpy as np


class ConvolutionWorker(QThread):
    """
    Thread separada para processar convolução sem bloquear a UI
    """
    
    # Sinais
    finished = pyqtSignal(np.ndarray, int)  # audio_data, sample_rate
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, convolution_processor, wet_mix: float = 1.0):
        super().__init__()
        self.convolution_processor = convolution_processor
        self.wet_mix = wet_mix
        
    def run(self):
        """Executa o processamento em thread separada"""
        try:
            self.progress.emit(10)
            
            audio_data, sample_rate = self.convolution_processor.process(self.wet_mix)
            
            self.progress.emit(100)
            
            if audio_data is not None:
                self.finished.emit(audio_data, sample_rate)
            else:
                self.error.emit("Erro ao processar convolução - resultado vazio")
                
        except Exception as e:
            self.error.emit(str(e))
