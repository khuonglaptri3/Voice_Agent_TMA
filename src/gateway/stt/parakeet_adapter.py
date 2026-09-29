"""NeMo Parakeet CTC STT adapter for Vietnamese."""
from src.core.interfaces.stt import BaseSTTService

class ParakeetAdapter(BaseSTTService):
    async def transcribe(self, audio_data: bytes) -> str:
        return ""
