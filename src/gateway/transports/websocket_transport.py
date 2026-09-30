"""Bi-directional WebSocket transport adapter."""
from __future__ import annotations

from fastapi import WebSocket, WebSocketDisconnect

from src.gateway.transports.base import BaseTransport


class WebSocketTransport(BaseTransport):
    """Tiny WebSocket adapter used by the Dev B Day 1 PoC.

    The gateway accepts binary PCM frames from the browser and immediately echoes
    them back for a simple round-trip validation of the raw audio contract.
    """

    def __init__(self, websocket: WebSocket | None = None):
        self.websocket = websocket

    async def start(self):
        if self.websocket is None:
            raise RuntimeError("WebSocketTransport requires a FastAPI WebSocket instance.")

        await self.websocket.accept()

        try:
            while True:
                message = await self.websocket.receive()

                if "bytes" in message:
                    await self.websocket.send_bytes(message["bytes"])
                elif "text" in message:
                    await self.websocket.send_text(message["text"])
        except WebSocketDisconnect:
            return
        except Exception as exc:  # pragma: no cover - Starlette disconnect edge case
            if "Cannot call \"receive\" once a disconnect message has been received" in str(exc):
                return
            raise
