"""Audio / STT router.

The renderer records audio via MediaRecorder, converts to base64, and POSTs JSON.
We decode, write a temp file, transcribe with Qwen3-ASR, return text.

Using a subprocess-based executor to avoid semaphore leaks with multiprocessing.
"""

import asyncio
import base64
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from pydantic import BaseModel

from backend.stt.qwen3_asr import transcribe_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcribe", tags=["stt"])

# Regular thread pool is fine — no multiprocessing, no semaphores
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt")


class TranscribeRequest(BaseModel):
    audio_b64: str   # base64-encoded audio bytes
    mime_type: str = "audio/webm"   # MIME type from MediaRecorder


@router.post("")
async def transcribe_audio(req: TranscribeRequest):
    """
    Receive base64-encoded audio from the browser, transcribe it, return text.
    """
    # Decode audio bytes
    try:
        audio_bytes = base64.b64decode(req.audio_b64)
    except Exception as e:
        return {"error": f"Invalid base64: {e}", "text": ""}

    logger.warning("Received audio: mime=%s bytes=%d", req.mime_type, len(audio_bytes))

    # Pick a file extension the model can handle
    ext = ".webm"
    if "ogg" in req.mime_type:
        ext = ".ogg"
    elif "mp4" in req.mime_type or "m4a" in req.mime_type:
        ext = ".mp4"
    elif "wav" in req.mime_type:
        ext = ".wav"

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(audio_bytes)
    tmp.flush()
    tmp.close()

    logger.warning("Saved to %s, size=%d bytes", tmp.name, os.path.getsize(tmp.name))

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, transcribe_file, tmp.name)
        logger.warning("Transcription result: '%s' lang=%s latency=%.2fs", result.text, result.language, result.latency_sec)
        return {"text": result.text, "language": result.language, "latency_sec": result.latency_sec}
    except Exception as e:
        logger.exception("Transcription failed")
        return {"error": str(e), "text": ""}
    finally:
        os.unlink(tmp.name)
