"""Qwen3-ASR-0.6B wrapper.

Loads the model once (lazy, on first request) and keeps it in memory.
Only does one thing: transcribe a file path → text.
"""

import logging
import time

import soundfile as sf
from mlx_qwen3_asr import Session as QwenSession

from backend.stt.schemas import STTResult

logger = logging.getLogger(__name__)

MODEL_ID = "Qwen/Qwen3-ASR-0.6B"

_session: QwenSession | None = None


def _get_session() -> QwenSession:
    global _session
    if _session is None:
        logger.info("Loading Qwen3-ASR model: %s", MODEL_ID)
        t0 = time.time()
        _session = QwenSession(model=MODEL_ID)
        logger.info("Qwen3-ASR loaded in %.1fs", time.time() - t0)
    return _session


def transcribe_file(file_path: str, language: str = "en") -> STTResult:
    """Transcribe an audio file. Accepts any format ffmpeg supports."""
    session = _get_session()

    audio, sr = sf.read(file_path)
    audio_duration = len(audio) / sr

    t0 = time.time()
    result = session.transcribe(file_path, language=language)
    latency = time.time() - t0

    return STTResult(
        text=result.text.strip(),
        language=result.language or language,
        latency_sec=latency,
        audio_duration_sec=audio_duration,
    )
