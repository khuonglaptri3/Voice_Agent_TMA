"""Streaming sentence boundary splitter for low-latency TTS dispatch."""
import re

class StreamingSentenceSplitter:
    PUNCTUATION_REGEX = re.compile(r'([.?!,;\n])')

    def split_stream(self, token_stream):
        buffer = []
        for token in token_stream:
            buffer.append(token)
            if self.PUNCTUATION_REGEX.search(token):
                yield "".join(buffer)
                buffer = []
        if buffer:
            yield "".join(buffer)
