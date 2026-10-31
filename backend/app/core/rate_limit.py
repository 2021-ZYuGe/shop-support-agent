from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: int


class InMemoryRateLimiter:
    """Single-process sliding-window limiter; use Redis for multi-worker deployments."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10000,
    ) -> None:
        self._clock = clock
        self._max_keys = max_keys
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        if limit <= 0 or window_seconds <= 0:
            return RateLimitDecision(True, max(limit, 0), 0)

        now = self._clock()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and now - bucket[0] >= window_seconds:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(
                    1, math.ceil(window_seconds - (now - bucket[0]))
                )
                return RateLimitDecision(False, 0, retry_after)

            bucket.append(now)
            self._prune_if_needed(now)
            return RateLimitDecision(True, max(0, limit - len(bucket)), 0)

    def _prune_if_needed(self, now: float) -> None:
        if len(self._buckets) <= self._max_keys:
            return
        stale = [
            key
            for key, bucket in self._buckets.items()
            if not bucket or now - bucket[-1] >= 3600
        ]
        for key in stale:
            self._buckets.pop(key, None)
        while len(self._buckets) > self._max_keys:
            self._buckets.pop(next(iter(self._buckets)))

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = InMemoryRateLimiter()


def _client_identity(request: Request, settings: SettingsDep) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()[:64] or "unknown"
    return request.client.host if request.client else "unknown"


def _enforce(
    request: Request,
    settings: SettingsDep,
    scope: str,
    rules: list[tuple[int, int]],
) -> None:
    if not settings.rate_limit_enabled:
        return
    identity = _client_identity(request, settings)
    for window_seconds, limit in rules:
        decision = rate_limiter.hit(
            f"{scope}:{window_seconds}:{identity}",
            limit,
            window_seconds,
        )
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试。",
                headers={"Retry-After": str(decision.retry_after)},
            )


def enforce_chat_rate_limit(
    request: Request,
    settings: SettingsDep,
) -> None:
    _enforce(
        request,
        settings,
        "chat",
        [
            (60, settings.rate_limit_chat_per_minute),
            (3600, settings.rate_limit_chat_per_hour),
        ],
    )


def enforce_read_rate_limit(
    request: Request,
    settings: SettingsDep,
) -> None:
    _enforce(
        request,
        settings,
        "read",
        [(60, settings.rate_limit_read_per_minute)],
    )


def enforce_feedback_rate_limit(
    request: Request,
    settings: SettingsDep,
) -> None:
    _enforce(
        request,
        settings,
        "feedback",
        [(60, settings.rate_limit_feedback_per_minute)],
    )


def enforce_login_rate_limit(
    request: Request,
    settings: SettingsDep,
) -> None:
    _enforce(
        request,
        settings,
        "login",
        [(60, settings.rate_limit_login_per_minute)],
    )
