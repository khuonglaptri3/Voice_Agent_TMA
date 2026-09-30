"""Main entry point: FastAPI Server and LiveKit Worker."""
from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.gateway.transports.websocket_transport import WebSocketTransport
from src.serving.api.v1.chat_routes import router as chat_router

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "web"

app = FastAPI(title="Enterprise Agentic AI & Realtime Voice Agent")
app.include_router(chat_router, prefix="/api/v1")
app.mount("/web", StaticFiles(directory=str(STATIC_DIR), html=True), name="web")


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/web")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    transport = WebSocketTransport(ws)
    try:
        await transport.start()
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    uvicorn.run("src.serving.main:app", host="0.0.0.0", port=8000, reload=True)
