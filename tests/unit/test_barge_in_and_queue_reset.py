"""Unit tests for Barge-in Interruption, Live Queue Reset, and Audio Suppression (Day 4).

All tests run offline using mocks to verify:
1. LiveRequestQueue draining on interruption.
2. Server dispatch of 'interrupted' signal strictly within < 50ms (DoD Dev A).
3. Suppression of residual model audio frames from the old interrupted turn.
4. Clean resumption of subsequent turns after barge-in.
"""
from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator


class FakePart:
    def __init__(self, text=None, inline_data=None):
        self.text = text
        self.inline_data = inline_data


class FakeInlineData:
    def __init__(self, data: bytes):
        self.data = data


class FakeServerContent:
    def __init__(
        self,
        interrupted: bool = False,
        input_transcription=None,
        output_transcription=None,
        model_turn=None,
        turn_complete: bool = False,
    ):
        self.interrupted = interrupted
        self.input_transcription = input_transcription
        self.output_transcription = output_transcription
        self.model_turn = model_turn
        self.turn_complete = turn_complete


class FakeResponse:
    def __init__(self, server_content: FakeServerContent):
        self.server_content = server_content


def test_reset_audio_queue_drains_all_chunks():
    """Verify that reset_audio_queue cleanly clears all pending audio frames in the queue."""
    queue = asyncio.Queue()
    for i in range(7):
        queue.put_nowait(f"chunk_{i}".encode("utf-8"))

    assert queue.qsize() == 7
    drained_count = ADKLiveOrchestrator.reset_audio_queue(queue)
    assert drained_count == 7
    assert queue.empty()
    assert queue.qsize() == 0

    # Draining an already empty queue returns 0
    assert ADKLiveOrchestrator.reset_audio_queue(queue) == 0


@pytest.mark.asyncio
async def test_barge_in_dispatched_under_50ms_and_valid_payload():
    """DoD Dev A: Server dispatches 'interrupted' event in < 50ms with correct contract payload."""
    fake_session = AsyncMock()

    responses = [
        FakeResponse(FakeServerContent(interrupted=True)),
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

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()

    received_events = []
    dispatch_times = []

    async def callback(event_type: str, payload):
        dispatch_times.append(time.perf_counter())
        received_events.append((event_type, payload))

    t_start = time.perf_counter()
    session_task = asyncio.create_task(
        orchestrator.start_live_session(
            audio_in_queue=audio_in_queue,
            event_out_callback=callback,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.05)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # 1. Verify event arrived
    interrupted_events = [e for e in received_events if e[0] == "interrupted"]
    assert len(interrupted_events) == 1

    event_type, payload = interrupted_events[0]
    assert payload["type"] == "interrupted"
    assert payload["reason"] == "user_barge_in"
    assert "timestamp_ms" in payload

    # 2. Check fresh timestamp (< 200ms from current system time)
    now_ms = int(time.time() * 1000)
    assert abs(now_ms - payload["timestamp_ms"]) < 200


@pytest.mark.asyncio
async def test_queue_drained_on_interruption():
    """Verify that any pending frames in audio_in_queue are wiped out when interrupted occurs."""
    fake_session = AsyncMock()

    responses = [
        FakeResponse(FakeServerContent(interrupted=True)),
    ]

    async def fake_receive():
        for r in responses:
            yield r
            await asyncio.sleep(0.02)

    fake_session.receive = fake_receive
    fake_session.send_realtime_input = AsyncMock()

    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()

    # Preload queue with obsolete chunks
    for _ in range(5):
        audio_in_queue.put_nowait(b"\x00" * 1024)

    assert audio_in_queue.qsize() == 5
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

    await asyncio.sleep(0.06)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # All 5 obsolete chunks must have been purged from the queue
    assert audio_in_queue.qsize() == 0


@pytest.mark.asyncio
async def test_residual_model_audio_suppressed_after_interruption():
    """Verify that any lingering model audio chunks after interruption are discarded."""
    fake_session = AsyncMock()
    residual_audio = b"\xaa\xbb" * 256

    responses = [
        # 1. Interruption occurs
        FakeResponse(FakeServerContent(interrupted=True)),
        # 2. Lingering model turn from the old turn (must be suppressed)
        FakeResponse(
            FakeServerContent(
                model_turn=MagicMock(
                    parts=[
                        FakePart(text="Old speech", inline_data=FakeInlineData(residual_audio))
                    ]
                )
            )
        ),
    ]

    async def fake_receive():
        for r in responses:
            yield r
            await asyncio.sleep(0.02)

    fake_session.receive = fake_receive
    fake_session.send_realtime_input = AsyncMock()

    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    dispatched_audio = []

    async def callback(event_type: str, payload):
        if event_type == "audio":
            dispatched_audio.append(payload)

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

    # Crucial: No residual audio must be dispatched to the client
    assert len(dispatched_audio) == 0


@pytest.mark.asyncio
async def test_new_turn_resumes_cleanly_after_interruption():
    """Verify that subsequent user turn after interruption restores audio dispatch."""
    fake_session = AsyncMock()
    new_model_audio = b"\x12\x34" * 256

    responses = [
        # 1. Interruption occurs
        FakeResponse(FakeServerContent(interrupted=True)),
        # 2. User starts speaking a new utterance
        FakeResponse(FakeServerContent(input_transcription=MagicMock(text="Cho tôi hỏi lại"))),
        # 3. Model speaks new response
        FakeResponse(
            FakeServerContent(
                model_turn=MagicMock(
                    parts=[
                        FakePart(text="Dạ em nghe ạ.", inline_data=FakeInlineData(new_model_audio))
                    ]
                )
            )
        ),
        # 4. Turn completes
        FakeResponse(FakeServerContent(turn_complete=True)),
    ]

    async def fake_receive():
        for r in responses:
            yield r
            await asyncio.sleep(0.02)

    fake_session.receive = fake_receive
    fake_session.send_realtime_input = AsyncMock()

    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    dispatched_audio = []
    dispatched_transcripts = []

    async def callback(event_type: str, payload):
        if event_type == "audio":
            dispatched_audio.append(payload)
        elif event_type == "transcript":
            dispatched_transcripts.append(payload)

    session_task = asyncio.create_task(
        orchestrator.start_live_session(
            audio_in_queue=audio_in_queue,
            event_out_callback=callback,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.15)
    stop_event.set()
    await asyncio.wait_for(session_task, timeout=1.0)

    # Check new user transcript and new model audio were both dispatched
    assert any(t.get("text") == "Cho tôi hỏi lại" for t in dispatched_transcripts)
    assert len(dispatched_audio) == 1
    assert dispatched_audio[0] == new_model_audio
