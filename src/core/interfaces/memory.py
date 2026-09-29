"""Abstract interface for memory stores."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseMemoryStore(ABC):
    @abstractmethod
    async def get_state(self, session_id: str) -> Dict[str, Any]:
        pass
