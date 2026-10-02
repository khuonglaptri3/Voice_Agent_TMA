"""Unit tests for Post-TTS Grace Guard & Acoustic Echo Filter (Day 4 - Dev B).

Runs completely offline to verify lockout window, RMS energy calculation,
and echo filtering behavior.
"""
import time
import numpy as np
import pytest

from src.guardrails.output_filters.grace_guard import GraceGuardManager


def test_calculate_rms_silence_and_signal():
    """Verify that RMS calculation correctly quantifies audio energy."""
    guard = GraceGuardManager()

    # Empty chunk
    assert guard.calculate_rms(b"") == 0.0

    # Perfect silence (all zeros)
    silence = b"\x00\x00" * 512
    assert guard.calculate_rms(silence) == 0.0

    # Low amplitude noise (echo simulator)
    low_noise = (np.random.uniform(-0.01, 0.01, 512) * 32767).astype(np.int16).tobytes()
    rms_low = guard.calculate_rms(low_noise)
    assert 0.0 < rms_low < 0.02

    # Loud speech signal
    loud_speech = (np.sin(np.linspace(0, 20, 512)) * 0.4 * 32767).astype(np.int16).tobytes()
    rms_loud = guard.calculate_rms(loud_speech)
    assert rms_loud > 0.15


def test_grace_window_timing():
    """Verify is_mic_locked timing behavior."""
    guard = GraceGuardManager(lockout_seconds=0.4)

    # Initially unlocked
    assert not guard.is_mic_locked()

    # Mark TTS ended at t=100.0
    guard.mark_tts_ended(timestamp=100.0)

    # Within 400ms window (e.g. t=100.2)
    assert guard.is_mic_locked(timestamp=100.2)
    # At boundary (t=100.39)
    assert guard.is_mic_locked(timestamp=100.39)
    # Outside window (t=100.41)
    assert not guard.is_mic_locked(timestamp=100.41)


def test_grace_guard_filters_echo_but_permits_loud_barge_in():
    """DoD Dev B: Low-energy echo frames in grace window are dropped; loud speech passes."""
    guard = GraceGuardManager(lockout_seconds=0.40, echo_energy_threshold=0.025)

    base_time = 1000.0
    guard.mark_tts_ended(timestamp=base_time)

    # 1. Low energy echo frame arriving 100ms after TTS ends -> MUST be filtered
    echo_samples = (np.sin(np.linspace(0, 10, 512)) * 0.01 * 32767).astype(np.int16).tobytes()
    should_filter_echo = guard.should_filter_frame(echo_samples, timestamp=base_time + 0.10)
    assert should_filter_echo is True
    assert guard.filtered_frames_count == 1

    # 2. Loud intentional user barge-in speech arriving 200ms after TTS ends -> MUST pass through
    loud_speech = (np.sin(np.linspace(0, 10, 512)) * 0.35 * 32767).astype(np.int16).tobytes()
    should_filter_speech = guard.should_filter_frame(loud_speech, timestamp=base_time + 0.20)
    assert should_filter_speech is False
    assert guard.passed_frames_count == 1

    # 3. Low energy audio arriving AFTER grace window (e.g. 500ms after TTS ends) -> MUST pass through
    should_filter_outside = guard.should_filter_frame(echo_samples, timestamp=base_time + 0.50)
    assert should_filter_outside is False
    assert guard.passed_frames_count == 2


def test_grace_guard_reset():
    """Verify reset clears lockout and stats."""
    guard = GraceGuardManager()
    guard.mark_tts_active()
    guard.mark_tts_ended(timestamp=time.time())
    guard.filtered_frames_count = 5
    guard.passed_frames_count = 10

    guard.reset()
    assert guard.last_tts_end_time == 0.0
    assert not guard.is_tts_active
    assert guard.filtered_frames_count == 0
    assert guard.passed_frames_count == 0
    assert not guard.is_mic_locked()
