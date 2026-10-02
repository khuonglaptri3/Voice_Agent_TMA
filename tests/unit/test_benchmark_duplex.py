"""Unit tests for Day 6 benchmark script and dataset."""
from __future__ import annotations

import json
import os
import pytest

from scripts.benchmark_duplex import (
    BENCHMARK_PROMPTS_EN,
    BENCHMARK_PROMPTS_VI,
    run_simulation_benchmark,
)
from src.observability.tracing.pipeline_tracer import PipelineTracer


def test_benchmark_prompts_count_and_structure():
    """Verify that Day 6 prompts contain exactly 10 Vietnamese and 10 English turns."""
    assert len(BENCHMARK_PROMPTS_VI) == 10
    assert len(BENCHMARK_PROMPTS_EN) == 10

    # Ensure required tool queries exist in both languages
    vi_tools = [p.get("tool") for p in BENCHMARK_PROMPTS_VI if "tool" in p]
    en_tools = [p.get("tool") for p in BENCHMARK_PROMPTS_EN if "tool" in p]

    assert "get_current_time" in vi_tools
    assert "check_meeting_room" in vi_tools
    assert "get_current_time" in en_tools
    assert "check_meeting_room" in en_tools


@pytest.mark.asyncio
async def test_run_simulation_benchmark_generates_20_turns():
    """Verify simulation benchmark creates exactly 20 turns with valid TTFA percentiles."""
    tracer = PipelineTracer(max_records=50)
    await run_simulation_benchmark(tracer, fast_mode=True)

    assert len(tracer.completed_turns) == 20

    summary = tracer.get_summary()
    assert summary["ttfa"]["count"] == 20
    assert summary["ttfa"]["p50"] > 0
    assert summary["ttfa"]["p90"] >= summary["ttfa"]["p50"]
    assert summary["ttfa"]["p99"] >= summary["ttfa"]["p90"]

    # Verify tool execution metrics recorded for the turns with tools
    assert summary["tool_execution"]["count"] == 20
    assert summary["tool_execution"]["max"] > 0


def test_benchmark_results_json_schema():
    """Verify data/benchmark_results.json exists and satisfies Day 6 DoD requirements."""
    results_path = "data/benchmark_results.json"
    assert os.path.exists(results_path), "data/benchmark_results.json must exist"

    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "generated_at" in data
    assert "metadata" in data
    assert "summary" in data
    assert "turns" in data

    assert data["metadata"]["total_turns"] >= 20
    assert len(data["turns"]) >= 20

    summary = data["summary"]
    assert "ttfa" in summary
    assert "server_turnaround" in summary
    assert "p50" in summary["ttfa"]
    assert "p90" in summary["ttfa"]
    assert "p99" in summary["ttfa"]
