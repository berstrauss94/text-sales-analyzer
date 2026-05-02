# -*- coding: utf-8 -*-
"""
Audio transcription component using faster-whisper (local, no API key needed).

faster-whisper uses CTranslate2 instead of PyTorch — much lighter (~200MB)
and faster on CPU. Compatible with all Whisper model sizes.

Supports any audio/video format that ffmpeg can decode.
No time limit — Whisper processes the full file.
"""
from __future__ import annotations

import os
import tempfile


class AudioTranscriber:
    """
    Wraps faster-whisper for local audio transcription.

    The model is loaded eagerly at construction time when faster-whisper is
    available, so the first transcription request does not block waiting
    for a model download. If faster-whisper is not installed the instance
    degrades gracefully and returns a structured error on every call.

    Supported models (trade-off speed vs accuracy):
        tiny, base, small, medium, large-v2, large-v3
    Default: "tiny" — fastest on CPU, good enough for Spanish/English.
    """

    def __init__(self, model_name: str = "tiny") -> None:
        self.model_name = model_name
        self._model = None
        self._whisper_available: bool | None = None
        # Eagerly load the model at startup so the first request is fast
        if self._check_whisper():
            try:
                self._load_model()
                print(f"faster-whisper model '{model_name}' loaded successfully.")
            except Exception as exc:
                print(f"Warning: could not pre-load faster-whisper model: {exc}")

    def _check_whisper(self) -> bool:
        """Return True if faster-whisper is importable."""
        if self._whisper_available is None:
            try:
                from faster_whisper import WhisperModel  # noqa: F401
                self._whisper_available = True
            except ImportError:
                self._whisper_available = False
        return self._whisper_available

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            # device="cpu", compute_type="int8" — optimal for Railway (no GPU)
            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
            )
        return self._model

    def transcribe(self, audio_path: str) -> dict:
        """
        Transcribe an audio file.

        Returns:
            {"ok": True, "text": "...", "language": "es", "segments": [...]}
            or
            {"ok": False, "error": "error message"}
        """
        if not self._check_whisper():
            return {
                "ok": False,
                "error": (
                    "faster-whisper no esta instalado en este servidor. "
                    "Contacta al administrador para habilitar la transcripcion de audio."
                ),
            }

        if not os.path.exists(audio_path):
            return {"ok": False, "error": f"Archivo no encontrado: {audio_path}"}

        try:
            model = self._load_model()
            segments, info = model.transcribe(
                audio_path,
                task="transcribe",
                beam_size=5,
            )
            # faster-whisper returns a generator — consume it
            segment_list = []
            full_text_parts = []
            for seg in segments:
                full_text_parts.append(seg.text)
                segment_list.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                })

            return {
                "ok": True,
                "text": " ".join(full_text_parts).strip(),
                "language": info.language,
                "segments": segment_list,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def transcribe_bytes(self, audio_bytes: bytes, suffix: str = ".wav") -> dict:
        """
        Transcribe audio from raw bytes (e.g. from a Flask file upload).
        Writes to a temp file, transcribes, then cleans up.
        """
        if not self._check_whisper():
            return {
                "ok": False,
                "error": (
                    "faster-whisper no esta instalado en este servidor. "
                    "Contacta al administrador para habilitar la transcripcion de audio."
                ),
            }

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.transcribe(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @property
    def is_available(self) -> bool:
        """True if faster-whisper is installed and usable."""
        return self._check_whisper()
