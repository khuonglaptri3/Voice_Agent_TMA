#!/usr/bin/env python3
"""
scripts/hello_adk_live.py
-------------------------
Nguyên mẫu đàm thoại âm thanh hai chiều trực tiếp (Native Speech-to-Speech)
sử dụng Gemini Live Multimodal API và sounddevice (Dành cho Dev A - Ngày 1).

Luồng xử lý:
    [Microphone 16kHz PCM] -> sounddevice RawInputStream -> asyncio.Queue
    -> Gemini Live API (bidi streaming)
    -> [Speaker 24kHz PCM] <- sounddevice RawOutputStream <- Gemini Audio Chunks
"""

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

# Đảm bảo sounddevice tìm thấy PortAudio nếu được cài qua conda
for conda_path in [
    os.path.expanduser("~/anaconda3/lib"),
    os.environ.get("CONDA_PREFIX", "") + "/lib",
]:
    if os.path.isdir(conda_path):
        os.environ["LD_LIBRARY_PATH"] = f"{conda_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"

# Tự động nạp CA cert của hệ thống nếu SSL_CERT_FILE chưa được đặt (tránh lỗi SSL trên mạng nội bộ TMA)
if "SSL_CERT_FILE" not in os.environ:
    for ca_path in ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]:
        if os.path.isfile(ca_path):
            os.environ["SSL_CERT_FILE"] = ca_path
            break

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

# Tải cấu hình từ .env
load_dotenv()

# Các tham số âm thanh chuẩn
INPUT_SAMPLE_RATE = 16000     # 16kHz cho mic gửi lên Gemini Live
OUTPUT_SAMPLE_RATE = 24000    # 24kHz cho âm thanh phát ra từ Gemini Live
CHANNELS = 1                  # Mono
CHUNK_SIZE = 512              # 512 mẫu (32ms mỗi chunk)
SAMPLE_WIDTH = 2              # 16-bit PCM = 2 bytes/sample (1024 bytes/chunk)


def print_banner():
    print("=" * 65)
    print("   VOICE AGENT TMA - NATIVE SPEECH-TO-SPEECH (POC DAY 1)   ")
    print("   Mô hình: Gemini Live Multimodal API")
    print("=" * 65)


def list_audio_devices():
    """In danh sách thiết bị thu/phát âm thanh có trên máy."""
    print("\nDanh sách thiết bị âm thanh khả dụng:")
    print("-" * 50)
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        in_ch = dev.get("max_input_channels", 0)
        out_ch = dev.get("max_output_channels", 0)
        default_mark = ""
        if idx == sd.default.device[0]:
            default_mark += " [Default IN]"
        if idx == sd.default.device[1]:
            default_mark += " [Default OUT]"
        print(f"[{idx:2d}] {dev.get('name')} (In: {in_ch}, Out: {out_ch}){default_mark}")
    print("-" * 50)


