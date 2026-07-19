"""Small asynchronous TTL cache used by live market requests."""

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


class TtlCache:
    """Process-local cache that prevents duplicate provider calls inside a TTL window."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[float, object]] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(
        self,
        key: str,
        ttl_seconds: int,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        """Return a valid cached value or create and retain one atomically."""

        async with self._lock:
            cached = self._items.get(key)
            if cached is not None and cached[0] > monotonic():
                return cached[1]  # type: ignore[return-value]

            value = await factory()
            self._items[key] = (monotonic() + ttl_seconds, value)
            return value
