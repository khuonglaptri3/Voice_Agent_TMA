"""Bi-directional WebSocket transport adapter."""
from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect

from src.gateway.transports.base import BaseTransport


class WebSocketTransport(BaseTransport):
    """Day 2 Dev B WebSocket gateway.

    It accepts both JSON control messages and raw PCM binary frames. Control
    messages are used to negotiate session metadata, while binary payloads are
    echoed back to the browser for contract validation and future ADK integration.
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
                    continue

                if "text" not in message:
                    continue

                text = message["text"]
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    await self.websocket.send_text(text)
                    continue

                message_type = payload.get("type")

                if message_type == "session_start":
                    ack = {
                        "type": "session_ack",
                        "status": "ok",
                        "sample_rate": payload.get("sample_rate", 16000),
                        "language": payload.get("language", "vi-VN"),
                    }
                    await self.websocket.send_json(ack)
                elif message_type == "session_stop":
                    await self.websocket.send_json({
                        "type": "session_stop",
                        "status": "stopped",
                        "reason": payload.get("reason", "user_hangup"),
                    })
                else:
                    await self.websocket.send_json({
                        "type": "control_ack",
                        "status": "received",
                        "payload": payload,
                    })
        except WebSocketDisconnect:
            return
        except Exception as exc:  # pragma: no cover - Starlette disconnect edge case
            if "Cannot call \"receive\" once a disconnect message has been received" in str(exc):
                return
            raise
