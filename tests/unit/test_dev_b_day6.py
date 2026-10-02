"""Unit & Integration tests for Dev B Day 6 deliverables:
1. Verification of 5 Reference Case Audio Recordings in data/audio_samples/.
2. Verification of sample_manifest.json schema, benchmarks, and metadata.
3. Verification of Web UI Latency Telemetry HUD, Session Exporter, and Reference Audio cards.
4. Verification of WebSocket 'latency_metric' event forwarding from ADK / PipelineTracer.
5. Verification of FastAPI static file mount for /data audio streaming.
"""
from __future__ import annotations

import asyncio
import json
import time
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from src.gateway.transports.websocket_transport import WebSocketTransport
from src.serving.main import app as serving_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_AUDIO_DIR = PROJECT_ROOT / "data" / "audio_samples"
MANIFEST_PATH = DATA_AUDIO_DIR / "sample_manifest.json"
WEB_DIR = PROJECT_ROOT / "web"


# ==============================================================================
# 1. Reference Audio Files & Manifest Tests
# ==============================================================================

def test_reference_audio_samples_and_manifest_exist():
    """Verify that all 5 WAV files and sample_manifest.json exist in data/audio_samples/."""
    assert DATA_AUDIO_DIR.is_dir(), f"Directory not found: {DATA_AUDIO_DIR}"
    assert MANIFEST_PATH.is_file(), f"Manifest file not found: {MANIFEST_PATH}"

    expected_files = [
        "fluent_dialogue_vi.wav",
        "fluent_dialogue_en.wav",
        "barge_in_interruption.wav",
        "tool_current_time.wav",
        "tool_meeting_room.wav",
    ]

    for fname in expected_files:
        wav_path = DATA_AUDIO_DIR / fname
        assert wav_path.is_file(), f"Expected audio file not found: {wav_path}"
        assert wav_path.stat().st_size > 10000, f"File {fname} is too small ({wav_path.stat().st_size} bytes)"


def test_reference_manifest_contents_and_metrics():
    """Verify sample_manifest.json schema, benchmark averages, and target thresholds."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert "summary" in manifest
    assert "samples" in manifest

    summary = manifest["summary"]
    assert summary["total_samples"] == 5
    assert summary["avg_e2e_ttfa_ms"] < 500.0, f"E2E TTFA average should be < 500ms, got {summary['avg_e2e_ttfa_ms']}"
    assert summary["barge_in_pass_threshold_ms"] == 250.0
    assert summary["barge_in_measured_ms"] < 250.0

    samples = manifest["samples"]
    assert len(samples) == 5

    filenames = [s["filename"] for s in samples]
    assert "fluent_dialogue_vi.wav" in filenames
    assert "fluent_dialogue_en.wav" in filenames
    assert "barge_in_interruption.wav" in filenames
    assert "tool_current_time.wav" in filenames
    assert "tool_meeting_room.wav" in filenames

    # Check Case 3: Barge-in
    barge_case = next(s for s in samples if s["filename"] == "barge_in_interruption.wav")
    assert barge_case["barge_in_reaction_time_ms"] is not None
    assert barge_case["barge_in_reaction_time_ms"] < 250.0, "Barge-in reaction time must be < 250ms"

    # Check Case 4 & 5: Tool Calling
    time_tool_case = next(s for s in samples if s["filename"] == "tool_current_time.wav")
    assert time_tool_case["tool_used"] == "get_current_time"
    assert time_tool_case["tool_execution_ms"] is not None

    room_tool_case = next(s for s in samples if s["filename"] == "tool_meeting_room.wav")
    assert room_tool_case["tool_used"] == "check_meeting_room"
    assert room_tool_case["tool_execution_ms"] is not None


def test_wav_audio_format_validity():
    """Verify that every audio file is a valid standard 16-bit PCM WAV at 16kHz."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for item in manifest["samples"]:
        wav_path = DATA_AUDIO_DIR / item["filename"]
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getnchannels() == item["channels"], f"Channel mismatch for {item['filename']}"
            assert wf.getsampwidth() == 2, f"Sample width must be 2 bytes (16-bit) for {item['filename']}"
            assert wf.getframerate() == item["sample_rate"], f"Sample rate mismatch for {item['filename']}"
            duration = wf.getnframes() / float(wf.getframerate())
            assert abs(duration - item["duration_seconds"]) < 0.1, f"Duration mismatch for {item['filename']}"


# ==============================================================================
# 2. Web UI Elements Verification (HTML, CSS, JS)
# ==============================================================================

