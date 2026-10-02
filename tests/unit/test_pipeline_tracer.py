"""Unit tests for PipelineTracer and Day 6 TTFA benchmarking instrumentation."""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, List
import pytest

from src.observability.tracing.pipeline_tracer import PipelineTracer, TurnTrace
from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator


def test_pipeline_tracer_record_stage_backward_compatibility():
    """Verify legacy record_stage method functions correctly with ring buffer."""
    tracer = PipelineTracer(max_records=5)
    for i in range(10):
        tracer.record_stage("session_1", f"stage_{i}", float(i * 10))

    assert len(tracer.buffer) == 5
    last_record = tracer.buffer[-1]
    assert last_record["stage"] == "stage_9"
    assert last_record["duration_ms"] == 90.0


def test_turn_trace_ttfa_and_turnaround_calculation():
    """Verify TTFA is calculated from user_speech_end (T0) to first_audio (T_first)."""
    trace = TurnTrace(turn_id="turn_1", session_id="sess_1", start_time=100.0)
    trace.mark_user_speech_end(timestamp=101.0)  # T0 = 101.0s

    ttfa = trace.mark_first_audio(timestamp=101.35)  # T_first = 101.35s
    assert ttfa == pytest.approx(350.0, rel=1e-2)

    # Calling mark_first_audio again in same turn should return identical TTFA without overwriting
    second_call = trace.mark_first_audio(timestamp=102.0)
    assert second_call == ttfa

    trace.mark_turn_complete(timestamp=102.5)  # Complete at 102.5s
    assert trace.server_turnaround_ms == pytest.approx(1500.0, rel=1e-2)

    data = trace.to_dict()
    assert data["turn_id"] == "turn_1"
    assert data["ttfa_ms"] == 350.0
    assert data["server_turnaround_ms"] == 1500.0


def test_turn_trace_tool_execution_tracking():
    """Verify tool execution time and names are recorded within the turn."""
    trace = TurnTrace(turn_id="turn_tool", session_id="sess_tool")
    trace.mark_tool_execution("get_current_time", 12.5)
    trace.mark_tool_execution("check_meeting_room", 18.2)

    assert trace.tool_names == ["get_current_time", "check_meeting_room"]
    assert trace.tool_execution_ms == pytest.approx(30.7, rel=1e-2)


def test_pipeline_tracer_percentile_calculations():
    """Verify calculation of P50, P90, P99, Mean, Min, Max percentiles."""
    tracer = PipelineTracer(max_records=100)

    # Insert 100 deterministic turns with TTFA from 100ms to 199ms
    for i in range(100):
        t_id = f"t_{i}"
        tracer.start_turn(t_id, timestamp=0.0)
        tracer.mark_user_speech_end(t_id, timestamp=0.0)
        tracer.mark_first_audio_chunk(t_id, timestamp=(100.0 + i) / 1000.0)
        tracer.mark_turn_complete(t_id, timestamp=(500.0 + i) / 1000.0)

    percentiles = tracer.calculate_percentiles("ttfa_ms")
    assert percentiles["count"] == 100
    assert percentiles["min"] == 100.0
    assert percentiles["max"] == 199.0
    assert percentiles["p50"] == pytest.approx(149.5, abs=1.0)
    assert percentiles["p90"] == pytest.approx(189.1, abs=1.5)
    assert percentiles["p99"] == pytest.approx(198.0, abs=1.5)


def test_latency_metric_payload_format():
    """Verify latency_metric payload complies with section 2.1 contract."""
    tracer = PipelineTracer()
    tracer.start_turn("turn_contract", session_id="sess_1")
    tracer.mark_user_speech_end("turn_contract", timestamp=10.0)
    tracer.record_tool_execution("turn_contract", "get_current_time", 15.4)
    tracer.mark_first_audio_chunk("turn_contract", timestamp=10.412)
    tracer.mark_turn_complete("turn_contract", timestamp=10.732)

    payload = tracer.create_latency_metric_payload("turn_contract")
    assert payload["type"] == "latency_metric"
    assert payload["ttfa_ms"] == pytest.approx(412.0, abs=0.1)
    assert payload["tool_execution_ms"] == pytest.approx(15.4, abs=0.1)
    assert "timestamp_ms" in payload


