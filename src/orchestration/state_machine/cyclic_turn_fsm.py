"""Cyclic turn state machine (LISTENING, THINKING, SPEAKING)."""
class CyclicTurnFSM:
    def __init__(self):
        self.state = "LISTENING"
