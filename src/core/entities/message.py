"""Message entities for text and multimodal interactions."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, Dict, Any

@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
