"""Pipeline Tracer - Low-latency stage profiling and TTFA benchmark instrumentation.

Tracks time-to-first-audio (TTFA), tool execution time, and server turnaround latency
for full-duplex voice agent turns, calculating P50/P90/P99 percentiles according to
the Day 6 specifications.
"""
from __future__ import annotations

from collections import deque
import json
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np


class TurnTrace:
    """State tracker for a single conversation turn."""

    def __init__(self, turn_id: str, session_id: str = "default", start_time: Optional[float] = None) -> None:
        self.turn_id = turn_id
        self.session_id = session_id
        self.start_time = start_time if start_time is not None else time.perf_counter()
        self.user_speech_end_time: Optional[float] = None
        self.first_audio_chunk_time: Optional[float] = None
        self.turn_complete_time: Optional[float] = None
        self.tool_execution_ms: float = 0.0
        self.tool_names: List[str] = []
        self.stages: Dict[str, float] = {}
        self.ttfa_ms: Optional[float] = None
        self.server_turnaround_ms: Optional[float] = None
        self.is_interrupted: bool = False

    def mark_user_speech_end(self, timestamp: Optional[float] = None) -> None:
        """Mark T0: the instant user finished speaking."""
        self.user_speech_end_time = timestamp if timestamp is not None else time.perf_counter()

    def mark_first_audio(self, timestamp: Optional[float] = None) -> Optional[float]:
        """Mark T_first_chunk: the instant the first model audio chunk arrives.

        Returns:
            Calculated TTFA in milliseconds, or None if already marked.
        """
        if self.first_audio_chunk_time is not None:
            return self.ttfa_ms  # Already recorded for this turn

        self.first_audio_chunk_time = timestamp if timestamp is not None else time.perf_counter()
        baseline = self.user_speech_end_time if self.user_speech_end_time is not None else self.start_time
        self.ttfa_ms = max(0.0, (self.first_audio_chunk_time - baseline) * 1000.0)
        return self.ttfa_ms

    def mark_tool_execution(self, tool_name: str, duration_ms: float) -> None:
        """Record tool execution duration in ms."""
        self.tool_names.append(tool_name)
        self.tool_execution_ms += duration_ms

    def mark_turn_complete(self, timestamp: Optional[float] = None) -> None:
        """Mark turn complete and compute overall turnaround time."""
        self.turn_complete_time = timestamp if timestamp is not None else time.perf_counter()
        baseline = self.user_speech_end_time if self.user_speech_end_time is not None else self.start_time
        self.server_turnaround_ms = max(0.0, (self.turn_complete_time - baseline) * 1000.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert turn record to dictionary."""
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "ttfa_ms": round(self.ttfa_ms, 2) if self.ttfa_ms is not None else None,
            "server_turnaround_ms": (
                round(self.server_turnaround_ms, 2) if self.server_turnaround_ms is not None else None
            ),
            "tool_execution_ms": round(self.tool_execution_ms, 2),
            "tool_names": list(self.tool_names),
            "is_interrupted": self.is_interrupted,
            "timestamp": time.time(),
        }


class PipelineTracer:
    """Thread-safe circular ring buffer and profiler for sub-millisecond stage latencies."""

    def __init__(self, max_records: int = 1000) -> None:
        self.max_records = max_records
        self.buffer: deque[dict[str, Any]] = deque(maxlen=max_records)
        self.completed_turns: deque[dict[str, Any]] = deque(maxlen=max_records)
        self.active_turns: dict[str, TurnTrace] = {}
        self.lock = threading.Lock()

    def record_stage(self, session_id: str, stage_name: str, duration_ms: float) -> None:
        """Record a single pipeline stage duration (backward compatible)."""
        with self.lock:
            self.buffer.append({
                "session_id": session_id,
                "stage": stage_name,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            })

    def start_turn(
        self,
        turn_id: str,
        session_id: str = "default",
        timestamp: Optional[float] = None,
    ) -> TurnTrace:
        """Initialize and track a new conversational turn."""
        with self.lock:
            trace = TurnTrace(turn_id=turn_id, session_id=session_id, start_time=timestamp)
            self.active_turns[turn_id] = trace
            return trace

    def get_or_create_turn(
        self,
        turn_id: str,
        session_id: str = "default",
    ) -> TurnTrace:
        """Retrieve existing turn trace or create one if not found."""
        with self.lock:
            if turn_id not in self.active_turns:
                self.active_turns[turn_id] = TurnTrace(turn_id=turn_id, session_id=session_id)
            return self.active_turns[turn_id]

    def mark_user_speech_end(
        self,
        turn_id: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """Mark T0 (user finished speaking) for a turn."""
        with self.lock:
            trace = self.active_turns.get(turn_id)
            if trace:
                trace.mark_user_speech_end(timestamp)

    def mark_first_audio_chunk(
        self,
        turn_id: str,
        timestamp: Optional[float] = None,
    ) -> Optional[float]:
        """Mark arrival of first model audio frame (T_first_chunk) and compute TTFA."""
        with self.lock:
            trace = self.active_turns.get(turn_id)
            if trace:
                return trace.mark_first_audio(timestamp)
            return None

    def record_tool_execution(
        self,
        turn_id: str,
        tool_name: str,
        duration_ms: float,
    ) -> None:
        """Record execution duration of a tool within a turn."""
        with self.lock:
            trace = self.active_turns.get(turn_id)
            if trace:
                trace.mark_tool_execution(tool_name, duration_ms)

    def mark_turn_interrupted(self, turn_id: str) -> None:
        """Flag that this turn was interrupted by the user (barge-in)."""
        with self.lock:
            trace = self.active_turns.get(turn_id)
            if trace:
                trace.is_interrupted = True

    def mark_turn_complete(
        self,
        turn_id: str,
        timestamp: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Finalize turn tracking, compute turnaround time, and archive to history."""
        with self.lock:
            trace = self.active_turns.pop(turn_id, None)
            if trace:
                trace.mark_turn_complete(timestamp)
                record = trace.to_dict()
                self.completed_turns.append(record)
                return record
            return None

    def create_latency_metric_payload(
        self,
        turn_id: str,
    ) -> Dict[str, Any]:
        """Build standardized latency_metric message adhering to the contract in section 2.1."""
        with self.lock:
            trace = self.active_turns.get(turn_id)
            if trace is None:
                # Check recent completed turns
                for completed in reversed(self.completed_turns):
                    if completed.get("turn_id") == turn_id:
                        payload: Dict[str, Any] = {
                            "type": "latency_metric",
                            "ttfa_ms": completed.get("ttfa_ms") or 0.0,
                            "server_turnaround_ms": completed.get("server_turnaround_ms") or 0.0,
                            "timestamp_ms": int(time.time() * 1000),
                        }
                        if completed.get("tool_execution_ms", 0) > 0:
                            payload["tool_execution_ms"] = completed["tool_execution_ms"]
                        return payload

            ttfa = trace.ttfa_ms if trace and trace.ttfa_ms is not None else 0.0
            turnaround = trace.server_turnaround_ms if trace and trace.server_turnaround_ms is not None else 0.0
            tool_ms = trace.tool_execution_ms if trace else 0.0

        payload: Dict[str, Any] = {
            "type": "latency_metric",
            "ttfa_ms": round(ttfa, 2),
            "server_turnaround_ms": round(turnaround, 2),
            "timestamp_ms": int(time.time() * 1000),
        }
        if tool_ms > 0:
            payload["tool_execution_ms"] = round(tool_ms, 2)
        return payload

    def calculate_percentiles(self, metric_name: str = "ttfa_ms") -> Dict[str, float]:
        """Calculate P50, P90, P99, mean, min, and max for the specified metric."""
        with self.lock:
            values = [
                turn[metric_name]
                for turn in self.completed_turns
                if turn.get(metric_name) is not None
            ]

        if not values:
            return {
                "count": 0,
                "p50": 0.0,
                "p90": 0.0,
                "p99": 0.0,
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0,
            }

        arr = np.array(values, dtype=float)
        return {
            "count": len(arr),
            "p50": round(float(np.percentile(arr, 50)), 2),
            "p90": round(float(np.percentile(arr, 90)), 2),
            "p99": round(float(np.percentile(arr, 99)), 2),
            "mean": round(float(np.mean(arr)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Return comprehensive latency summary across all metrics."""
        return {
            "ttfa": self.calculate_percentiles("ttfa_ms"),
            "server_turnaround": self.calculate_percentiles("server_turnaround_ms"),
            "tool_execution": self.calculate_percentiles("tool_execution_ms"),
            "total_turns": len(self.completed_turns),
            "active_turns": len(self.active_turns),
        }

    def export_benchmark_json(
        self,
        output_path: str = "data/benchmark_results.json",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export benchmark measurements to JSON file according to DoD Day 6."""
        summary = self.get_summary()
        with self.lock:
            turns_data = list(self.completed_turns)

        report = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metadata": metadata or {},
            "summary": summary,
            "turns": turns_data,
        }

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return report

    def clear(self) -> None:
        """Reset all active and completed records."""
        with self.lock:
            self.buffer.clear()
            self.completed_turns.clear()
            self.active_turns.clear()


# Global default instance for convenience
global_pipeline_tracer = PipelineTracer()
