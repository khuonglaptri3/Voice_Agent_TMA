"""Unit tests for ASR hallucination filter and Unicode guard."""
from src.guardrails.hallucination.speech_hallucination_filter import ASRHallucinationFilter

def test_hallucination_filter():
    f = ASRHallucinationFilter()
    assert not f.is_valid_transcription("xin chào xin chào xin chào xin chào")
    assert f.is_valid_transcription("Xin chào, tôi cần đặt phòng họp ngày mai")
