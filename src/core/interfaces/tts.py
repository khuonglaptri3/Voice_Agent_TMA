"""Abstract interface for Text-to-Speech services."""
from abc import ABC, abstractmethod
from typing import AsyncIterator

class BaseTTSService(ABC):
    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        pass
