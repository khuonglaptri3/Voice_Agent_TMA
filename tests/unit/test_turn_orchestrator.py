"""Unit tests for ADKLiveOrchestrator and TurnOrchestrator (Day 2 - Dev A).

These tests run completely OFFLINE using mock/fake live sessions so NO external
API quota is consumed.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator, TurnOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_initialization():
    """Verify that ADKLiveOrchestrator initializes with proper defaults."""

    orchestrator = ADKLiveOrchestrator(
        api_key="mock-api-key",
        model="gemini-2.5-flash-native-audio-latest",
        voice_name="Puck",
    )
    assert orchestrator.model == "gemini-2.5-flash-native-audio-latest"
    assert orchestrator.voice_name == "Puck"
    assert orchestrator.api_key == "mock-api-key"


@pytest.mark.asyncio
async def test_orchestrator_processes_10_audio_chunks():
    """DoD Dev A requirement: Simulate pushing 10 audio chunks into queue without error."""
    from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator

    received_audio_chunks = []
    fake_session = AsyncMock()

    async def fake_send_realtime_input(media=None, **kwargs):
        if media and hasattr(media, "data"):
            received_audio_chunks.append(media.data)
        elif kwargs.get("data"):
            received_audio_chunks.append(kwargs["data"])

    fake_session.send_realtime_input = fake_send_realtime_input

    # Fake receive generator that produces no events and waits until stopped
    async def fake_receive():
        while True:
            await asyncio.sleep(0.05)
            # yield nothing, keep loop alive
            if False:
                yield None

    fake_session.receive = fake_receive

    # Create mock client that yields fake_session
    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(
        api_key="mock-key",
        client=fake_client,
    )

    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    callback_events = []

    async def event_out_callback(event_type: str, data):
        callback_events.append((event_type, data))

    # Push 10 dummy audio chunks (1024 bytes each, 16kHz PCM)
    sample_chunk = b"\x00" * 1024
    for _ in range(10):
        await audio_in_queue.put(sample_chunk)

    # Run session in background
    session_task = asyncio.create_task(
        orchestrator.start_live_session(
            audio_in_queue=audio_in_queue,
            event_out_callback=event_out_callback,
            stop_event=stop_event,
        )
    )

    # Wait for queue to be drained
    await asyncio.sleep(0.1)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # Verify that exactly 10 chunks were forwarded to the live session
    assert len(received_audio_chunks) == 10
    assert all(c == sample_chunk for c in received_audio_chunks)
    live_config = fake_client.aio.live.connect.call_args.kwargs["config"]
    assert live_config.thinking_config.thinking_level.value == "LOW"


class FakePart:
    def __init__(self, text=None, inline_data=None):
        self.text = text
        self.inline_data = inline_data


class FakeInlineData:
    def __init__(self, data):
        self.data = data


class FakeServerContent:
    def __init__(self, model_turn=None, input_transcription=None, interrupted=False, turn_complete=False):
        self.model_turn = model_turn
        self.input_transcription = input_transcription
        self.interrupted = interrupted
        self.turn_complete = turn_complete


class FakeResponse:
    def __init__(self, server_content):
        self.server_content = server_content


@pytest.mark.asyncio
async def test_orchestrator_dispatches_audio_and_transcripts_to_callback():
    """Verify that incoming model audio and transcripts trigger event_out_callback."""
    from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator

    # Prepare fake responses
    fake_model_audio = b"\x01\x02\x03\x04" * 256

    # Sequence of fake responses
    responses = [
        # 1. User transcription
        FakeResponse(
            FakeServerContent(
                input_transcription=MagicMock(text="Xin chao")
            )
        ),
        # 2. Model speech output (text + audio)
        FakeResponse(
            FakeServerContent(
                model_turn=MagicMock(
                    parts=[
                        FakePart(text="Dạ em chào anh ạ.", inline_data=FakeInlineData(fake_model_audio))
                    ]
                )
            )
        ),
        # 3. Interrupted signal
        FakeResponse(
            FakeServerContent(
                interrupted=True
            )
        ),
    ]

    fake_session = AsyncMock()
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
    )

    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    received_events = []

    async def event_out_callback(event_type: str, data):
        received_events.append((event_type, data))

    session_task = asyncio.create_task(
        orchestrator.start_live_session(
            audio_in_queue=audio_in_queue,
            event_out_callback=event_out_callback,
            stop_event=stop_event,
        )
    )

    # Let the responses play out
    await asyncio.sleep(0.1)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # Check that events were dispatched
    event_types = [e[0] for e in received_events]
    assert "transcript" in event_types
    assert "audio" in event_types
    assert "interrupted" in event_types

    # Verify user transcript
    user_transcripts = [e[1] for e in received_events if e[0] == "transcript" and e[1].get("role") == "user"]
    assert len(user_transcripts) == 1
    assert user_transcripts[0]["text"] == "Xin chao"

    # Verify agent audio
    audio_events = [e[1] for e in received_events if e[0] == "audio"]
    assert len(audio_events) == 1
    assert audio_events[0] == fake_model_audio

    # Verify interrupted event
    interrupted_events = [e[1] for e in received_events if e[0] == "interrupted"]
    assert len(interrupted_events) == 1
    assert interrupted_events[0].get("reason") == "user_barge_in"


@pytest.mark.asyncio
async def test_turn_orchestrator_backward_compatibility():
    """Verify that TurnOrchestrator alias is available and inherits from ADKLiveOrchestrator."""
    from src.orchestration.engine.turn_orchestrator import TurnOrchestrator, ADKLiveOrchestrator
    assert issubclass(TurnOrchestrator, ADKLiveOrchestrator)


@pytest.mark.asyncio
async def test_multi_turn_live_session_does_not_close_after_first_turn_complete():
    """Verify that turn_complete does not terminate the live session for subsequent conversation turns."""
    turn1_audio = b"\x01\x01" * 128
    turn2_audio = b"\x02\x02" * 128

    responses = [
        # Turn 1
        FakeResponse(
            server_content=FakeServerContent(
                model_turn=MagicMock(parts=[FakePart(text="Turn 1", inline_data=FakeInlineData(turn1_audio))]),
            )
        ),
        FakeResponse(server_content=FakeServerContent(turn_complete=True)),
        # Turn 2 (arriving after turn 1 complete)
        FakeResponse(
            server_content=FakeServerContent(
                model_turn=MagicMock(parts=[FakePart(text="Turn 2", inline_data=FakeInlineData(turn2_audio))]),
            )
        ),
        FakeResponse(server_content=FakeServerContent(turn_complete=True)),
    ]

    class RealGenAiLikeSession:
        __module__ = "google.genai.live"

        def __init__(self, items):
            self.items = list(items)

        async def _receive(self):
            if self.items:
                await asyncio.sleep(0.01)
                return self.items.pop(0)
            await asyncio.sleep(0.5)
            return None

        async def send_realtime_input(self, media):
            pass

    mock_session = RealGenAiLikeSession(responses)
    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = mock_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    received_audio = []
    received_transcripts = []

    async def callback(event_type: str, payload):
        if event_type == "audio":
            received_audio.append(payload)
        elif event_type == "transcript" and payload.get("role") == "agent":
            received_transcripts.append(payload["text"])

    session_task = asyncio.create_task(
        orchestrator.start_live_session(
            audio_in_queue=audio_in_queue,
            event_out_callback=callback,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.12)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # Both Turn 1 and Turn 2 must be dispatched successfully
    assert len(received_audio) == 2
    assert received_audio[0] == turn1_audio
    assert received_audio[1] == turn2_audio
    assert "Turn 1" in received_transcripts
    assert "Turn 2" in received_transcripts

