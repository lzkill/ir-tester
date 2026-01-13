"""
Worker thread for convolution processing
"""

from PyQt6.QtCore import QThread, pyqtSignal
import numpy as np


class ConvolutionWorker(QThread):
    """
    Separate thread for processing convolution without blocking UI
    """
    
    # Signals
    finished = pyqtSignal(np.ndarray, int)  # audio_data, sample_rate
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, convolution_processor, wet_mix: float = 1.0):
        super().__init__()
        self.convolution_processor = convolution_processor
        self.wet_mix = wet_mix
        
    def run(self):
        """Executes processing in separate thread"""
        try:
            self.progress.emit(10)
            
            audio_data, sample_rate = self.convolution_processor.process(self.wet_mix)
            
            self.progress.emit(100)
            
            if audio_data is not None:
                self.finished.emit(audio_data, sample_rate)
            else:
                self.error.emit("Error processing convolution - empty result")
                
        except Exception as e:
            self.error.emit(str(e))
