"""Startup script: FastAPI Voice Agent Server and Web Studio Interface."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# SSL Certificate fallback
if "SSL_CERT_FILE" not in os.environ:
    for ca_path in ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]:
        if os.path.isfile(ca_path):
            os.environ["SSL_CERT_FILE"] = ca_path
            break

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Start Voice Agent FastAPI Server & Web Studio")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=True, help="Enable auto-reload (default: True)")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Number of worker processes (when reload is disabled)")

    args = parser.parse_args()

    print("=" * 64)
    print("    TMA ENTERPRISE VOICE AGENT - SPEECH-TO-SPEECH SERVER")
    print("=" * 64)
    print(f"  🌐 Web Studio (Giao diện):  http://localhost:{args.port}/web")
    print(f"  ⚡ WebSocket Live API:       ws://localhost:{args.port}/ws/live")
    print(f"  📚 Tài liệu Swagger Docs:   http://localhost:{args.port}/docs")
    print(f"  🩺 Kiểm tra sức khỏe:       http://localhost:{args.port}/health")
    print("-" * 64)
    print(f"Host: {args.host} | Port: {args.port} | Reload: {args.reload}")
    print("Nhấn Ctrl + C để dừng server.\n")

    uvicorn_kwargs = {
        "app": "src.serving.main:app",
        "host": args.host,
        "port": args.port,
    }

    if args.reload:
        uvicorn_kwargs["reload"] = True
    else:
        uvicorn_kwargs["workers"] = args.workers

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
