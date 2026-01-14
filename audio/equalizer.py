
import numpy as np
import scipy.signal

class Equalizer:
    """10-band Graphic Equalizer using bi-quad peaking filters"""
    
    BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    
    @staticmethod
    def process_frame(audio_data: np.ndarray, sample_rate: int, gains_db: list[float]) -> np.ndarray:
        """Applies equalization using cascaded SOS filters"""
        if len(gains_db) != 10:
            raise ValueError("Exactly 10 gain values are required.")
            
        if all(g == 0 for g in gains_db):
            return audio_data
            
        all_sos = []
        
        for i, freq in enumerate(Equalizer.BANDS):
            gain = gains_db[i]
            if gain == 0:
                continue
                
            sos = Equalizer._design_peaking_filter(freq, gain, Q=1.41, fs=sample_rate)
            all_sos.append(sos)
            
        if not all_sos:
            return audio_data
            
        cascaded_sos = np.vstack(all_sos)
        processed = scipy.signal.sosfilt(cascaded_sos, audio_data)
        processed = np.clip(processed, -1.0, 1.0)
        
        return processed.astype(np.float32)

    @staticmethod
    def _design_peaking_filter(f0, gain_db, Q, fs):
        """Peaking EQ filter based on Robert Bristow-Johnson's Audio EQ Cookbook"""
        A = 10 ** (gain_db / 40.0)
        w0 = 2 * np.pi * f0 / fs
        alpha = np.sin(w0) / (2 * Q)
        cos_w0 = np.cos(w0)
        
        b0 = 1 + alpha * A
        b1 = -2 * cos_w0
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cos_w0
        a2 = 1 - alpha / A
        
        sos = np.array([b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0])
        return sos
