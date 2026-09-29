"""Sliding window buffer with atomic turn-pair pruning."""
class SlidingWindowBuffer:
    def __init__(self, max_pairs: int = 5):
        self.max_pairs = max_pairs
        self.messages = []
