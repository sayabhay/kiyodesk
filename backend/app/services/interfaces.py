from abc import ABC, abstractmethod
from typing import Any
from app.schemas.events import Event

class NotificationProvider(ABC):
    """Base interface for all notification providers (Telegram, Discord, etc.)."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def send(self, event: Event) -> None:
        """Send a notification based on the event."""
        pass

class AIService(ABC):
    """Base interface for future AI Assistant integration."""
    
    @abstractmethod
    async def process_event(self, event: Event) -> None:
        """Process a system event to provide AI insights."""
        pass
