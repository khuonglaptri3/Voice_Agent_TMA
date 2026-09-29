"""FastAPI routes for observability metrics and traces."""
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
