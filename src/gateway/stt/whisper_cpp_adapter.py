"""Whisper.cpp CUDA STT adapter."""
from src.core.interfaces.stt import BaseSTTService

class WhisperCppSTT(BaseSTTService):
    async def transcribe(self, audio_data: bytes) -> str:
        return ""
