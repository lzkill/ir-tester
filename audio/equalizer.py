
import numpy as np
import scipy.signal

class Equalizer:
    """
    Equalizador Gráfico de 10 band com filtros Peaking EQ de 2ª ordem (bi-quad).
    """
    
    # Frequências ISO padrão para equalizador de 10 bandas
    BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    
    @staticmethod
    def process_frame(audio_data: np.ndarray, sample_rate: int, gains_db: list[float]) -> np.ndarray:
        """
        Aplica a equalização a um buffer de áudio inteiro.
        Usa processamento em cascata de filtros SOS (Second Order Sections) para estabilidade.
        """
        if len(gains_db) != 10:
            raise ValueError("São necessários exatamente 10 valores de ganho.")
            
        # Se todos os ganhos forem zero, retorna o original (bypass eficiente)
        if all(g == 0 for g in gains_db):
            return audio_data
            
        # Pré-aloca SOS array (10 bandas, 1 seção por banda, 6 coeficientes por seção)
        # scipy.signal.sosfilt executa uma cascata de seções de segunda ordem
        all_sos = []
        
        for i, freq in enumerate(Equalizer.BANDS):
            gain = gains_db[i]
            if gain == 0:
                continue
                
            # Cria filtro peaking
            # Q = 1.41 é um valor razoável para 1 oitava de largura de banda aproximada
            sos = scipy.signal.iirpeak(freq, Q=2.0, fs=sample_rate)
            
            # Ajusta o ganho. iirpeak padrão não tem parâmetro de ganho em dB direto no scipy < 1.9 (às vezes)
            # Mas podemos usar filters designados ou trick de mistura.
            # Alternativa melhor: Usar design de equalizador paramétrico manual ou shelving.
            
            # Melhor abordagem com scipy.signal.iirpeak:
            # iirpeak projeta um filtro passa-banda com ganho 0dB no pico (normalizado) e atenuação fora.
            # Isso não é exatamente um EQ peaking que pode ter ganho positivo ou negativo sobre o sinal original.
            
            # Vamos usar uma implementação direta de Peaking Filter coefficients robusta
            # para garantir que Boost e Cut funcionem corretamente.
            
            sos = Equalizer._design_peaking_filter(freq, gain, Q=1.41, fs=sample_rate)
            all_sos.append(sos)
            
        if not all_sos:
            return audio_data
            
        # Concatena todos os coeficientes SOS (n_sections, 6)
        cascaded_sos = np.vstack(all_sos)
        
        # Aplica a filtragem
        # axis=0 assume áudio mono (N,) ou multicanal channel-last? 
        # O audio engine usa (N,) float32. sosfilt funciona bem em 1D.
        processed = scipy.signal.sosfilt(cascaded_sos, audio_data)
        
        # Limita clipping simples
        processed = np.clip(processed, -1.0, 1.0)
        
        return processed.astype(np.float32)

    @staticmethod
    def _design_peaking_filter(f0, gain_db, Q, fs):
        """
        Projeta coeficientes SOS para um filtro Peaking EQ.
        Fórmulas baseadas no Audio EQ Cookbook de Robert Bristow-Johnson.
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
        
        # Normaliza por a0 e retorna formato SOS: [b0, b1, b2, a0, a1, a2] -> [b0, b1, b2, 1, a1/a0, a2/a0]
        # O scipy sosfilt espera [b0, b1, b2, a0, a1, a2], mas é bom normalizar a0 para 1 para estabilidade numérica
        
        sos = np.array([b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0])
        return sos
