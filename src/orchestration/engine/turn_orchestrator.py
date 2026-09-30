"""turn_orchestrator.py
--------------------
Orchestration engine for bidirectional Speech-to-Speech sessions (Day 2 - Dev A).

Connects client incoming audio queues to Gemini Live Multimodal streaming session,
and routes outgoing audio chunks, live transcripts, and interruption signals back
to the caller.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from typing import Any, Awaitable, Callable, Optional

from dotenv import load_dotenv

load_dotenv()

# Tự động nạp CA cert hệ thống nếu SSL_CERT_FILE chưa được đặt (tránh lỗi SSL trên mạng TMA)
if "SSL_CERT_FILE" not in os.environ:
    for ca_path in ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]:
        if os.path.isfile(ca_path):
            os.environ["SSL_CERT_FILE"] = ca_path
            break

from config.settings import settings

logger = logging.getLogger(__name__)

# LiveRequestQueue: Alias to asyncio.Queue or ADK LiveRequestQueue if available
try:
    from google.adk.runners import LiveRequestQueue  # type: ignore
except ImportError:
    LiveRequestQueue = asyncio.Queue  # type: ignore


class ADKLiveOrchestrator:
    """Manages real-time bidirectional streaming sessions with Gemini Live API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice_name: str = "Puck",
        system_instruction: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "GOOGLE_API_KEY", None) or os.getenv("GOOGLE_API_KEY")
        self.model = model or getattr(settings, "GEMINI_LIVE_MODEL", None) or os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")
        self.voice_name = voice_name
        self.system_instruction = system_instruction or (
            "Bạn là Trợ lý giọng nói thông minh bằng tiếng Việt của TMA Solutions. "
            "Hãy trả lời thật ngắn gọn, súc tích (dưới 2 câu), thân thiện và tự nhiên. "
            "Tuyệt đối không dùng ký tự Markdown, code block hay bảng biểu."
        )
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from google import genai
        return genai.Client(api_key=self.api_key)

    def create_live_request_queue(self) -> asyncio.Queue:
        """Create an asynchronous queue for incoming audio chunks."""
        return asyncio.Queue()

    async def _safe_dispatch(
        self,
        callback: Callable[[str, Any], Any],
        event_type: str,
        payload: Any,
    ) -> None:
        """Dispatch event to callback regardless of whether it is sync or async."""
        try:
            res = callback(event_type, payload)
            if inspect.isawaitable(res):
                await res
        except Exception as exc:
            logger.error(f"Error in event callback for '{event_type}': {exc}", exc_info=True)

    async def start_live_session(
        self,
        audio_in_queue: asyncio.Queue,
        event_out_callback: Callable[[str, Any], Any],
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        """Start full-duplex live session.

        Task 1 (Client -> Live Session): Reads PCM audio chunks from audio_in_queue and
        streams them to Gemini Live via send_realtime_input().

        Task 2 (Live Session -> Client): Listens for Gemini Live events and routes
        audio frames, transcriptions, and barge-in signals to event_out_callback.
        """
        from google.genai import types

        stop_event = stop_event or asyncio.Event()
        client = self._get_client()

        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice_name
                    )
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=self.system_instruction)]
            ),
        )

        async with client.aio.live.connect(model=self.model, config=config) as session:
            logger.info("Connected to Gemini Live session successfully.")
            await self._safe_dispatch(
                event_out_callback,
                "session_ready",
                {"type": "session_ready", "status": "connected"},
            )

            async def send_audio_worker():
                """Continuously read audio frames from queue and stream to Gemini."""
                try:
                    while not stop_event.is_set():
                        try:
                            # Use timeout to regularly check stop_event
                            chunk = await asyncio.wait_for(audio_in_queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            continue

                        if chunk is None:  # Sentinel indicating end of stream
                            break

                        await session.send_realtime_input(
                            media=types.Blob(
                                data=chunk,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    if not stop_event.is_set():
                        logger.error(f"Error sending audio to Gemini Live: {exc}", exc_info=True)

            async def receive_events_worker():
                """Listen for server responses: audio chunks, transcripts, and barge-in."""
                try:
                    async for response in session.receive():
                        if stop_event.is_set():
                            break

                        server_content = getattr(response, "server_content", None)
                        if not server_content:
                            continue

                        # 1. Handle Barge-in Interruption
                        if getattr(server_content, "interrupted", False):
                            await self._safe_dispatch(
                                event_out_callback,
                                "interrupted",
                                {
                                    "type": "interrupted",
                                    "timestamp_ms": int(time.time() * 1000),
                                    "reason": "user_barge_in",
                                },
                            )
                            continue

                        # 2. Handle User Transcription
                        input_transcription = getattr(server_content, "input_transcription", None)
                        if input_transcription and getattr(input_transcription, "text", None):
                            await self._safe_dispatch(
                                event_out_callback,
                                "transcript",
                                {
                                    "type": "transcript",
                                    "role": "user",
                                    "text": input_transcription.text,
                                    "is_final": True,
                                },
                            )

                        # 3. Handle Model Turn (Audio & Agent Text)
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn and getattr(model_turn, "parts", None):
                            for part in model_turn.parts:
                                if getattr(part, "text", None):
                                    await self._safe_dispatch(
                                        event_out_callback,
                                        "transcript",
                                        {
                                            "type": "transcript",
                                            "role": "agent",
                                            "text": part.text,
                                            "is_final": False,
                                        },
                                    )
                                inline_data = getattr(part, "inline_data", None)
                                if inline_data and getattr(inline_data, "data", None):
                                    await self._safe_dispatch(
                                        event_out_callback,
                                        "audio",
                                        inline_data.data,
                                    )

                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    if not stop_event.is_set():
                        logger.error(f"Error receiving events from Gemini Live: {exc}", exc_info=True)

            send_task = asyncio.create_task(send_audio_worker())
            recv_task = asyncio.create_task(receive_events_worker())

            # Wait until stop_event is set or one of the tasks finishes
            try:
                while not stop_event.is_set():
                    done, _ = await asyncio.wait(
                        [send_task, recv_task],
                        timeout=0.1,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if done:
                        break
            finally:
                send_task.cancel()
                recv_task.cancel()
                await asyncio.gather(send_task, recv_task, return_exceptions=True)


class TurnOrchestrator(ADKLiveOrchestrator):
    """Backward-compatible alias for TurnOrchestrator."""
    async def execute_turn(self, audio_stream: Any) -> None:
        pass
