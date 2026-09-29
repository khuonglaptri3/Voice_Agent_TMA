"""Turn boundary detector based on silence duration and speech ratio."""
class TurnDetector:
    def is_turn_complete(self, speech_probability_history: list) -> bool:
        return False
