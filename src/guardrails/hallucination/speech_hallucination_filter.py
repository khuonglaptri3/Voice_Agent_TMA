"""ASR Hallucination Filter with Unique_Ratio threshold < 0.40."""
class ASRHallucinationFilter:
    def is_valid_transcription(self, text: str) -> bool:
        tokens = text.lower().split()
        if not tokens:
            return False
        unique_ratio = len(set(tokens)) / len(tokens)
        if unique_ratio < 0.40:
            return False
        return True
