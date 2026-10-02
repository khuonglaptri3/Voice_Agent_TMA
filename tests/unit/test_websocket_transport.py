"""Unit test: Verify WebSocketTransport handshake and audio streaming routing (Day 2 - Dev B).

Runs completely OFFLINE using mock orchestrators so NO external API quota is consumed.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.gateway.transports.websocket_transport import WebSocketTransport


def test_websocket_transport_handshake_and_lifecycle():
    """Verify session_start, audio forwarding, and session_stop."""
    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    # When start_live_session runs, echo "session_ready" back to callback
    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})
        # Read from queue until stopped
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
            # 1. Send session_start handshake
            websocket.send_json({
                "type": "session_start",
                "sample_rate": 16000,
                "language": "vi-VN",
            })

            # Expect session_ack
            ack = websocket.receive_json()
            assert ack["type"] == "session_ack"
            assert ack["status"] == "connecting"

            # Expect session_ready event from orchestrator
            ready_event = websocket.receive_json()
            assert ready_event["type"] == "session_ready"
            assert ready_event["status"] == "connected"

            # 2. Send 1024 bytes binary PCM chunk
            audio_payload = b"\x00\x01" * 512
            websocket.send_bytes(audio_payload)

            # 3. Send session_stop
            websocket.send_json({
                "type": "session_stop",
                "reason": "user_hangup",
            })
            stop_ack = websocket.receive_json()
            assert stop_ack["type"] == "session_stop"
            assert stop_ack["status"] == "stopped"


def test_websocket_transport_rejects_audio_before_session_start():
    """Verify that sending audio frames before session_start returns error."""
    app = FastAPI()

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(ws)
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            # Send raw audio before starting session
            websocket.send_bytes(b"\x00" * 1024)
            err = websocket.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "session_not_started"


def test_websocket_transport_rejects_invalid_voice():
    """Verify that specifying an unsupported voice returns error."""
    app = FastAPI()

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(ws)
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({
                "type": "session_start",
                "sample_rate": 16000,
                "voice": "NonExistentVoice",
            })
            err = websocket.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "invalid_voice"
            assert "Unsupported voice" in err["message"]


def test_websocket_transport_grace_guard_filters_echo():
    """Verify that WebSocketTransport drops acoustic echo frames when GraceGuard is locked."""
    from src.guardrails.output_filters.grace_guard import GraceGuardManager

    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    received_audio = []

    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})
        # Simulate agent finished speaking, triggering grace guard
        await event_out_callback("turn_complete", {"type": "turn_complete"})
        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                if chunk is not None:
                    received_audio.append(chunk)
            except asyncio.TimeoutError:
                continue

    mock_orchestrator.start_live_session = mock_start_live_session

    custom_guard = GraceGuardManager(lockout_seconds=10.0, echo_energy_threshold=0.03)

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(
            ws,
            orchestrator_factory=lambda: mock_orchestrator,
            grace_guard=custom_guard,
        )
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "session_start", "sample_rate": 16000})
            websocket.receive_json()  # session_ack
            websocket.receive_json()  # session_ready
            turn_done = websocket.receive_json()  # turn_complete
            assert turn_done["type"] == "turn_complete"

            # 1. Send low-energy echo frame (silence/low noise)
            low_energy_chunk = b"\x00\x00" * 512
            websocket.send_bytes(low_energy_chunk)

            # Wait briefly to ensure it was processed by receive loop
            import time
            time.sleep(0.05)

            # Queue must still be empty because GraceGuard dropped the echo
            assert len(received_audio) == 0
            assert custom_guard.filtered_frames_count == 1

            # 2. Send loud intentional barge-in speech frame
            import numpy as np
            loud_chunk = (np.sin(np.linspace(0, 10, 512)) * 0.4 * 32767).astype(np.int16).tobytes()
            websocket.send_bytes(loud_chunk)
            time.sleep(0.05)

            # Loud chunk must pass through to the audio queue
            assert len(received_audio) == 1
            assert received_audio[0] == loud_chunk
            assert custom_guard.passed_frames_count == 1

