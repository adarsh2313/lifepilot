"""
Standalone STT test — speak into mic, get text back.

Usage:
    conda run -n lifepilot python test_stt.py
    conda run -n lifepilot python test_stt.py --seconds 15

Controls:
    Press ENTER to start recording.
    Press ENTER again to stop.
    Transcription prints immediately after.
"""

import argparse
import os
import sys
import tempfile
import threading
import time
import wave

import numpy as np
import pyaudio
from mlx_qwen3_asr import Session

MODEL_ID    = "Qwen/Qwen3-ASR-0.6B"
SAMPLE_RATE = 16000
CHANNELS    = 1
CHUNK       = 1024
FORMAT      = pyaudio.paInt16


def load_model() -> Session:
    print(f"Loading model: {MODEL_ID}")
    t0 = time.time()
    session = Session(model=MODEL_ID)
    print(f"Model ready ({time.time() - t0:.1f}s)\n")
    return session


def record_until_enter(max_seconds: int = 120) -> bytes:
    """Record from mic until user presses Enter (or max_seconds exceeded)."""
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    frames = []
    stop_flag = threading.Event()

    def wait_for_enter():
        input()   # blocks until Enter
        stop_flag.set()

    listener = threading.Thread(target=wait_for_enter, daemon=True)
    listener.start()

    start = time.time()
    while not stop_flag.is_set():
        elapsed = time.time() - start
        if elapsed >= max_seconds:
            print(f"\nMax {max_seconds}s reached — stopping.")
            break
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        # Simple elapsed indicator, redrawn in place
        print(f"  Recording... {elapsed:.1f}s  (press Enter to stop)", end="\r", flush=True)

    print()  # newline after the \r line
    stream.stop_stream()
    stream.close()
    pa.terminate()

    return b"".join(frames)


def save_wav(pcm_bytes: bytes) -> str:
    """Write raw PCM bytes to a temp WAV file. Returns file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)       # int16 = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return tmp.name


def transcribe(session: Session, wav_path: str) -> str:
    result = session.transcribe(wav_path, language="en")
    return result.text.strip()


def main():
    parser = argparse.ArgumentParser(description="Manual STT test — speak, press Enter, get text.")
    parser.add_argument("--seconds", type=int, default=120, help="Max recording seconds (default: 120)")
    args = parser.parse_args()

    session = load_model()

    while True:
        print("─" * 50)
        input("Press ENTER to start recording…")
        print("  🎤  Speaking now — press ENTER to stop\n")

        pcm = record_until_enter(max_seconds=args.seconds)

        duration = len(pcm) / (SAMPLE_RATE * CHANNELS * 2)  # int16 = 2 bytes
        print(f"  Recorded {duration:.1f}s of audio — transcribing…")

        wav_path = save_wav(pcm)
        try:
            t0 = time.time()
            text = transcribe(session, wav_path)
            latency = time.time() - t0
        finally:
            os.unlink(wav_path)

        print()
        print("  ┌─ Transcript " + "─" * 35)
        print(f"  │  {text if text else '(nothing detected)'}")
        print("  └" + "─" * 48)
        print(f"  Latency: {latency:.2f}s   RTF: {latency/duration:.3f}x\n")

        again = input("Go again? [Y/n]: ").strip().lower()
        if again == "n":
            break

    print("Done.")


if __name__ == "__main__":
    main()
