"""Thread-safe circular ring buffer for sub-millisecond stage latencies."""
from collections import deque
import threading
import time

class PipelineTracer:
    def __init__(self, max_records: int = 1000):
        self.buffer = deque(maxlen=max_records)
        self.lock = threading.Lock()

    def record_stage(self, session_id: str, stage_name: str, duration_ms: float):
        with self.lock:
            self.buffer.append({
                "session_id": session_id,
                "stage": stage_name,
                "duration_ms": duration_ms,
                "timestamp": time.time()
            })
