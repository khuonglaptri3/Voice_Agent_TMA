"""Scanner stripping action markers from token stream before TTS."""
import re

class ActionMarkerParser:
    MARKER_REGEX = re.compile(r'\[ACTION:([A-Z_]+)\s*(.*?)\]')

    def parse_and_strip(self, text: str):
        markers = self.MARKER_REGEX.findall(text)
        cleaned_text = self.MARKER_REGEX.sub('', text)
        return cleaned_text, markers
