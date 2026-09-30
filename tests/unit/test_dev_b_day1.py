from fastapi.testclient import TestClient

from src.serving.main import app


def test_ws_live_echoes_binary_chunk():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            payload = b"\x00" * 1024
            websocket.send_bytes(payload)
            received = websocket.receive_bytes()
            assert received == payload
