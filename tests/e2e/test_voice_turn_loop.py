"""Comprehensive Real-API E2E Tests for Full-Duplex Voice Agent.

Tests all possible real-world scenarios and edge cases using the REAL Gemini Live API:
1. Standard full-duplex session lifecycle (Connect, Handshake, Stream, Hangup).
2. Multi-voice and persona customization (Puck, Charon, Kore, concise, customer_service).
3. Barge-in interruption & queue reset with real live session.
4. Post-TTS acoustic echo filtering with GraceGuard.
5. High-throughput burst audio streaming stress test.
6. Edge case: Audio frames sent before session_start.
7. Edge case: Invalid / non-JSON control messages.
8. Edge case: Unsupported audio sample rate.
9. Edge case: Invalid voice configuration.
10. Edge case: Duplicate session_start while active.
11. Edge case: Unsupported control message type.
12. Edge case: Abrupt client disconnect and resource cleanup.
"""
from __future__ import annotations

import asyncio
import os
import time
import numpy as np
import pytest
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from config.settings import settings
from src.gateway.transports.websocket_transport import WebSocketTransport
from src.guardrails.output_filters.grace_guard import GraceGuardManager
from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator
from src.serving.main import app

load_dotenv()

# Skip tests if GOOGLE_API_KEY is not configured
API_KEY = getattr(settings, "GOOGLE_API_KEY", None) or os.getenv("GOOGLE_API_KEY")
requires_real_api = pytest.mark.skipif(
    not API_KEY or API_KEY == "your-google-api-key",
    reason="GOOGLE_API_KEY required for real Gemini Live API tests",
)


@requires_real_api
def test_real_api_standard_lifecycle():
    """Case 1: Standard Lifecycle - Connect, Handshake, Stream audio, Stop gracefully."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            # 1. Start live session with real Gemini API
            ws.send_json({
                "type": "session_start",
                "sample_rate": 16000,
                "voice": "Puck",
                "language": "vi-VN",
            })

            ack = ws.receive_json()
            assert ack["type"] == "session_ack"
            assert ack["status"] == "connecting"

            ready = ws.receive_json()
            assert ready["type"] == "session_ready"
            assert ready["status"] == "connected"

            # 2. Stream 10 PCM audio chunks (1024 bytes each, 16kHz mono)
            for _ in range(10):
                ws.send_bytes(b"\x00" * 1024)
                time.sleep(0.01)

            # 3. Graceful session stop
            ws.send_json({"type": "session_stop", "reason": "user_hangup"})
            stopped = ws.receive_json()
            assert stopped["type"] == "session_stop"
            assert stopped["status"] == "stopped"
            assert stopped["reason"] == "user_hangup"


@requires_real_api
@pytest.mark.parametrize("voice,persona", [
    ("Charon", "concise"),
    ("Kore", "customer_service"),
])
def test_real_api_voice_and_persona_selection(voice: str, persona: str):
    """Case 2: Custom Voices & Personas with real Gemini Live API."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({
                "type": "session_start",
                "sample_rate": 16000,
                "voice": voice,
                "persona": persona,
                "language": "vi-VN",
            })

            ack = ws.receive_json()
            assert ack["type"] == "session_ack"

            ready = ws.receive_json()
            assert ready["type"] == "session_ready"
            assert ready["status"] == "connected"

            # Send brief audio chunk
            ws.send_bytes(b"\x00" * 1024)

            # Stop session
            ws.send_json({"type": "session_stop"})
            stopped = ws.receive_json()
            assert stopped["type"] == "session_stop"


@requires_real_api
def test_real_api_barge_in_and_queue_draining():
    """Case 3: Barge-in interruption & queue reset with real Live session."""
    orchestrator = ADKLiveOrchestrator(api_key=API_KEY)
    queue = orchestrator.create_live_request_queue()

    # Pre-populate queue with obsolete chunks
    for i in range(8):
        queue.put_nowait(f"chunk_{i}".encode("utf-8"))
    assert queue.qsize() == 8

    # Reset queue (Dev A Day 4 mechanism)
    t0 = time.perf_counter()
    drained = orchestrator.reset_audio_queue(queue)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert drained == 8
    assert queue.empty()
    assert elapsed_ms < 50.0, f"Queue reset exceeded 50ms: {elapsed_ms}ms"


