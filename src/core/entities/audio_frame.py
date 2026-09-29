"""Binary audio frame entity for streaming pipeline."""
from dataclasses import dataclass

@dataclass
class AudioFrame:
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    duration_ms: int = 20
    is_speech: bool = False
