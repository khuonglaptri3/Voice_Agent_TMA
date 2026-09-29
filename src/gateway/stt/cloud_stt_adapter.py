"""Cloud STT adapter (e.g. Deepgram Nova)."""
from src.core.interfaces.stt import BaseSTTService

class CloudSTTAdapter(BaseSTTService):
    async def transcribe(self, audio_data: bytes) -> str:
        return ""
