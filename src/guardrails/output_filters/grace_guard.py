"""Post-TTS Grace Guard locking mic for 0.5s - 1.0s to avoid acoustic feedback."""
import time

class GraceGuardManager:
    def __init__(self, lockout_seconds: float = 0.75):
        self.lockout_seconds = lockout_seconds
        self.last_tts_end_time = 0.0

    def mark_tts_ended(self):
        self.last_tts_end_time = time.time()

    def is_mic_locked(self) -> bool:
        return (time.time() - self.last_tts_end_time) < self.lockout_seconds
