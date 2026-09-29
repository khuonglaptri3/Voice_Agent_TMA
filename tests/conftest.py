"""Pytest configuration and global mock fixtures."""
import pytest

@pytest.fixture
def mock_audio_frame():
    return b'\x00' * 640
