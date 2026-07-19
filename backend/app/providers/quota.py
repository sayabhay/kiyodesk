"""Local sliding-window quota protection for weighted provider requests."""

import asyncio
from collections import deque
from time import monotonic

from app.providers.errors import ProviderRateLimitError


class SlidingWindowQuota:
    """Restrict requests to a configured weight budget per rolling minute."""

    def __init__(self, max_weight: int, window_seconds: int = 60) -> None:
        self._max_weight = max_weight
        self._window_seconds = window_seconds
        self._requests: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    async def reserve(self, weight: int) -> None:
        """Reserve request weight or reject the request before it leaves KiyoDesk."""

        now = monotonic()
        async with self._lock:
            while self._requests and self._requests[0][0] <= now - self._window_seconds:
                self._requests.popleft()

            used_weight = sum(request_weight for _, request_weight in self._requests)
            if used_weight + weight > self._max_weight:
                raise ProviderRateLimitError(
                    f"Local quota budget of {self._max_weight} weight/minute has been reached. "
                    "Failing over to next provider or wait before retrying."
                )
            self._requests.append((now, weight))
