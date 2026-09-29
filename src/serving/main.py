"""Main entry point: FastAPI Server and LiveKit Worker."""
import uvicorn
from fastapi import FastAPI
from src.serving.api.v1.chat_routes import router as chat_router

app = FastAPI(title="Enterprise Agentic AI & Realtime Voice Agent")
app.include_router(chat_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("src.serving.main:app", host="0.0.0.0", port=8000, reload=True)
