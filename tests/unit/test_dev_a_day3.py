"""Unit tests for Dev A Day 3: Conversation Persona, Voice Config, and Subtitle Dissection.

All tests run completely offline with mocks to ensure zero Gemini API quota consumption.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.orchestration.engine.turn_orchestrator import (
    ADKLiveOrchestrator,
    SUPPORTED_VOICES,
    VoicePersona,
)


def test_voice_persona_default_and_rules():
    """Verify default persona contains mandatory voice guidelines."""
    persona = VoicePersona.get_persona("default")
    assert "tiếng Việt" in persona
    assert "2 câu" in persona or "hai câu" in persona
    # Strictly forbids markdown & formatting not suitable for TTS
    assert "Markdown" in persona or "markdown" in persona


def test_supported_voices_contains_gemini_standard():
    """Verify that supported voices match Google Gemini Live options."""
    for voice in ["Puck", "Charon", "Kore", "Fenrir", "Aoede"]:
        assert voice in SUPPORTED_VOICES


def test_orchestrator_validates_voice_selection():
    """Verify valid voice is retained and invalid voice raises ValueError."""
    orchestrator = ADKLiveOrchestrator(voice_name="Charon")
    assert orchestrator.voice_name == "Charon"

    with pytest.raises(ValueError, match="Unsupported voice"):
        ADKLiveOrchestrator(voice_name="InvalidVoice123")


@pytest.mark.asyncio
async def test_orchestrator_handles_turn_complete_and_final_transcript():
    """Verify that when turn_complete arrives, final transcript or turn_complete event is emitted."""
    fake_session = AsyncMock()

    class FakePart:
        def __init__(self, text=None, inline_data=None):
            self.text = text
            self.inline_data = inline_data

    class FakeServerContent:
        def __init__(self, model_turn=None, input_transcription=None, interrupted=False, turn_complete=False):
            self.model_turn = model_turn
            self.input_transcription = input_transcription
            self.interrupted = interrupted
            self.turn_complete = turn_complete

    class FakeResponse:
        def __init__(self, server_content):
            self.server_content = server_content

    # Responses: model streaming text chunk, then turn_complete
    responses = [
        FakeResponse(
            FakeServerContent(
                model_turn=MagicMock(parts=[FakePart(text="Dạ, phòng A đang trống ạ.")])
            )
        ),
        FakeResponse(
            FakeServerContent(turn_complete=True)
        ),
    ]

    async def fake_receive():
        for r in responses:
            yield r
            await asyncio.sleep(0.01)

    fake_session.receive = fake_receive
    fake_session.send_realtime_input = AsyncMock()

    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(
        api_key="mock-key",
        client=fake_client,
        voice_name="Kore",
    )

    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    received_events = []

    async def callback(event_type: str, payload):
        received_events.append((event_type, payload))

    session_task = asyncio.create_task(
        orchestrator.start_live_session(
            audio_in_queue=audio_in_queue,
            event_out_callback=callback,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.1)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # Check transcript event was dispatched
    agent_transcripts = [e[1] for e in received_events if e[0] == "transcript" and e[1].get("role") == "agent"]
    assert len(agent_transcripts) >= 1
    assert "Dạ, phòng A đang trống ạ." in agent_transcripts[0]["text"]

    # Check turn_complete was dispatched
    turn_complete_events = [e[1] for e in received_events if e[0] == "turn_complete"]
    assert len(turn_complete_events) == 1
    assert turn_complete_events[0]["type"] == "turn_complete"
