"""Abstract interface for tools and external actions."""
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        pass
