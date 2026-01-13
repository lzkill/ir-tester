
import numpy as np
import scipy.signal

class Equalizer:
    """
    10-band Graphic Equalizer with 2nd order Peaking EQ filters (bi-quad).
    """
    
    # Standard ISO frequencies for 10-band equalizer
    BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    
    @staticmethod
    def process_frame(audio_data: np.ndarray, sample_rate: int, gains_db: list[float]) -> np.ndarray:
        """
        Applies equalization to an entire audio buffer.
        Uses cascaded SOS (Second Order Sections) filter processing for stability.
        """
        if len(gains_db) != 10:
            raise ValueError("Exactly 10 gain values are required.")
            
        # If all gains are zero, return original (efficient bypass)
        if all(g == 0 for g in gains_db):
            return audio_data
            
        # Pre-allocate SOS array (10 bands, 1 section per band, 6 coefficients per section)
        # scipy.signal.sosfilt executes a cascade of second order sections
        all_sos = []
        
        for i, freq in enumerate(Equalizer.BANDS):
            gain = gains_db[i]
            if gain == 0:
                continue
                
            # Create peaking filter
            # Q = 1.41 is a reasonable value for approximately 1 octave bandwidth
            sos = scipy.signal.iirpeak(freq, Q=2.0, fs=sample_rate)
            
            # Adjust gain. iirpeak default doesn't have direct dB gain parameter in scipy < 1.9 (sometimes)
            # But we can use designated filters or mixing trick.
            # Better approach: Use manual parametric equalizer or shelving design.
            
            # Better approach with scipy.signal.iirpeak:
            # iirpeak designs a bandpass filter with 0dB gain at peak (normalized) and attenuation outside.
            # This is not exactly a peaking EQ that can have positive or negative gain over original signal.
            
            # Let's use a direct robust Peaking Filter coefficients implementation
            # to ensure Boost and Cut work correctly.
            
            sos = Equalizer._design_peaking_filter(freq, gain, Q=1.41, fs=sample_rate)
            all_sos.append(sos)
            
        if not all_sos:
            return audio_data
            
        # Concatenate all SOS coefficients (n_sections, 6)
        cascaded_sos = np.vstack(all_sos)
        
        # Apply filtering
        # axis=0 assumes mono audio (N,) or multichannel channel-last?
        # Audio engine uses (N,) float32. sosfilt works well on 1D.
        processed = scipy.signal.sosfilt(cascaded_sos, audio_data)
        
        # Simple clipping limiter
        processed = np.clip(processed, -1.0, 1.0)
        
        return processed.astype(np.float32)

    @staticmethod
    def _design_peaking_filter(f0, gain_db, Q, fs):
        """
        Designs SOS coefficients for a Peaking EQ filter.
        Formulas based on Robert Bristow-Johnson's Audio EQ Cookbook.
        """
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
        
        # Normalize by a0 and return SOS format: [b0, b1, b2, a0, a1, a2] -> [b0, b1, b2, 1, a1/a0, a2/a0]
        # scipy sosfilt expects [b0, b1, b2, a0, a1, a2], but normalizing a0 to 1 is good for numerical stability
        
        sos = np.array([b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0])
        return sos
