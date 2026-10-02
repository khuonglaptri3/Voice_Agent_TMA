"""Unit & Integration tests for Dev B Day 5 deliverables:
1. WebSocket transport message forwarding of 'tool_event' ('executing' and 'done') to frontend client.
2. Resilience: WebSocket does not timeout or drop during 300ms - 500ms tool execution.
3. Mid-tool & post-tool barge-in interruption resilience.
4. Static verification of web/index.html and web/app.js tool badge & prompt chips wiring.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.gateway.transports.websocket_transport import WebSocketTransport


def test_websocket_forwards_tool_events_to_client():
    """Verify WebSocket client receives tool_event messages (executing -> done)."""
    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        # 1. session ready
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})
        
        # 2. Simulate tool execution event
        await event_out_callback(
            "tool_event",
            {
                "type": "tool_event",
                "tool_name": "check_meeting_room",
                "status": "executing",
                "params": {"room_name": "Lab A"},
                "call_id": "call_test_001",
                "timestamp_ms": int(time.time() * 1000),
            },
        )

        # 3. Simulate short tool execution time (30ms)
        await asyncio.sleep(0.03)

        # 4. Simulate tool done event
        await event_out_callback(
            "tool_event",
            {
                "type": "tool_event",
                "tool_name": "check_meeting_room",
                "status": "done",
                "result": {"room_name": "Phòng Lab A", "found": True, "status": "Trống"},
                "execution_time_ms": 32.5,
                "call_id": "call_test_001",
                "timestamp_ms": int(time.time() * 1000),
            },
        )

        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                if chunk is None:
                    break
            except asyncio.TimeoutError:
                continue

    mock_orchestrator.start_live_session = mock_start_live_session

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(
            ws,
            orchestrator_factory=lambda: mock_orchestrator,
        )
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            # 1. Handshake
            websocket.send_json({"type": "session_start", "sample_rate": 16000, "language": "vi-VN"})
            ack = websocket.receive_json()
            assert ack["type"] == "session_ack"

            ready = websocket.receive_json()
            assert ready["type"] == "session_ready"

            # 2. Receive executing event
            tool_exec = websocket.receive_json()
            assert tool_exec["type"] == "tool_event"
            assert tool_exec["status"] == "executing"
            assert tool_exec["tool_name"] == "check_meeting_room"
            assert tool_exec["params"] == {"room_name": "Lab A"}

            # 3. Receive done event
            tool_done = websocket.receive_json()
            assert tool_done["type"] == "tool_event"
            assert tool_done["status"] == "done"
            assert tool_done["result"]["status"] == "Trống"
            assert tool_done["execution_time_ms"] == 32.5

            # 4. Stop session
            websocket.send_json({"type": "session_stop"})
            stop = websocket.receive_json()
            assert stop["type"] == "session_stop"


def test_websocket_resilience_during_tool_execution_delay():
    """Verify that a 350ms tool execution delay does not cause connection drop or timeout."""
    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})

        # Executing event
        await event_out_callback(
            "tool_event",
            {
                "type": "tool_event",
                "tool_name": "get_current_time",
                "status": "executing",
                "params": {},
                "call_id": "call_delay_01",
                "timestamp_ms": int(time.time() * 1000),
            },
        )

        # Simulate 350ms DB lookup or API latency
        await asyncio.sleep(0.35)

        # Done event
        await event_out_callback(
            "tool_event",
            {
                "type": "tool_event",
                "tool_name": "get_current_time",
                "status": "done",
                "result": {"current_time": "10:00:00"},
                "execution_time_ms": 350.0,
                "call_id": "call_delay_01",
                "timestamp_ms": int(time.time() * 1000),
            },
        )

        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                if chunk is None:
                    break
            except asyncio.TimeoutError:
                continue

    mock_orchestrator.start_live_session = mock_start_live_session

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(
            ws,
            orchestrator_factory=lambda: mock_orchestrator,
        )
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "session_start", "sample_rate": 16000})
            websocket.receive_json()  # ack
            websocket.receive_json()  # ready

            # While tool is executing, send mic audio frames to prove connection is healthy
            exec_event = websocket.receive_json()
            assert exec_event["status"] == "executing"

            # Send multiple PCM chunks during execution
            for _ in range(5):
                websocket.send_bytes(b"\x00\x02" * 512)

            done_event = websocket.receive_json()
            assert done_event["status"] == "done"
            assert done_event["execution_time_ms"] == 350.0

            # Verify session continues normally
            websocket.send_json({"type": "session_stop"})
            stop = websocket.receive_json()
            assert stop["type"] == "session_stop"


def test_barge_in_interruption_during_tool_speech():
    """Verify barge-in interruption signal arrives properly when agent speaks tool output."""
    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})
        
        # Tool execution complete
        await event_out_callback("tool_event", {"type": "tool_event", "status": "executing", "tool_name": "get_current_time"})
        await event_out_callback("tool_event", {"type": "tool_event", "status": "done", "tool_name": "get_current_time"})

        # Agent starts speaking tool result
        await event_out_callback("audio", b"\x01\x02" * 480)

        # User barges in! Server fires interrupted event
        await event_out_callback("interrupted", {"type": "interrupted", "timestamp_ms": int(time.time() * 1000)})

        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                if chunk is None:
                    break
            except asyncio.TimeoutError:
                continue

    mock_orchestrator.start_live_session = mock_start_live_session

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(
            ws,
            orchestrator_factory=lambda: mock_orchestrator,
        )
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "session_start", "sample_rate": 16000})
            websocket.receive_json()  # ack
            websocket.receive_json()  # ready
            websocket.receive_json()  # executing
            websocket.receive_json()  # done
            audio_frame = websocket.receive_bytes()
            assert len(audio_frame) == 960

            interrupted = websocket.receive_json()
            assert interrupted["type"] == "interrupted"

            websocket.send_json({"type": "session_stop"})
            stop = websocket.receive_json()
            assert stop["type"] == "session_stop"


def test_ui_files_contain_tool_badge_and_prompt_elements():
    """Verify HTML and JS files contain all required Day 5 Dev B DOM elements and bindings."""
    project_root = Path(__file__).resolve().parent.parent.parent
    html_file = project_root / "web" / "index.html"
    js_file = project_root / "web" / "app.js"
    css_file = project_root / "web" / "style.css"

    assert html_file.exists()
    assert js_file.exists()
    assert css_file.exists()

    html_content = html_file.read_text(encoding="utf-8")
    assert 'id="tool-activity-badge"' in html_content
    assert 'id="tool-activity-icon"' in html_content
    assert 'id="tool-activity-text"' in html_content
    assert 'class="tool-prompts-bar"' in html_content
    assert "Bây giờ là mấy giờ?" in html_content
    assert "Phòng Lab A có đang trống không?" in html_content

    js_content = js_file.read_text(encoding="utf-8")
    assert "toolActivityBadge" in js_content
    assert "handleToolEvent" in js_content
    assert "resetToolBadge" in js_content
    assert 'payload.type === "tool_event"' in js_content
    assert "get_current_time" in js_content
    assert "check_meeting_room" in js_content

    css_content = css_file.read_text(encoding="utf-8")
    assert ".tool-activity-badge" in css_content
    assert ".tool-activity-badge.executing" in css_content
    assert ".tool-activity-badge.done" in css_content
    assert "@keyframes toolPulseGlow" in css_content
