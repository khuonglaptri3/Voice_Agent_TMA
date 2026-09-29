"""HTTP REST and SSE transport adapter."""
from src.gateway.transports.base import BaseTransport

class FastAPITransport(BaseTransport):
    async def start(self):
        pass
