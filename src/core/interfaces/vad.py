"""Abstract interface for Voice Activity Detection."""
from abc import ABC, abstractmethod
from src.core.entities.audio_frame import AudioFrame

class BaseVADDetector(ABC):
    @abstractmethod
    def is_speech(self, frame: AudioFrame) -> bool:
        pass
