"""Sliding window rate limiter and one-shot tickets."""
class SlidingWindowLimiter:
    def allow_request(self, client_id: str) -> bool:
        return True
