"""
Motor de áudio para reprodução usando sounddevice
"""

import numpy as np
import sounddevice as sd


class AudioEngine:
    """
    Motor de reprodução de áudio com controles de play, pause, stop, seek
    Usa variáveis atômicas em vez de locks para evitar deadlocks no callback
    """
    
    def __init__(self):
        self.audio_data = None
        self.sample_rate = None
        self.position = 0  # Posição atual em samples
        self.volume = 0.8
        self._is_playing = False
        self._is_paused = False
        self.stream = None
        
    def load_audio(self, audio_data: np.ndarray, sample_rate: int):
        """Carrega dados de áudio para reprodução"""
        self.stop()
        self.audio_data = audio_data.astype(np.float32)
        self.sample_rate = sample_rate
        self.position = 0
            
    def has_audio(self) -> bool:
        """Verifica se há áudio carregado"""
        return self.audio_data is not None
        
    def play(self):
        """Inicia a reprodução"""
        if not self.has_audio():
            return
            
        # Para stream anterior se existir
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
            
        self._is_playing = True
        self._is_paused = False
        
        # Referências locais para o callback (evita problemas com self)
        audio_data = self.audio_data
        audio_len = len(self.audio_data)
        
        def callback(outdata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
                
            if self._is_paused or not self._is_playing:
                outdata.fill(0)
                return
                
            pos = self.position
            end_pos = pos + frames
            
            if pos >= audio_len:
                outdata.fill(0)
                self._is_playing = False
                raise sd.CallbackStop()
                
            if end_pos > audio_len:
                # Preenche com o áudio restante e zeros
                remaining = audio_len - pos
                outdata[:remaining, 0] = audio_data[pos:audio_len] * self.volume
                outdata[remaining:, 0] = 0
                self.position = audio_len
            else:
                outdata[:, 0] = audio_data[pos:end_pos] * self.volume
                self.position = end_pos
                
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=callback,
                dtype='float32',
                blocksize=1024,
                latency='low'
            )
            self.stream.start()
        except Exception as e:
            print(f"Erro ao iniciar stream: {e}")
            self._is_playing = False
            
    def pause(self):
        """Pausa a reprodução"""
        self._is_paused = True
            
    def resume(self):
        """Continua a reprodução após pausa"""
        if self._is_paused and self._is_playing:
            self._is_paused = False
        elif not self._is_playing and self.has_audio():
            # Se estava parado, reinicia do início ou da posição atual
            self.play()
                
    def stop(self):
        """Para a reprodução completamente"""
        self._is_playing = False
        self._is_paused = False
        self.position = 0
        
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
                
    def seek(self, position_seconds: float):
        """Vai para uma posição específica em segundos"""
        if not self.has_audio():
            return
            
        position_samples = int(position_seconds * self.sample_rate)
        position_samples = max(0, min(position_samples, len(self.audio_data) - 1))
        self.position = position_samples
            
    def seek_relative(self, delta_seconds: float):
        """Move a posição relativamente em segundos"""
        if not self.has_audio():
            return
            
        current_pos = self.get_position()
        new_pos = current_pos + delta_seconds
        self.seek(new_pos)
        
    def get_position(self) -> float:
        """Retorna a posição atual em segundos"""
        if not self.has_audio():
            return 0.0
            
        return self.position / self.sample_rate
            
    def get_duration(self) -> float:
        """Retorna a duração total em segundos"""
        if not self.has_audio():
            return 0.0
            
        return len(self.audio_data) / self.sample_rate
        
    def set_volume(self, volume: float):
        """Define o volume (0.0 a 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
            
    def is_playing(self) -> bool:
        """Verifica se está reproduzindo"""
        return self._is_playing and not self._is_paused
            
    def __del__(self):
        """Cleanup ao destruir"""
        try:
            self.stop()
        except:
            pass
