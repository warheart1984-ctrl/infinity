"""Speech processing: transcription (STT) and text-to-speech (TTS)"""

import os
import io
import tempfile
import numpy as np
from pathlib import Path
from src.logger import get_logger

logger = get_logger(__name__)


class SpeechToText:
    """Audio transcription using OpenAI Whisper"""

    def __init__(self, model_size: str = "base"):
        """
        Args:
            model_size: Whisper model size - tiny, base, small, medium, large
        """
        self.model_size = model_size
        self._model = None

    def _load_model(self):
        """Lazy-load the Whisper model.

        Prefers faster-whisper (CTranslate2, CPU-friendly, no torch required)
        and falls back to openai-whisper when installed.
        """
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                size_map = {"tiny": "tiny", "base": "base", "small": "small",
                            "medium": "medium", "large": "large-v3"}
                fw_size = size_map.get(self.model_size, "base")
                logger.info(f"Loading faster-whisper model: {fw_size}")
                self._model = WhisperModel(
                    fw_size, device="cpu", compute_type="int8"
                )
                self._backend = "faster_whisper"
                logger.info("faster-whisper model loaded")
                return self._model
            except ImportError:
                logger.info("faster-whisper unavailable; trying openai-whisper")

            try:
                import whisper
                logger.info(f"Loading Whisper model: {self.model_size}")
                self._model = whisper.load_model(self.model_size)
                self._backend = "openai_whisper"
                logger.info("Whisper model loaded")
            except ImportError:
                raise ImportError(
                    "faster-whisper or openai-whisper is required. "
                    "Install with: pip install faster-whisper"
                )
        return self._model

    def transcribe(self, audio_path: str, language: str = None) -> dict:
        """Transcribe an audio file to text

        Args:
            audio_path: Path to audio file (wav, mp3, m4a, flac, etc.)
            language: Optional language code (e.g. 'en', 'es', 'fr')

        Returns:
            Dict with 'text', 'segments', and 'language'
        """
        model = self._load_model()
        logger.info(f"Transcribing: {audio_path}")
        if getattr(self, "_backend", "") == "faster_whisper":
            segments, info = model.transcribe(audio_path, language=language)
            text_parts = [seg.text.strip() for seg in segments]
            return {
                "text": " ".join(t for t in text_parts if t),
                "segments": [
                    {"start": s.start, "end": s.end, "text": s.text.strip()}
                    for s in segments
                ],
                "language": info.language,
            }

        options = {}
        if language:
            options["language"] = language

        result = model.transcribe(str(audio_path), **options)

        segments = [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ]

        logger.info(f"Transcription complete: {len(segments)} segments")
        return {
            "text": result["text"].strip(),
            "language": result.get("language", language),
            "segments": segments,
            "duration": segments[-1]["end"] if segments else 0,
        }

    def transcribe_bytes(self, audio_bytes: bytes, suffix: str = ".wav", language: str = None) -> dict:
        """Transcribe audio from raw bytes"""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.transcribe(tmp_path, language=language)
        finally:
            os.unlink(tmp_path)


class TextToSpeech:
    """Text-to-speech synthesis.

    Prefers Piper (neural, CPU-realtime, no torch). Falls back to the
    SpeechT5 transformer pipeline when Piper or its voice model is absent.
    """

    def __init__(self):
        self._synthesizer = None
        self._piper_voice = None
        self._backend = None

    def _load_model(self):
        if self._synthesizer is not None or self._piper_voice is not None:
            return self._piper_voice or self._synthesizer

        voice_path = os.getenv(
            "AAIS_PIPER_VOICE",
            str(Path.home() / "dev" / "piper-voices" / "en_US-ryan-high.onnx"),
        )
        try:
            from piper import PiperVoice
            if os.path.exists(voice_path):
                logger.info(f"Loading Piper voice: {voice_path}")
                self._piper_voice = PiperVoice.load(voice_path)
                self._backend = "piper"
                logger.info("Piper TTS loaded")
                return self._piper_voice
            logger.warning(f"Piper voice file missing: {voice_path}")
        except Exception as e:
            logger.warning(f"Piper unavailable ({e}); trying SpeechT5")

        try:
            from transformers import pipeline as hf_pipeline
            logger.info("Loading TTS model: microsoft/speecht5_tts")
            self._synthesizer = hf_pipeline("text-to-speech", model="microsoft/speecht5_tts")
            self._backend = "speecht5"
            logger.info("TTS model loaded")
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            raise
        return self._synthesizer

    def synthesize(self, text: str) -> dict:
        """Convert text to speech audio. Returns {'audio': int16 ndarray, 'sampling_rate': int}."""
        model = self._load_model()
        logger.info(f"Synthesizing speech for: {text[:60]}...")

        if self._backend == "piper":
            import numpy as np
            chunks = []
            sample_rate = 22050
            for chunk in model.synthesize(text):
                sample_rate = chunk.sample_rate
                chunks.append(chunk.audio_int16_array)
            audio = np.concatenate(chunks) if len(chunks) > 1 else (chunks[0] if chunks else np.array([], dtype=np.int16))
            return {"audio": audio, "sampling_rate": sample_rate}

        result = model(text)
        return {
            "audio": result["audio"],
            "sampling_rate": result["sampling_rate"],
        }

    def synthesize_to_wav_bytes(self, text: str) -> bytes:
        """Convert text to speech and return WAV bytes"""
        import struct
        import wave

        result = self.synthesize(text)
        audio = result["audio"]
        sr = result["sampling_rate"]

        if isinstance(audio, np.ndarray):
            if audio.dtype == np.int16:
                audio_int16 = audio
            else:
                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        else:
            audio_int16 = np.array(audio, dtype=np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(audio_int16.tobytes())

        return buf.getvalue()


# Module-level singletons (lazy-loaded)
speech_to_text = SpeechToText(model_size=os.getenv("WHISPER_MODEL_SIZE", "base"))
text_to_speech = TextToSpeech()
