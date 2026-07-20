from datetime import datetime, UTC
from typing import Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class Event(BaseModel):
    """Standard Event Model for KiyoDesk Event Bus."""
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    correlation_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True
