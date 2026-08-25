from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from app.core.exceptions import (
    RateLimitExceededError,
)


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._requests: dict[
            tuple[str, str], deque[float]
        ] = defaultdict(deque)
        self._lock = Lock()

    def check(
        self,
        scope: str,
        actor_id: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        now = monotonic()
        cutoff = now - window_seconds
        key = (scope, actor_id)

        with self._lock:
            timestamps = self._requests[key]

            while (
                timestamps
                and timestamps[0] <= cutoff
            ):
                timestamps.popleft()

            if len(timestamps) >= limit:
                retry_after = max(
                    1,
                    int(
                        timestamps[0]
                        + window_seconds
                        - now
                    )
                    + 1,
                )
                raise RateLimitExceededError(
                    retry_after_seconds=(
                        retry_after
                    )
                )

            timestamps.append(now)

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


request_limiter = InMemoryRateLimiter()
