import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

from app.schemas.events import Event
from loguru import logger

# Subscriber type: an async callable that takes an Event
Subscriber: TypeAlias = Callable[[Event], Awaitable[None]]

class EventBus:
    """Internal Event Bus for KiyoDesk.
    
    Decouples system components by allowing them to communicate via events.
    Supports multiple subscribers per event type or a catch-all subscription.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, set[Subscriber]] = defaultdict(set)
        self._global_subscribers: set[Subscriber] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, subscriber: Subscriber, event_type: str | None = None) -> None:
        """Subscribe to a specific event type or all events if event_type is None."""
        async with self._lock:
            if event_type:
                self._subscribers[event_type].add(subscriber)
                logger.debug("Subscribed to event type: {}", event_type)
            else:
                self._global_subscribers.add(subscriber)
                logger.debug("Subscribed to all events (global)")

    async def unsubscribe(self, subscriber: Subscriber, event_type: str | None = None) -> None:
        """Unsubscribe from a specific event type or all events."""
        async with self._lock:
            if event_type:
                if event_type in self._subscribers:
                    self._subscribers[event_type].discard(subscriber)
                    if not self._subscribers[event_type]:
                        del self._subscribers[event_type]
            else:
                self._global_subscribers.discard(subscriber)

    async def publish(self, event: Event) -> None:
        """Publish an event to all relevant subscribers."""
        # We don't hold the lock during execution of subscribers to avoid deadlocks
        # and allow concurrent processing of the same event by different subscribers.
        async with self._lock:
            targets = list(self._global_subscribers)
            if event.event_type in self._subscribers:
                targets.extend(self._subscribers[event.event_type])

        if not targets:
            logger.trace("No subscribers for event: {}", event.event_type)
            return

        logger.debug("Publishing event {} from {}", event.event_type, event.source)
        
        # Run all subscribers concurrently
        tasks = [self._run_subscriber(subscriber, event) for subscriber in targets]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_subscriber(self, subscriber: Subscriber, event: Event) -> None:
        try:
            await subscriber(event)
        except Exception as e:
            logger.error("Error in subscriber for event {}: {}", event.event_type, e)

# Global singleton instance
event_bus = EventBus()
