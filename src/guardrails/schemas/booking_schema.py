"""Visitor booking validation schema."""
from pydantic import BaseModel, Field

class VisitorBookingSchema(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., pattern=r'^\+?[0-9]{9,15}$')
