"""Strips Markdown, code blocks, and URLs before TTS."""
import re

class TTSTextCleaner:
    @staticmethod
    def clean_for_speech(text: str) -> str:
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'[*_#`~]', '', text)
        return text.strip()