async def live_audio_loop(api_key: str, model_name: str, voice_name: str, in_dev=None, out_dev=None):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Cấu hình Live Connect
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voice_name
                )
            )
        ),
        system_instruction=types.Content(
            parts=[
                types.Part.from_text(
                    text=(
                        "Bạn là Trợ lý giọng nói thông minh bằng tiếng Việt của TMA Solutions. "
                        "Hãy trả lời thật ngắn gọn, súc tích (dưới 2 câu), thân thiện và tự nhiên. "
                        "Tuyệt đối không dùng ký tự Markdown, code block hay bảng biểu."
                    )
                )
            ]
        ),
    )

    audio_in_queue = asyncio.Queue()
    audio_out_queue = asyncio.Queue()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    # Callback thu âm từ Microphone
    def mic_callback(indata, frames, time_info, status):
        if status:
            pass
        # Đẩy dữ liệu nhị phân thô (bytes) vào hàng đợi
        loop.call_soon_threadsafe(audio_in_queue.put_nowait, bytes(indata))

    # Khởi tạo luồng âm thanh vào (Microphone 16kHz)
    input_stream = sd.RawInputStream(
        samplerate=INPUT_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=CHUNK_SIZE,
        device=in_dev,
        callback=mic_callback,
    )

    # Khởi tạo luồng âm thanh ra (Loa 24kHz)
    output_stream = sd.RawOutputStream(
        samplerate=OUTPUT_SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        device=out_dev,
    )

    print(f"\n[INFO] Đang kết nối tới Gemini Live ({model_name})...")
    print("[HƯỚNG DẪN] Đeo tai nghe để có trải nghiệm tốt nhất. Nhấn Ctrl+C để kết thúc.\n")

    input_stream.start()
    output_stream.start()

    async def send_audio_task(session):
        """Đọc audio chunks từ micro và gửi realtime lên Gemini Live."""
        try:
            while not stop_event.is_set():
                chunk = await audio_in_queue.get()
                await session.send_realtime_input(
                    media=types.Blob(
                        data=chunk,
                        mime_type=f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                    )
                )
        except asyncio.CancelledError:
            pass

    async def receive_audio_task(session):
        """Nhận phản hồi từ Gemini Live và phát ra loa."""
        try:
            async for response in session.receive():
                if stop_event.is_set():
                    break

                server_content = response.server_content
                if not server_content:
                    continue

                # Xử lý cờ ngắt lời (Barge-in)
                if server_content.interrupted:
                    print("\n[⚡ BARGE-IN] Phát hiện người dùng nói chen ngang -> Dừng phát loa!")
                    # Xóa sạch hàng đợi âm thanh đang chờ phát
                    while not audio_out_queue.empty():
                        try:
                            audio_out_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    continue

                # Phụ đề nhận dạng giọng nói của User
                if hasattr(server_content, "input_transcription") and server_content.input_transcription:
                    user_text = getattr(server_content.input_transcription, "text", "")
                    if user_text:
                        print(f"\n[User]: {user_text}", flush=True)

                # Bóc tách âm thanh và phụ đề từ Agent
                if server_content.model_turn:
                    for part in server_content.model_turn.parts:
                        if part.text:
                            print(f"[Agent]: {part.text}", flush=True)
                        if part.inline_data and part.inline_data.data:
                            # Đẩy chunk âm thanh nhận được vào hàng đợi phát
                            await audio_out_queue.put(part.inline_data.data)

                # Nếu lượt nói của Agent kết thúc
                if server_content.turn_complete:
                    pass

        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not stop_event.is_set():
                print(f"\n[LỖI NHẬN DỮ LIỆU]: {e}", file=sys.stderr)

    async def play_audio_task():
        """Lấy audio chunk từ queue và phát trực tiếp ra loa."""
        try:
            while not stop_event.is_set():
                audio_bytes = await audio_out_queue.get()
                # Ghi bytes ra output stream của sounddevice (chạy trên thread executor để không block event loop)
                await asyncio.to_thread(output_stream.write, audio_bytes)
        except asyncio.CancelledError:
            pass

    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            print("[KẾT NỐI THÀNH CÔNG] Đã vào phòng đàm thoại trực tiếp với Gemini Live!")
            print(">>> Hãy bắt đầu nói vào Micro...\n")

            t_send = asyncio.create_task(send_audio_task(session))
            t_recv = asyncio.create_task(receive_audio_task(session))
            t_play = asyncio.create_task(play_audio_task())

            await asyncio.gather(t_send, t_recv, t_play)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\n[LỖI KẾT NỐI GEMINI LIVE]: {e}", file=sys.stderr)
    finally:
        stop_event.set()
        print("\n[INFO] Đang đóng thiết bị âm thanh...")
        input_stream.stop()
        input_stream.close()
        output_stream.stop()
        output_stream.close()
        print("[INFO] Đã giải phóng tài nguyên hoàn tất.")


def main():
    parser = argparse.ArgumentParser(
        description="Demo Speech-to-Speech hai chiều trực tiếp với Gemini Live API qua CLI."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("GOOGLE_API_KEY"),
        help="Google Gemini API Key (mặc định lấy từ GOOGLE_API_KEY trong .env)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest"),
        help="Tên model Gemini Live (mặc định: gemini-2.5-flash-native-audio-latest)",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="Puck",
        choices=["Puck", "Charon", "Kore", "Fenrir", "Aoede"],
        help="Giọng đọc của Agent (mặc định: Puck)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Liệt kê danh sách thiết bị âm thanh và thoát.",
    )
    parser.add_argument(
        "--input-device",
        type=int,
        default=None,
        help="ID thiết bị Microphone (xem bằng --list-devices)",
    )
    parser.add_argument(
        "--output-device",
        type=int,
        default=None,
        help="ID thiết bị Loa/Tai nghe (xem bằng --list-devices)",
    )

    args = parser.parse_args()

    print_banner()

    if args.list_devices:
        list_audio_devices()
        return

    api_key = args.api_key
    if not api_key or api_key == "your-google-api-key":
        print("\n[CẢNH BÁO] Chưa tìm thấy Google API Key hợp lệ!")
        print("Vui lòng cấu hình GOOGLE_API_KEY trong file .env hoặc truyền qua tham số:")
        print("    python scripts/hello_adk_live.py --api-key YOUR_ACTUAL_KEY\n")
        print("Bạn có thể lấy API Key miễn phí tại: https://aistudio.google.com/apikey")
        sys.exit(1)

    # Đăng ký xử lý Ctrl+C
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    main_task = loop.create_task(
        live_audio_loop(
            api_key=api_key,
            model_name=args.model,
            voice_name=args.voice,
            in_dev=args.input_device,
            out_dev=args.output_device,
        )
    )

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, main_task.cancel)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(main_task)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nĐã nhận lệnh kết thúc từ người dùng.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
