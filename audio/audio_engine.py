"""
Audio engine for playback using sounddevice
"""

import numpy as np
import sounddevice as sd


class AudioEngine:
    """
    Audio playback engine with play, pause, stop, seek controls
    Uses atomic variables instead of locks to avoid deadlocks in callback
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
        """Loads audio data for playback"""
        self.stop()
        self.audio_data = audio_data.astype(np.float32)
        self.sample_rate = sample_rate
        self.position = 0
            
    def has_audio(self) -> bool:
        """Checks if there is audio loaded"""
        return self.audio_data is not None
        
    def update_audio(self, audio_data: np.ndarray):
        """Updates audio buffer in real-time (hot-swap)"""
        # Ensures contiguous array and float32
        data = np.ascontiguousarray(audio_data, dtype=np.float32)
        if self._is_playing:
            self.audio_data = data
        else:
            self.audio_data = data

    def play(self):
        """Starts playback"""
        if not self.has_audio():
            return
            
        # Stop previous stream if exists
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
            
        self._is_playing = True
        self._is_paused = False
        
        def callback(outdata, frames, time, status):
            try:
                if status:
                    print(f"Audio status: {status}")
                    
                if self._is_paused or not self._is_playing:
                    outdata.fill(0)
                    return
                
                current_audio = self.audio_data
                if current_audio is None:
                    outdata.fill(0)
                    return

                audio_len = len(current_audio)
                pos = self.position
                end_pos = pos + frames
                
                if pos >= audio_len:
                    outdata.fill(0)
                    self._is_playing = False
                    raise sd.CallbackStop()
                    
                if end_pos > audio_len:
                    remaining = audio_len - pos
                    chunk = current_audio[pos:audio_len]
                    if len(chunk) > 0:
                         outdata[:remaining, 0] = chunk * self.volume
                    outdata[remaining:, 0] = 0
                    self.position = audio_len
                else:
                    chunk = current_audio[pos:end_pos]
                    outdata[:, 0] = chunk * self.volume
                    self.position = end_pos
                    
            except Exception as e:
                print(f"Error in audio callback: {e}")
                outdata.fill(0)
                # Opcional: Parar reprodução em caso de erro crítico
                # raise sd.CallbackAbort()
                
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
            print(f"Error starting stream: {e}")
            self._is_playing = False
            
    def pause(self):
        """Pauses playback"""
        self._is_paused = True
            
    def resume(self):
        """Resumes playback after pause"""
        if self._is_paused and self._is_playing:
            self._is_paused = False
        elif not self._is_playing and self.has_audio():
            # If stopped, restart from beginning or current position
            self.play()
                
    def stop(self):
        """Stops playback completely"""
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
        """Seeks to a specific position in seconds"""
        if not self.has_audio():
            return
            
        position_samples = int(position_seconds * self.sample_rate)
        position_samples = max(0, min(position_samples, len(self.audio_data) - 1))
        self.position = position_samples
            
    def seek_relative(self, delta_seconds: float):
        """Moves position relatively in seconds"""
        if not self.has_audio():
            return
            
        current_pos = self.get_position()
        new_pos = current_pos + delta_seconds
        self.seek(new_pos)
        
    def get_position(self) -> float:
        """Returns current position in seconds"""
        if not self.has_audio():
            return 0.0
            
        return self.position / self.sample_rate
            
    def get_duration(self) -> float:
        """Returns total duration in seconds"""
        if not self.has_audio():
            return 0.0
            
        return len(self.audio_data) / self.sample_rate
        
    def set_volume(self, volume: float):
        """Sets volume (0.0 to 1.0)"""
        self.volume = max(0.0, min(1.0, volume))
            
    def is_playing(self) -> bool:
        """Checks if playing"""
        return self._is_playing and not self._is_paused
            
    def __del__(self):
        """Cleanup on destroy"""
        try:
            self.stop()
        except:
            pass