def test_web_index_html_contains_latency_hud_elements():
    """Verify that web/index.html includes all required Latency Telemetry HUD and Exporter elements."""
    html_content = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    # Latency HUD container & metrics
    assert 'id="latency-hud"' in html_content
    assert 'id="e2e-ttfa"' in html_content
    assert 'id="e2e-status-badge"' in html_content
    assert 'id="server-ttfa"' in html_content
    assert 'id="network-rtt"' in html_content
    assert 'id="barge-in-time"' in html_content
    assert 'id="barge-status-badge"' in html_content

    # Percentiles
    assert 'id="p50-val"' in html_content
    assert 'id="p90-val"' in html_content
    assert 'id="p99-val"' in html_content
    assert 'id="turn-sample-count"' in html_content

    # Session Recording & Exporter controls
    assert 'id="record-session-btn"' in html_content
    assert 'id="record-dot"' in html_content
    assert 'id="record-btn-text"' in html_content
    assert 'id="export-recording-btn"' in html_content

    # Reference Case Audio section
    assert 'id="reference-samples"' in html_content
    assert "fluent_dialogue_vi.wav" in html_content
    assert "fluent_dialogue_en.wav" in html_content
    assert "barge_in_interruption.wav" in html_content
    assert "tool_current_time.wav" in html_content
    assert "tool_meeting_room.wav" in html_content


def test_web_style_css_contains_latency_hud_styles():
    """Verify that web/style.css defines styling for Latency HUD, badges, and recordings."""
    css_content = (WEB_DIR / "style.css").read_text(encoding="utf-8")

    assert ".latency-hud-card" in css_content
    assert ".latency-metrics-grid" in css_content
    assert ".latency-pill" in css_content
    assert ".latency-pill.ok" in css_content
    assert ".latency-pill.warn" in css_content
    assert ".latency-percentiles-bar" in css_content
    assert ".record-action-btn" in css_content
    assert ".reference-samples-card" in css_content


def test_web_app_js_contains_latency_and_export_logic():
    """Verify that web/app.js contains E2E TTFA calculation, percentile tracking, and WAV encoding."""
    js_content = (WEB_DIR / "app.js").read_text(encoding="utf-8")

    assert "updateE2eTtfa" in js_content
    assert "handleLatencyMetric" in js_content
    assert "recordBargeInLatency" in js_content
    assert "updatePercentiles" in js_content
    assert "encodeWav" in js_content
    assert "toggleSessionRecording" in js_content
    assert "exportRecordedWav" in js_content
    assert 'payload.type === "latency_metric"' in js_content


# ==============================================================================
# 3. WebSocket Latency Metric Dispatch Integration Test
# ==============================================================================

def test_websocket_latency_metric_forwarding_to_client():
    """Verify WebSocket client correctly receives 'latency_metric' frames from server orchestrator."""
    app = FastAPI()
    mock_orchestrator = MagicMock()
    mock_orchestrator.api_key = "mock-key"
    mock_queue = asyncio.Queue()
    mock_orchestrator.create_live_request_queue.return_value = mock_queue

    async def mock_start_live_session(audio_in_queue, event_out_callback, stop_event):
        # 1. session ready
        await event_out_callback("session_ready", {"type": "session_ready", "status": "connected"})

        # 2. Simulate latency metric event dispatched on first audio packet
        await event_out_callback(
            "latency_metric",
            {
                "type": "latency_metric",
                "ttfa_ms": 382.5,
                "server_turnaround_ms": 1250.0,
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
            websocket.send_json({"type": "session_start", "sample_rate": 16000})
            ack = websocket.receive_json()
            assert ack["type"] == "session_ack"

            ready = websocket.receive_json()
            assert ready["type"] == "session_ready"

            # 2. Receive latency_metric event
            metric = websocket.receive_json()
            assert metric["type"] == "latency_metric"
            assert metric["ttfa_ms"] == 382.5
            assert metric["server_turnaround_ms"] == 1250.0
            assert "timestamp_ms" in metric


# ==============================================================================
# 4. FastAPI Static Mount Integration Test (/data)
# ==============================================================================

def test_fastapi_data_mount_serves_manifest_and_audio():
    """Verify that FastAPI server serves sample_manifest.json and WAV files under /data."""
    with TestClient(serving_app) as client:
        # Check manifest
        resp_manifest = client.get("/data/audio_samples/sample_manifest.json")
        assert resp_manifest.status_code == 200
        manifest_data = resp_manifest.json()
        assert manifest_data["summary"]["total_samples"] == 5

        # Check WAV file streaming
        resp_wav = client.get("/data/audio_samples/fluent_dialogue_vi.wav")
        assert resp_wav.status_code == 200
        assert len(resp_wav.content) > 100000
        # First 4 bytes of WAV must be RIFF
        assert resp_wav.content[:4] == b"RIFF"
