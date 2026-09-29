"""Base transport contract."""
from abc import ABC, abstractmethod

class BaseTransport(ABC):
    @abstractmethod
    async def start(self): pass
