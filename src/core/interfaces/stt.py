"""Abstract interface for Speech-to-Text services."""
from abc import ABC, abstractmethod

class BaseSTTService(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes) -> str:
        pass
