"""
Convolution processing module for IRs
"""

import numpy as np
import soundfile as sf
from scipy import signal


class ConvolutionProcessor:
    """
    Processes convolution between DI files and IRs
    """
    
    def __init__(self):
        self.ir_data = None
        self.ir_sample_rate = None
        self.di_data = None
        self.di_sample_rate = None
        self.last_result = None
        self.last_sample_rate = None
        
    def load_ir(self, filepath: str) -> str:
        """Load an Impulse Response file"""
        try:
            data, sample_rate = sf.read(filepath, dtype='float32')
            
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            info_obj = sf.info(filepath)
            bit_depth = info_obj.subtype
            
            max_val = np.max(np.abs(data))
            if max_val > 0:
                data = data / max_val
            
            self.ir_data = data
            self.ir_sample_rate = sample_rate
            
            duration = len(data) / sample_rate
            return f"IR: {sample_rate}Hz, {bit_depth}, {duration:.3f}s, {len(data)} samples"
            
        except Exception as e:
            self.ir_data = None
            self.ir_sample_rate = None
            raise Exception(f"Error loading IR: {str(e)}")
            
    def load_di(self, filepath: str) -> str:
        """Load a DI file"""
        try:
            data, sample_rate = sf.read(filepath, dtype='float32')
            
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            info_obj = sf.info(filepath)
            bit_depth = info_obj.subtype
            
            max_val = np.max(np.abs(data))
            if max_val > 0:
                data = data / max_val
            
            self.di_data = data
            self.di_sample_rate = sample_rate
            
            duration = len(data) / sample_rate
            return f"DI: {sample_rate}Hz, {bit_depth}, {duration:.2f}s"
            
        except Exception as e:
            self.di_data = None
            self.di_sample_rate = None
            raise Exception(f"Error loading DI: {str(e)}")
            
    def process(self, wet_mix: float = 1.0) -> tuple:
        """Process convolution between the loaded DI and IR"""
        if self.ir_data is None or self.di_data is None:
            return None, None
            
        try:
            ir_resampled = self.ir_data
            if self.ir_sample_rate != self.di_sample_rate:
                num_samples = int(len(self.ir_data) * self.di_sample_rate / self.ir_sample_rate)
                ir_resampled = signal.resample(self.ir_data, num_samples)
                
            # fftconvolve is much faster for long signals
            wet_signal = signal.fftconvolve(self.di_data, ir_resampled, mode='full')
            
            output_length = len(self.di_data) + len(ir_resampled) - 1
            wet_signal = wet_signal[:output_length]
            
            max_wet = np.max(np.abs(wet_signal))
            if max_wet > 0:
                wet_signal = wet_signal / max_wet
                
            if wet_mix < 1.0:
                dry_signal = np.zeros(len(wet_signal))
                dry_signal[:len(self.di_data)] = self.di_data
                
                result = (1 - wet_mix) * dry_signal + wet_mix * wet_signal
            else:
                result = wet_signal
                
            max_result = np.max(np.abs(result))
            if max_result > 0:
                result = result / max_result * 0.9  # Leave headroom
                
            result = result.astype(np.float32)
            
            self.last_result = result
            self.last_sample_rate = self.di_sample_rate
            
            return result, self.di_sample_rate
            
        except Exception as e:
            print(f"Error in convolution: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None
            
    def get_last_result(self) -> tuple:
        """Returns the last processed result"""
        return self.last_result, self.last_sample_rate
