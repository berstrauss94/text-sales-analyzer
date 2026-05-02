# -*- coding: utf-8 -*-
"""
Audio transcription component using OpenAI Whisper (local, no API key needed).

Supports any audio/video format that ffmpeg can decode.
No time limit — Whisper processes the full file.
"""
from __future__ import annotations

import os
import tempfile


class AudioTranscriber:
    """
    Wraps OpenAI Whisper for local audio transcription.

    The model is loaded lazily on first use to avoid slowing down
    the web app startup.

    Supported models (trade-off speed vs accuracy):
        tiny, base, small, medium, large
    Default: "base" — good balance for Spanish/English on CPU.
    """

    def __init__(self, model_name: str = "base") -> None:
        self.model_name = model_name
        self._model = None   # lazy load
        self._whisper_available: bool | None = None  # None = not checked yet

    def _check_whisper(self) -> bool:
        """Return True if openai-whisper is importable."""
        if self._whisper_available is None:
            try:
                import whisper  # noqa: F401
                self._whisper_available = True
            except ImportError:
                self._whisper_available = False
        return self._whisper_available

    def _load_model(self):
        if self._model is None:
            import whisper  # type: ignore
            self._model = whisper.load_model(self.model_name)
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
                    "Whisper no esta instalado en este servidor. "
                    "Instala openai-whisper y ffmpeg para habilitar la transcripcion de audio."
                ),
            }

        if not os.path.exists(audio_path):
            return {"ok": False, "error": f"Archivo no encontrado: {audio_path}"}

        try:
            model = self._load_model()
            result = model.transcribe(
                audio_path,
                task="transcribe",      # keep original language
                verbose=False,
            )
            return {
                "ok": True,
                "text": result.get("text", "").strip(),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", []),
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
                    "Whisper no esta instalado en este servidor. "
                    "Instala openai-whisper y ffmpeg para habilitar la transcripcion de audio."
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
        """True if Whisper is installed and usable."""
        return self._check_whisper()
