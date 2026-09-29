"""Entity extraction schema."""
from pydantic import BaseModel

class ExtractedEntitySchema(BaseModel):
    key: str
    value: str