def test_export_benchmark_json(tmp_path):
    """Verify export_benchmark_json creates valid file with summary and turn records."""
    tracer = PipelineTracer()
    for i in range(5):
        t_id = f"turn_{i}"
        tracer.start_turn(t_id)
        tracer.mark_user_speech_end(t_id)
        tracer.mark_first_audio_chunk(t_id)
        tracer.mark_turn_complete(t_id)

    out_file = str(tmp_path / "test_benchmark.json")
    metadata = {"test_run": True, "total_turns": 5}
    report = tracer.export_benchmark_json(output_path=out_file, metadata=metadata)

    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["metadata"]["test_run"] is True
    assert loaded["summary"]["total_turns"] == 5
    assert len(loaded["turns"]) == 5


@pytest.mark.asyncio
async def test_orchestrator_dispatches_latency_metric_events():
    """Verify ADKLiveOrchestrator dispatches latency_metric events on first audio and turn complete."""
    tracer = PipelineTracer()
    orchestrator = ADKLiveOrchestrator(voice_name="Puck", pipeline_tracer=tracer)

    dispatched_events: List[tuple[str, Any]] = []

    async def callback(ev_type: str, data: Any):
        dispatched_events.append((ev_type, data))

    # Mock Gemini Live session yielding:
    # 1. user input transcription (sets T0)
    # 2. model audio chunk (triggers first_audio TTFA latency_metric)
    # 3. turn_complete (triggers final turnaround latency_metric)
    class MockPart:
        def __init__(self, data=None):
            if data:
                class InlineData:
                    pass
                self.inline_data = InlineData()
                self.inline_data.data = data
            else:
                self.inline_data = None
            self.text = None

    class MockModelTurn:
        def __init__(self, data):
            self.parts = [MockPart(data)]

    class MockTranscription:
        def __init__(self, text):
            self.text = text

    class MockServerContent:
        def __init__(self, input_text=None, audio_data=None, turn_complete=False):
            self.input_transcription = MockTranscription(input_text) if input_text else None
            self.interim_input_transcription = None
            self.output_transcription = None
            self.model_turn = MockModelTurn(audio_data) if audio_data else None
            self.turn_complete = turn_complete
            self.interrupted = False
            self.generation_complete = False

    class MockResponse:
        def __init__(self, server_content=None):
            self.server_content = server_content
            self.tool_call = None
            self.tool_call_cancellation = None

    mock_responses = [
        MockResponse(MockServerContent(input_text="Xin chào")),
        MockResponse(MockServerContent(audio_data=b"\x01\x02" * 160)),
        MockResponse(MockServerContent(turn_complete=True)),
    ]

    class MockSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def receive(self):
            for r in mock_responses:
                yield r

        async def send_realtime_input(self, media):
            pass

    class MockLive:
        def connect(self, model, config):
            return MockSession()

    class MockAio:
        def __init__(self):
            self.live = MockLive()

    class MockClient:
        def __init__(self):
            self.aio = MockAio()

    orchestrator._client = MockClient()
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = asyncio.Event()

    await orchestrator.start_live_session(
        audio_in_queue=queue,
        event_out_callback=callback,
        stop_event=stop_event,
    )

    event_types = [ev[0] for ev in dispatched_events]
    assert "latency_metric" in event_types

    latency_metrics = [ev[1] for ev in dispatched_events if ev[0] == "latency_metric"]
    assert len(latency_metrics) >= 1
    first_metric = latency_metrics[0]
    assert first_metric["type"] == "latency_metric"
    assert "ttfa_ms" in first_metric
    assert "server_turnaround_ms" in first_metric
