"""Abstract interface for LLM providers."""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncIterator[str]:
        pass
