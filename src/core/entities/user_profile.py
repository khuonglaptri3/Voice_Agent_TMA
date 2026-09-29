"""User identity and preference profile entity."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class UserProfile:
    user_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: str = "vi"
    attributes: Dict[str, Any] = field(default_factory=dict)
