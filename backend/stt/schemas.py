"""Pydantic schemas for the STT layer.

These are the typed contracts between the STT module, the FastAPI endpoints,
and the coach layer. All STT output flows through these schemas.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Core STT types ────────────────────────────────────────────────────────────

class TranscriptChunk(BaseModel):
    """A single piece of transcribed speech — one sentence/phrase."""
    text: str
    is_final: bool
    elapsed_sec: float

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class TranscriptSession(BaseModel):
    """Complete transcript of a voice input session."""
    session_type: Literal["morning", "evening", "dropin"]
    date: str                                        # YYYY-MM-DD
    chunks: list[TranscriptChunk] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    language_detected: str = "en"

    @property
    def full_text(self) -> str:
        return " ".join(
            c.text.strip() for c in self.chunks
            if c.is_final and not c.is_empty
        )

    def add_chunk(self, text: str, is_final: bool = True) -> TranscriptChunk:
        elapsed = (datetime.now() - self.started_at).total_seconds()
        chunk = TranscriptChunk(text=text, is_final=is_final, elapsed_sec=elapsed)
        self.chunks.append(chunk)
        return chunk

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())


class STTResult(BaseModel):
    """Result from a single audio transcription (batch or per-chunk)."""
    text: str
    language: str = "en"
    latency_sec: float
    audio_duration_sec: float

    @property
    def realtime_factor(self) -> float:
        if self.audio_duration_sec == 0:
            return 0.0
        return self.latency_sec / self.audio_duration_sec

    @property
    def is_fast_enough(self) -> bool:
        return self.realtime_factor < 0.3


# ── FastAPI request / response schemas ───────────────────────────────────────

class TranscribeResponse(BaseModel):
    """Response from POST /transcribe (batch file upload)."""
    text: str
    language: str
    latency_sec: float
    audio_duration_sec: float
    realtime_factor: float
