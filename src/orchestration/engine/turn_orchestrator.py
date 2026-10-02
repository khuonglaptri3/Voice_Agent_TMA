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


SUPPORTED_VOICES = ("Puck", "Charon", "Kore", "Fenrir", "Aoede")


class VoicePersona:
    """Manages system instruction personas tailored for real-time Vietnamese speech synthesis."""

    TEMPLATES: dict[str, str] = {
        "default": (
            "Bạn là Trợ lý giọng nói thông minh bằng tiếng Việt của TMA Solutions. "
            "Quy tắc phản hồi qua giọng nói:\n"
            "1. Luôn trả lời ngắn gọn, súc tích, tối đa dưới 2 câu.\n"
            "2. Sử dụng văn phong giao tiếp tự nhiên, lịch sự (dạ, thưa, ạ).\n"
            "3. Tuyệt đối KHÔNG dùng ký tự định dạng Markdown (như *, **, #, gạch đầu dòng, danh sách số), "
            "không dùng code block, không dùng bảng biểu để tránh lỗi phát âm TTS."
        ),
        "concise": (
            "Bạn là trợ lý tiếng Việt siêu ngắn gọn của TMA Solutions. "
            "Chỉ trả lời trong đúng 1 hoặc 2 câu ngắn. "
            "Tuyệt đối không dùng Markdown, danh sách liệt kê hay ký tự đặc biệt."
        ),
        "customer_service": (
            "Bạn là nhân viên lễ tân, chăm sóc khách hàng bằng tiếng Việt của TMA Solutions. "
            "Giao tiếp cực kỳ lịch thiệp, niềm nở ('Dạ em nghe', 'Dạ vâng ạ'). "
            "Trả lời ngắn gọn dưới 2 câu. Tuyệt đối không dùng định dạng Markdown hay ký tự lạ."
        ),
    }

    @classmethod
    def get_persona(cls, name: str = "default") -> str:
        """Get persona system instruction by name."""
        return cls.TEMPLATES.get(name, cls.TEMPLATES["default"])


