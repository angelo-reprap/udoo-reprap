"""
whisper_service.py — Singleton-Wrapper fuer faster-whisper (WAV -> Rohtext).
Modell wird einmal pro Django-Worker-Prozess geladen (nicht pro Request),
analog zum deepseek_pbx-Singleton in deepseek_api_pbx.py.
Getestet: 'medium' auf GPU (RTX PRO 2000, float16), ~1.6s Ladezeit aus Cache.
"""
import time
import logging

logger = logging.getLogger(__name__)

MODEL_SIZE = 'medium'


class WhisperService:
    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            t0 = time.time()
            self._model = WhisperModel(MODEL_SIZE, device='cuda', compute_type='float16')
            logger.info(f'Whisper-Modell "{MODEL_SIZE}" geladen in {time.time() - t0:.1f}s')
        return self._model

    def transcribe(self, path, language='de'):
        model = self._get_model()
        segments, info = model.transcribe(path, language=language, beam_size=5)
        text = ''.join(seg.text for seg in segments).strip()
        return {
            'text': text,
            'language': info.language,
            'language_probability': round(info.language_probability, 2),
        }


whisper_service = WhisperService()
