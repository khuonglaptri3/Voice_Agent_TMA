from fastapi.testclient import TestClient

from src.serving.main import app


def test_ws_live_echoes_binary_chunk():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            payload = b"\x00" * 1024
            websocket.send_bytes(payload)
            received = websocket.receive_bytes()
            assert received == payload


def test_ws_live_accepts_session_handshake_and_echoes_audio():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            websocket.send_json({"type": "session_start", "sample_rate": 16000, "client_timestamp": 1, "language": "vi-VN"})
            ack = websocket.receive_json()
            assert ack["type"] == "session_ack"
            assert ack["status"] == "ok"

            payload = b"\x01\x02\x03\x04" * 256
            websocket.send_bytes(payload)
            received = websocket.receive_bytes()
            assert received == payload

            websocket.send_json({"type": "session_stop", "reason": "user_hangup"})
            stop_ack = websocket.receive_json()
            assert stop_ack["type"] == "session_stop"
            assert stop_ack["status"] == "stopped"