class ADKLiveOrchestrator:
    """Manages real-time bidirectional streaming sessions with Gemini Live API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice_name: str = "Puck",
        system_instruction: Optional[str] = None,
        client: Optional[Any] = None,
        tools: Optional[list[Any]] = None,
        tool_registry: Optional[dict[str, Callable]] = None,
    ) -> None:
        if voice_name not in SUPPORTED_VOICES:
            raise ValueError(
                f"Unsupported voice '{voice_name}'. Supported voices are: {', '.join(SUPPORTED_VOICES)}"
            )
        self.api_key = api_key or getattr(settings, "GOOGLE_API_KEY", None) or os.getenv("GOOGLE_API_KEY")
        self.model = model or getattr(settings, "GEMINI_LIVE_MODEL", None) or os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")
        self.voice_name = voice_name
        self.system_instruction = system_instruction or VoicePersona.get_persona("default")
        self._client = client

        from src.tools.sample_tools import SAMPLE_TOOLS, TOOL_REGISTRY
        self.tools = tools if tools is not None else list(SAMPLE_TOOLS)
        self.tool_registry = tool_registry if tool_registry is not None else dict(TOOL_REGISTRY)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        from google import genai
        return genai.Client(api_key=self.api_key)

    @staticmethod
    def reset_audio_queue(queue: asyncio.Queue) -> int:
        """Drain and clear all pending audio chunks in the input queue upon interruption."""
        drained = 0
        while not queue.empty():
            try:
                queue.get_nowait()
                try:
                    queue.task_done()
                except ValueError:
                    pass
                drained += 1
            except asyncio.QueueEmpty:
                break
        return drained

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

        config_kwargs: dict[str, Any] = {
            "response_modalities": [types.Modality.AUDIO],
            "thinking_config": types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.LOW
            ),
            "speech_config": types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self.voice_name
                    )
                )
            ),
            "input_audio_transcription": types.AudioTranscriptionConfig(),
            "output_audio_transcription": types.AudioTranscriptionConfig(),
            "system_instruction": types.Content(
                parts=[types.Part.from_text(text=self.system_instruction)]
            ),
        }
        if self.tools:
            config_kwargs["tools"] = self.tools

        config = types.LiveConnectConfig(**config_kwargs)

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
                is_interrupted = False
                try:
                    async for response in session.receive():
                        if stop_event.is_set():
                            break

                        # 0. Handle Mid-Speech Tool Calling (Day 5 - Dev A)
                        tool_call = getattr(response, "tool_call", None)
                        if tool_call and getattr(tool_call, "function_calls", None):
                            for call in tool_call.function_calls:
                                call_name = getattr(call, "name", "")
                                call_id = getattr(call, "id", "")
                                call_args = getattr(call, "args", {}) or {}

                                # Notify client: tool status "executing"
                                await self._safe_dispatch(
                                    event_out_callback,
                                    "tool_event",
                                    {
                                        "type": "tool_event",
                                        "tool_name": call_name,
                                        "status": "executing",
                                        "params": call_args,
                                        "call_id": call_id,
                                        "timestamp_ms": int(time.time() * 1000),
                                    },
                                )

                                # Execute registered tool
                                t_tool_start = time.perf_counter()
                                fn = self.tool_registry.get(call_name)
                                if fn is not None:
                                    try:
                                        if inspect.iscoroutinefunction(fn):
                                            result = await fn(**call_args)
                                        else:
                                            result = fn(**call_args)
                                    except Exception as tool_exc:
                                        logger.error(f"Error executing tool '{call_name}': {tool_exc}", exc_info=True)
                                        result = {"error": str(tool_exc)}
                                else:
                                    logger.warning(f"Tool '{call_name}' not found in registry.")
                                    result = {"error": f"Tool '{call_name}' not registered."}

                                exec_time_ms = (time.perf_counter() - t_tool_start) * 1000

                                # Send tool response back to Gemini Live
                                try:
                                    tool_resp_payload = result if isinstance(result, dict) else {"output": result}
                                    await session.send_tool_response(
                                        function_responses=[
                                            types.FunctionResponse(
                                                id=call_id,
                                                name=call_name,
                                                response=tool_resp_payload,
                                            )
                                        ]
                                    )
                                except Exception as send_tool_exc:
                                    logger.error(f"Error sending tool response to Gemini: {send_tool_exc}", exc_info=True)

                                # Notify client: tool status "done"
                                await self._safe_dispatch(
                                    event_out_callback,
                                    "tool_event",
                                    {
                                        "type": "tool_event",
                                        "tool_name": call_name,
                                        "status": "done",
                                        "result": result,
                                        "execution_time_ms": round(exec_time_ms, 2),
                                        "call_id": call_id,
                                        "timestamp_ms": int(time.time() * 1000),
                                    },
                                )
                            continue

                        # Handle Tool Call Cancellation (if user barged in during tool call)
                        tool_call_cancellation = getattr(response, "tool_call_cancellation", None)
                        if tool_call_cancellation:
                            cancelled_ids = getattr(tool_call_cancellation, "ids", [])
                            await self._safe_dispatch(
                                event_out_callback,
                                "tool_event",
                                {
                                    "type": "tool_event",
                                    "status": "cancelled",
                                    "ids": cancelled_ids,
                                    "timestamp_ms": int(time.time() * 1000),
                                },
                            )
                            continue

                        server_content = getattr(response, "server_content", None)
                        if not server_content:
                            continue

                        # 1. Handle Barge-in Interruption (Day 4 - Dev A)
                        if getattr(server_content, "interrupted", False):
                            is_interrupted = True
                            drained = self.reset_audio_queue(audio_in_queue)
                            t0 = time.perf_counter()
                            now_ms = int(time.time() * 1000)
                            await self._safe_dispatch(
                                event_out_callback,
                                "interrupted",
                                {
                                    "type": "interrupted",
                                    "timestamp_ms": now_ms,
                                    "reason": "user_barge_in",
                                },
                            )
                            dispatch_latency_ms = (time.perf_counter() - t0) * 1000
                            logger.info(
                                "⚡ Barge-in interruption handled in %.2fms (<50ms target). Drained %d queue frames.",
                                dispatch_latency_ms,
                                drained,
                            )
                            continue

                        # 2. Handle User Transcription (Final & Interim)
                        input_transcription = getattr(server_content, "input_transcription", None)
                        if input_transcription and getattr(input_transcription, "text", None):
                            is_interrupted = False
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

                        interim_transcription = getattr(server_content, "interim_input_transcription", None)
                        if interim_transcription and getattr(interim_transcription, "text", None):
                            is_interrupted = False
                            await self._safe_dispatch(
                                event_out_callback,
                                "transcript",
                                {
                                    "type": "transcript",
                                    "role": "user",
                                    "text": interim_transcription.text,
                                    "is_final": False,
                                },
                            )

                        # 3. Handle Agent Output Transcription
                        output_transcription = getattr(server_content, "output_transcription", None)
                        if output_transcription and getattr(output_transcription, "text", None):
                            if not is_interrupted:
                                await self._safe_dispatch(
                                    event_out_callback,
                                    "transcript",
                                    {
                                        "type": "transcript",
                                        "role": "agent",
                                        "text": output_transcription.text,
                                        "is_final": getattr(output_transcription, "finished", False) or False,
                                    },
                                )

                        # 4. Handle Model Turn (Audio & Agent Text fallback)
                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn and getattr(model_turn, "parts", None):
                            if is_interrupted:
                                logger.debug("Discarding residual model turn audio/text after interruption.")
                            else:
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

                        # 5. Handle Turn Complete
                        if getattr(server_content, "turn_complete", False):
                            is_interrupted = False
                            await self._safe_dispatch(
                                event_out_callback,
                                "turn_complete",
                                {
                                    "type": "turn_complete",
                                    "timestamp_ms": int(time.time() * 1000),
                                },
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
