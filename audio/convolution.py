"""
Módulo de processamento de convolução para IRs
"""

import numpy as np
import soundfile as sf
from scipy import signal


class ConvolutionProcessor:
    """
    Processa convolução entre arquivos DI e IRs
    """
    
    def __init__(self):
        self.ir_data = None
        self.ir_sample_rate = None
        self.di_data = None
        self.di_sample_rate = None
        self.last_result = None
        self.last_sample_rate = None
        
    def load_ir(self, filepath: str) -> str:
        """
        Carrega um arquivo de Impulse Response
        
        Returns:
            String com informações do arquivo
        """
        try:
            data, sample_rate = sf.read(filepath, dtype='float32')
            
            # Converte para mono se necessário
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            info_obj = sf.info(filepath)
            bit_depth = info_obj.subtype
            
            # Normaliza
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
            raise Exception(f"Erro ao carregar IR: {str(e)}")
            
    def load_di(self, filepath: str) -> str:
        """
        Carrega um arquivo DI
        
        Returns:
            String com informações do arquivo
        """
        try:
            data, sample_rate = sf.read(filepath, dtype='float32')
            
            # Converte para mono se necessário
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
                
            info_obj = sf.info(filepath)
            bit_depth = info_obj.subtype
            
            # Normaliza
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
            raise Exception(f"Erro ao carregar DI: {str(e)}")
            
    def process(self, wet_mix: float = 1.0) -> tuple:
        """
        Processa a convolução entre o DI e o IR carregados
        
        Args:
            wet_mix: Proporção do sinal processado (0.0 = dry, 1.0 = wet)
            
        Returns:
            Tuple (audio_data, sample_rate) ou (None, None) se erro
        """
        if self.ir_data is None or self.di_data is None:
            return None, None
            
        try:
            # Reamostra o IR se necessário para combinar com o DI
            ir_resampled = self.ir_data
            if self.ir_sample_rate != self.di_sample_rate:
                # Calcula o novo número de samples
                num_samples = int(len(self.ir_data) * self.di_sample_rate / self.ir_sample_rate)
                ir_resampled = signal.resample(self.ir_data, num_samples)
                
            # Realiza a convolução usando FFT para melhor performance
            # fftconvolve é muito mais rápido para sinais longos
            wet_signal = signal.fftconvolve(self.di_data, ir_resampled, mode='full')
            
            # Trunca para o tamanho do DI original (ou um pouco mais para o decay do IR)
            # Adiciona o tamanho do IR para preservar o decay
            output_length = len(self.di_data) + len(ir_resampled) - 1
            wet_signal = wet_signal[:output_length]
            
            # Normaliza o sinal wet
            max_wet = np.max(np.abs(wet_signal))
            if max_wet > 0:
                wet_signal = wet_signal / max_wet
                
            # Aplica o mix dry/wet
            if wet_mix < 1.0:
                # Estende o dry signal para combinar com o wet
                dry_signal = np.zeros(len(wet_signal))
                dry_signal[:len(self.di_data)] = self.di_data
                
                result = (1 - wet_mix) * dry_signal + wet_mix * wet_signal
            else:
                result = wet_signal
                
            # Normaliza o resultado final
            max_result = np.max(np.abs(result))
            if max_result > 0:
                result = result / max_result * 0.9  # Deixa headroom
                
            # Converte para float32
            result = result.astype(np.float32)
            
            self.last_result = result
            self.last_sample_rate = self.di_sample_rate
            
            return result, self.di_sample_rate
            
        except Exception as e:
            print(f"Erro na convolução: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None
            
    def get_last_result(self) -> tuple:
        """Retorna o último resultado processado"""
        return self.last_result, self.last_sample_rate
