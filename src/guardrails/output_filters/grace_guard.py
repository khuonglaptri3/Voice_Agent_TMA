"""Post-TTS Grace Guard for acoustic feedback avoidance and echo filtering (Day 4 - Dev B).

Prevents AI agent from interrupting itself due to room acoustics/speaker echo,
while allowing intentional loud user barge-in speech to pass through immediately.
"""
from __future__ import annotations

import time
import numpy as np


class GraceGuardManager:
    """Manages the post-TTS lockout window and RMS acoustic echo filtering."""

    def __init__(
        self,
        lockout_seconds: float = 0.40,
        echo_energy_threshold: float = 0.025,
    ) -> None:
        """Initialize GraceGuardManager.

        Args:
            lockout_seconds: Duration after TTS ends to filter low-energy echo (default 400ms).
            echo_energy_threshold: Normalized RMS threshold below which mic frames
                                  are treated as speaker echo and discarded.
        """
        self.lockout_seconds = lockout_seconds
        self.echo_energy_threshold = echo_energy_threshold
        self.last_tts_end_time = 0.0
        self.is_tts_active = False

        # Metric tracking
        self.filtered_frames_count = 0
        self.passed_frames_count = 0

    def mark_tts_active(self) -> None:
        """Mark that Agent audio output is currently being transmitted or played."""
        self.is_tts_active = True

    def mark_tts_ended(self, timestamp: float | None = None) -> None:
        """Mark that Agent audio output has finished."""
        self.is_tts_active = False
        self.last_tts_end_time = timestamp if timestamp is not None else time.time()

    def is_mic_locked(self, timestamp: float | None = None) -> bool:
        """Check if currently within the post-TTS lockout window."""
        now = timestamp if timestamp is not None else time.time()
        return (now - self.last_tts_end_time) < self.lockout_seconds

    @staticmethod
    def calculate_rms(pcm_chunk: bytes) -> float:
        """Calculate normalized RMS (Root Mean Square) energy of 16-bit PCM mono samples.

        Returns:
            Normalized RMS value in range [0.0, 1.0].
        """
        if not pcm_chunk:
            return 0.0

        samples = np.frombuffer(pcm_chunk, dtype=np.int16)
        if len(samples) == 0:
            return 0.0

        float_samples = samples.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(float_samples ** 2)))
        return rms

    def should_filter_frame(
        self,
        pcm_chunk: bytes,
        timestamp: float | None = None,
    ) -> bool:
        """Evaluate if an incoming microphone audio chunk should be dropped.

        A frame is filtered out (returns True) if:
        1. It arrives within the post-TTS grace window (e.g. 400ms after agent speaking).
        2. Its RMS energy is below the echo threshold, meaning it is merely the room echo
           of the speaker sound rather than an intentional user utterance.

        Loud intentional speech (RMS >= threshold) passes through even inside the window,
        ensuring responsive Barge-in.

        Returns:
            True if the frame should be discarded/silenced, False otherwise.
        """
        now = timestamp if timestamp is not None else time.time()

        # If outside grace window, all mic audio passes through
        if not self.is_mic_locked(now):
            self.passed_frames_count += 1
            return False

        # Within grace window: inspect energy
        rms = self.calculate_rms(pcm_chunk)
        if rms < self.echo_energy_threshold:
            self.filtered_frames_count += 1
            return True

        # High energy intentional speech (Barge-in attempt)
        self.passed_frames_count += 1
        return False

    def reset(self) -> None:
        """Reset grace window and frame counters."""
        self.last_tts_end_time = 0.0
        self.is_tts_active = False
        self.filtered_frames_count = 0
        self.passed_frames_count = 0
