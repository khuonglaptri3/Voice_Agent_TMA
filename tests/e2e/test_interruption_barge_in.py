"""E2E test for Barge-in Interruption and Audio Truncation (Day 4 - Dev B & Dev A Milestone 2).

Verifies that:
1. When user barges in while the agent is streaming audio, the server emits an 'interrupted' event.
2. The event includes timestamp_ms for client latency tracking (< 250ms target).
3. The server switches back to listening for the new user utterance.
4. Post-TTS GraceGuard prevents room echo from re-triggering accidental self-interruptions.
"""
import asyncio
import time
import numpy as np
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.gateway.transports.websocket_transport import WebSocketTransport
from src.guardrails.output_filters.grace_guard import GraceGuardManager


def test_barge_in_interruption_e2e_flow():
    """Verify end-to-end barge-in signal emission, audio truncation contract, and echo guard."""
    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})

        # Step 1: Agent streams 3 audio frames to client
        for _ in range(3):
            dummy_pcm = b"\x01\x00" * 960  # 24kHz audio chunk
            await event_out_callback("audio", dummy_pcm)
            await asyncio.sleep(0.02)

        # Step 2: User barges in. Live engine detects interruption.
        # Send interrupted signal with timestamp
        now_ms = int(time.time() * 1000)
        await event_out_callback(
            "interrupted",
            {
                "type": "interrupted",
                "timestamp_ms": now_ms,
                "reason": "user_barge_in",
            },
        )

        # Step 3: Listen for incoming new speech from user
        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                if chunk is not None:
                    received_speech.append(chunk)
            except asyncio.TimeoutError:
                continue

    received_speech = []
    mock_orchestrator.start_live_session = mock_start_live_session
    grace_guard = GraceGuardManager(lockout_seconds=1.5, echo_energy_threshold=0.025)

    @app.websocket("/ws/live")
    async def ws_endpoint(ws: WebSocket):
        transport = WebSocketTransport(
            ws,
            orchestrator_factory=lambda: mock_orchestrator,
            grace_guard=grace_guard,
        )
        await transport.start()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            # 1. Start live session
            websocket.send_json({"type": "session_start", "sample_rate": 16000})
            ack = websocket.receive_json()
            assert ack["type"] == "session_ack"
            ready = websocket.receive_json()
            assert ready["type"] == "session_ready"

            # 2. Receive streaming agent audio frames
            audio_frames_received = []
            for _ in range(3):
                audio_bytes = websocket.receive_bytes()
                assert len(audio_bytes) > 0
                audio_frames_received.append(audio_bytes)
            assert len(audio_frames_received) == 3

            # 3. Receive the 'interrupted' barge-in event
            interrupted_event = websocket.receive_json()
            assert interrupted_event["type"] == "interrupted"
            assert "timestamp_ms" in interrupted_event
            assert interrupted_event["reason"] == "user_barge_in"

            # Transit latency check: ensure server emitted timestamp is fresh (< 250ms)
            current_ms = int(time.time() * 1000)
            elapsed_ms = current_ms - interrupted_event["timestamp_ms"]
            assert elapsed_ms < 250, f"Barge-in transit latency exceeded 250ms: {elapsed_ms}ms"

            # 4. Verify GraceGuard behavior:
            # Low-energy room echo immediately following the interruption is filtered
            echo_chunk = (np.random.uniform(-0.005, 0.005, 512) * 32767).astype(np.int16).tobytes()
            websocket.send_bytes(echo_chunk)
            time.sleep(0.05)
            assert len(received_speech) == 0  # Dropped by GraceGuard
            assert grace_guard.filtered_frames_count == 1

            # 5. Loud intentional user new speech passes through
            new_speech = (np.sin(np.linspace(0, 20, 512)) * 0.40 * 32767).astype(np.int16).tobytes()
            websocket.send_bytes(new_speech)
            time.sleep(0.05)
            assert len(received_speech) == 1
            assert received_speech[0] == new_speech
            assert grace_guard.passed_frames_count == 1
