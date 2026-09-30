"""Unit test: Verify that the Python environment and core libraries are properly configured."""
import importlib
import os
import pytest
from pathlib import Path


def test_core_dependencies_importable():
    """Verify that all core runtime modules can be imported without error."""
    required_modules = [
        "google.genai",
        "google.adk",
        "sounddevice",
        "fastapi",
        "websockets",
        "numpy",
        "pydantic",
        "pydantic_settings",
    ]
    for module_name in required_modules:
        mod = importlib.import_module(module_name)
        assert mod is not None, f"Failed to import {module_name}"


def test_settings_configuration():
    """Verify that settings are loaded with valid defaults."""
    from config.settings import settings
    assert settings.AUDIO_SAMPLE_RATE == 16000
    assert settings.AUDIO_CHANNELS == 1
    assert hasattr(settings, "GOOGLE_API_KEY")
    assert isinstance(settings.GEMINI_LIVE_MODEL, str) and len(settings.GEMINI_LIVE_MODEL) > 0


def test_sounddevice_devices_available():
    """Verify that PortAudio and sounddevice can query audio devices."""
    import sounddevice as sd
    devices = sd.query_devices()
    assert devices is not None
    # Ensure default devices or list of devices is returned
    assert len(devices) >= 0


def test_env_file_configuration():
    """Verify that .env exists in project root."""
    project_root = Path(__file__).resolve().parents[2]
    env_file = project_root / ".env"
    assert env_file.exists(), ".env file must exist in project root"
    content = env_file.read_text()
    assert "GOOGLE_API_KEY" in content
    assert "GEMINI_LIVE_MODEL" in content


def test_hello_adk_live_script_syntax():
    """Verify that scripts/hello_adk_live.py can be invoked with --help."""
    import subprocess
    import sys
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "hello_adk_live.py"
    assert script_path.exists()
    
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Gemini Live" in result.stdout or "--api-key" in result.stdout

