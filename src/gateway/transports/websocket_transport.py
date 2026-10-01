"""WebSocket transport between the browser and the live voice orchestrator."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

from fastapi import WebSocket, WebSocketDisconnect

from src.gateway.transports.base import BaseTransport
from src.orchestration.engine.turn_orchestrator import ADKLiveOrchestrator, VoicePersona

logger = logging.getLogger(__name__)


class WebSocketTransport(BaseTransport):
    """Route browser PCM frames to ADK and live events back to the browser."""

    def __init__(
        self,
        websocket: WebSocket | None = None,
        orchestrator_factory: Optional[Callable[[], ADKLiveOrchestrator]] = None,
    ) -> None:
        self.websocket = websocket
        self._send_lock = asyncio.Lock()
        self._orchestrator_factory = orchestrator_factory or ADKLiveOrchestrator

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self.websocket is None:
            return
        async with self._send_lock:
            await self.websocket.send_json(payload)

    async def _send_event(self, event_type: str, payload: Any) -> None:
        if self.websocket is None:
            return

        async with self._send_lock:
            if event_type == "audio":
                await self.websocket.send_bytes(payload)
            elif isinstance(payload, dict):
                await self.websocket.send_json(payload)
            else:
                await self.websocket.send_json({"type": event_type, "data": payload})

    async def _stop_session(
        self,
        audio_queue: asyncio.Queue | None,
        stop_event: asyncio.Event | None,
        session_task: asyncio.Task | None,
    ) -> None:
        if stop_event is not None:
            stop_event.set()
        if audio_queue is not None:
            audio_queue.put_nowait(None)
        if session_task is not None and not session_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(session_task), timeout=2.0)
            except asyncio.TimeoutError:
                session_task.cancel()
                await asyncio.gather(session_task, return_exceptions=True)

    async def _run_live_session(
        self,
        orchestrator: ADKLiveOrchestrator,
        audio_queue: asyncio.Queue,
        stop_event: asyncio.Event,
    ) -> None:
        try:
            await orchestrator.start_live_session(
                audio_in_queue=audio_queue,
                event_out_callback=self._send_event,
                stop_event=stop_event,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Live orchestrator session failed")
            try:
                await self._send_json({
                    "type": "error",
                    "code": "live_session_failed",
                    "message": str(exc),
                })
            except (WebSocketDisconnect, RuntimeError):
                pass
            stop_event.set()

    async def start(self):
        if self.websocket is None:
            raise RuntimeError("WebSocketTransport requires a FastAPI WebSocket instance.")

        await self.websocket.accept()
        orchestrator = None
        audio_queue = None
        stop_event = None
        session_task = None

        try:
            while True:
                message = await self.websocket.receive()

                if "bytes" in message:
                    if audio_queue is None:
                        await self._send_json({
                            "type": "error",
                            "code": "session_not_started",
                            "message": "Send session_start before audio frames.",
                        })
                    else:
                        await audio_queue.put(message["bytes"])
                    continue

                if "text" not in message:
                    continue

                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    await self._send_json({
                        "type": "error",
                        "code": "invalid_json",
                        "message": "Control messages must be valid JSON.",
                    })
                    continue

                message_type = payload.get("type")
                if message_type == "session_start":
                    if audio_queue is not None:
                        await self._send_json({"type": "session_ack", "status": "already_started"})
                        continue
                    if payload.get("sample_rate", 16000) != 16000:
                        await self._send_json({
                            "type": "error",
                            "code": "unsupported_sample_rate",
                            "message": "The live audio input contract requires 16000 Hz PCM.",
                        })
                        continue

                    voice_name = payload.get("voice", "Puck")
                    persona_name = payload.get("persona", "default")
                    try:
                        orchestrator = self._orchestrator_factory(
                            voice_name=voice_name,
                            system_instruction=VoicePersona.get_persona(persona_name) if "persona" in payload else None,
                        )
                    except TypeError:
                        orchestrator = self._orchestrator_factory()
                    except ValueError as ve:
                        await self._send_json({
                            "type": "error",
                            "code": "invalid_voice",
                            "message": str(ve),
                        })
                        continue

                    if not orchestrator.api_key:
                        await self._send_json({
                            "type": "error",
                            "code": "missing_api_key",
                            "message": "Configure GOOGLE_API_KEY before starting a live session.",
                        })
                        orchestrator = None
                        continue

                    audio_queue = orchestrator.create_live_request_queue()
                    stop_event = asyncio.Event()
                    await self._send_json({
                        "type": "session_ack",
                        "status": "connecting",
                        "sample_rate": 16000,
                        "language": payload.get("language", "vi-VN"),
                    })
                    session_task = asyncio.create_task(
                        self._run_live_session(orchestrator, audio_queue, stop_event)
                    )
                elif message_type == "session_stop":
                    await self._stop_session(audio_queue, stop_event, session_task)
                    audio_queue = None
                    stop_event = None
                    session_task = None
                    orchestrator = None
                    await self._send_json({
                        "type": "session_stop",
                        "status": "stopped",
                        "reason": payload.get("reason", "user_hangup"),
                    })
                else:
                    await self._send_json({
                        "type": "error",
                        "code": "unsupported_message",
                        "message": f"Unsupported control message: {message_type}",
                    })
        except WebSocketDisconnect:
            return
        except Exception as exc:
            if "disconnect message has been received" in str(exc):
                return
            raise
        finally:
            await self._stop_session(audio_queue, stop_event, session_task)