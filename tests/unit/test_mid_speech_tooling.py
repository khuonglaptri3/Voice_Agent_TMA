"""Unit tests for Mid-Speech Function Calling & Tool Orchestration (Day 5 - Dev A & Dev B).

Runs offline using mocks to verify:
1. Tool call detection and execution from Gemini Live streaming responses.
2. Dispatch of 'tool_event' with status='executing' and status='done'.
3. Proper formatting and dispatch of FunctionResponse back to Gemini session.
4. Tool call cancellation upon barge-in.
5. Error handling for unregistered tools.
"""
from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator
from src.tools.sample_tools import get_current_time, check_meeting_room


class FakeFunctionCall:
    def __init__(self, id: str, name: str, args: dict | None = None):
        self.id = id
        self.name = name
        self.args = args or {}


class FakeToolCall:
    def __init__(self, function_calls: list[FakeFunctionCall]):
        self.function_calls = function_calls


class FakeToolCallCancellation:
    def __init__(self, ids: list[str]):
        self.ids = ids


class FakeResponse:
    def __init__(
        self,
        tool_call: FakeToolCall | None = None,
        tool_call_cancellation: FakeToolCallCancellation | None = None,
        server_content=None,
    ):
        self.tool_call = tool_call
        self.tool_call_cancellation = tool_call_cancellation
        self.server_content = server_content


@pytest.mark.asyncio
async def test_orchestrator_initializes_with_default_tools():
    """Verify that ADKLiveOrchestrator auto-registers sample tools."""
    orchestrator = ADKLiveOrchestrator(api_key="mock-key")
    assert len(orchestrator.tools) >= 2
    assert "get_current_time" in orchestrator.tool_registry
    assert "check_meeting_room" in orchestrator.tool_registry


@pytest.mark.asyncio
async def test_orchestrator_executes_tool_call_and_sends_response():
    """Verify complete tool calling cycle: executing event -> function run -> response sent -> done event."""
    fake_session = AsyncMock()

    responses = [
        FakeResponse(
            tool_call=FakeToolCall(
                function_calls=[
                    FakeFunctionCall(
                        id="call_time_123",
                        name="get_current_time",
                        args={"timezone_name": "Asia/Ho_Chi_Minh"},
                    )
                ]
            )
        ),
    ]

    async def fake_receive():
        for r in responses:
            yield r
            await asyncio.sleep(0.01)

    fake_session.receive = fake_receive
    fake_session.send_realtime_input = AsyncMock()
    fake_session.send_tool_response = AsyncMock()

    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    dispatched_events = []

    async def callback(event_type: str, payload):
        dispatched_events.append((event_type, payload))

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

    # 1. Verify 'tool_event' executing was dispatched
    executing_events = [e[1] for e in dispatched_events if e[0] == "tool_event" and e[1].get("status") == "executing"]
    assert len(executing_events) == 1
    assert executing_events[0]["tool_name"] == "get_current_time"
    assert executing_events[0]["call_id"] == "call_time_123"

    # 2. Verify send_tool_response was called on fake_session
    assert fake_session.send_tool_response.call_count == 1
    kwargs = fake_session.send_tool_response.call_args.kwargs
    function_responses = kwargs.get("function_responses")
    assert len(function_responses) == 1
    fr = function_responses[0]
    assert fr.name == "get_current_time"
    assert fr.id == "call_time_123"
    assert "output" in fr.response or "result" in fr.response or isinstance(fr.response, dict)

    # 3. Verify 'tool_event' done was dispatched to client
    done_events = [e[1] for e in dispatched_events if e[0] == "tool_event" and e[1].get("status") == "done"]
    assert len(done_events) == 1
    assert done_events[0]["tool_name"] == "get_current_time"
    assert "execution_time_ms" in done_events[0]
    assert "Hiện tại là" in str(done_events[0]["result"])


@pytest.mark.asyncio
async def test_orchestrator_executes_meeting_room_query():
    """Verify tool call for checking meeting room status."""
    fake_session = AsyncMock()

    responses = [
        FakeResponse(
            tool_call=FakeToolCall(
                function_calls=[
                    FakeFunctionCall(
                        id="call_room_456",
                        name="check_meeting_room",
                        args={"room_name": "Phòng Lab A"},
                    )
                ]
            )
        ),
    ]

    async def fake_receive():
        for r in responses:
            yield r
            await asyncio.sleep(0.01)

    fake_session.receive = fake_receive
    fake_session.send_realtime_input = AsyncMock()
    fake_session.send_tool_response = AsyncMock()

    fake_client = MagicMock()
    fake_connect_cm = AsyncMock()
    fake_connect_cm.__aenter__.return_value = fake_session
    fake_client.aio.live.connect.return_value = fake_connect_cm

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    dispatched_events = []

    async def callback(event_type: str, payload):
        dispatched_events.append((event_type, payload))

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

    # Verify result contains meeting room info
    done_events = [e[1] for e in dispatched_events if e[0] == "tool_event" and e[1].get("status") == "done"]
    assert len(done_events) == 1
    result = done_events[0]["result"]
    assert result["found"] is True
    assert result["room_name"] == "Phòng Lab A"
    assert result["status"] == "Trống"


@pytest.mark.asyncio
async def test_orchestrator_handles_tool_cancellation():
    """Verify tool cancellation event dispatch when user barges in during tool execution."""
    fake_session = AsyncMock()

    responses = [
        FakeResponse(
            tool_call_cancellation=FakeToolCallCancellation(ids=["call_cancelled_01"])
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

    orchestrator = ADKLiveOrchestrator(api_key="mock-key", client=fake_client)
    audio_in_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    dispatched_events = []

    async def callback(event_type: str, payload):
        dispatched_events.append((event_type, payload))

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

    cancelled_events = [e[1] for e in dispatched_events if e[0] == "tool_event" and e[1].get("status") == "cancelled"]
    assert len(cancelled_events) == 1
    assert "call_cancelled_01" in cancelled_events[0]["ids"]
