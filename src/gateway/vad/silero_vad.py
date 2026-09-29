"""Silero VAD ONNX Runtime adapter."""
from src.core.interfaces.vad import BaseVADDetector
from src.core.entities.audio_frame import AudioFrame

class SileroVADDetector(BaseVADDetector):
    def is_speech(self, frame: AudioFrame) -> bool:
        return False