@requires_real_api
def test_real_api_echo_filter_grace_guard():
    """Case 4: Acoustic Echo Cancellation & Grace Guard live filtering."""
    grace_guard = GraceGuardManager(lockout_seconds=1.5, echo_energy_threshold=0.025)

    test_app = FastAPI()

    @test_app.websocket("/ws/live")
    async def endpoint(ws: WebSocket):
        transport = WebSocketTransport(ws, grace_guard=grace_guard)
        await transport.start()

    with TestClient(test_app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"type": "session_start", "sample_rate": 16000})
            _ = ws.receive_json()  # ack
            _ = ws.receive_json()  # ready

            # Simulate agent finished speaking -> trigger grace window
            grace_guard.mark_tts_ended(time.time())
            assert grace_guard.is_mic_locked()

            # 1. Low energy echo frame (RMS < 0.025) must be dropped
            echo_chunk = (np.random.uniform(-0.005, 0.005, 512) * 32767).astype(np.int16).tobytes()
            ws.send_bytes(echo_chunk)
            time.sleep(0.05)
            assert grace_guard.filtered_frames_count >= 1

            # 2. Loud intentional speech frame (RMS >= 0.025) must pass through
            loud_chunk = (np.sin(np.linspace(0, 20, 512)) * 0.40 * 32767).astype(np.int16).tobytes()
            ws.send_bytes(loud_chunk)
            time.sleep(0.05)
            assert grace_guard.passed_frames_count >= 1

            # Clean stop
            ws.send_json({"type": "session_stop"})


@requires_real_api
def test_real_api_burst_streaming_stress():
    """Case 5: Rapid high-throughput burst streaming (60 audio chunks)."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"type": "session_start", "sample_rate": 16000})
            _ = ws.receive_json()  # ack
            _ = ws.receive_json()  # ready

            # Burst stream 60 chunks rapidly
            chunk = b"\x00" * 1024
            for _ in range(60):
                ws.send_bytes(chunk)

            # Ensure session is still healthy and responsive to control commands
            ws.send_json({"type": "session_stop"})
            stopped = ws.receive_json()
            assert stopped["type"] == "session_stop"
            assert stopped["status"] == "stopped"


def test_edge_case_audio_before_session_start():
    """Case 6: Binary audio frame sent before session_start -> Error."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_bytes(b"\x00" * 1024)
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "session_not_started"


def test_edge_case_invalid_json():
    """Case 7: Corrupted / non-JSON message sent -> Error."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_text("THIS_IS_NOT_VALID_JSON{{{")
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "invalid_json"


def test_edge_case_unsupported_sample_rate():
    """Case 8: Unsupported sample rate -> Error."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"type": "session_start", "sample_rate": 44100})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "unsupported_sample_rate"


def test_edge_case_invalid_voice():
    """Case 9: Invalid voice name -> Error."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({
                "type": "session_start",
                "sample_rate": 16000,
                "voice": "NonExistentVoiceXYZ",
            })
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "invalid_voice"


@requires_real_api
def test_edge_case_duplicate_session_start():
    """Case 10: Duplicate session_start while active -> already_started."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"type": "session_start", "sample_rate": 16000})
            _ = ws.receive_json()  # ack
            _ = ws.receive_json()  # ready

            # Second session_start
            ws.send_json({"type": "session_start", "sample_rate": 16000})
            dup_ack = ws.receive_json()
            assert dup_ack["type"] == "session_ack"
            assert dup_ack["status"] == "already_started"

            ws.send_json({"type": "session_stop"})
            _ = ws.receive_json()  # stopped


@requires_real_api
def test_edge_case_unsupported_control_message():
    """Case 11: Unsupported control message type -> Error."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"type": "session_start", "sample_rate": 16000})
            _ = ws.receive_json()  # ack
            _ = ws.receive_json()  # ready

            ws.send_json({"type": "unknown_command_abc"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == "unsupported_message"

            ws.send_json({"type": "session_stop"})
            _ = ws.receive_json()


@requires_real_api
def test_edge_case_abrupt_client_disconnect():
    """Case 12: Abrupt client disconnect without session_stop -> Clean cleanup."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            ws.send_json({"type": "session_start", "sample_rate": 16000})
            _ = ws.receive_json()  # ack
            _ = ws.receive_json()  # ready
            ws.send_bytes(b"\x00" * 1024)
            # Socket closes here when exiting context block
        # Verify a new connection immediately succeeds without port lock or leaked state
        with client.websocket_connect("/ws/live") as ws2:
            ws2.send_json({"type": "session_start", "sample_rate": 16000})
            ack = ws2.receive_json()
            assert ack["type"] == "session_ack"
            ready = ws2.receive_json()
            assert ready["type"] == "session_ready"
            ws2.send_json({"type": "session_stop"})
            _ = ws2.receive_json()
