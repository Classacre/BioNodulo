"""Shared HTTP client primitives for API-backed workflow nodes."""
from __future__ import annotations

import asyncio
import json
import os
import time
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx


ResponseSender = Callable[..., Awaitable[httpx.Response]]
Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


@dataclass
class _CacheEntry:
    expires_at: float
    status_code: int
    headers: dict[str, str]
    text: str
    url: str


class APICache:
    """Small response cache for idempotent API requests.

    Defaults to in-memory storage. Supplying ``cache_dir`` enables a disk-backed
    cache that can be shared across cache instances and process restarts.
    """

    def __init__(
        self,
        ttl_seconds: float = 300.0,
        *,
        cache_dir: str | Path | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock or time.monotonic
        self._entries: dict[str, _CacheEntry] = {}
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls, *, default_ttl_seconds: float = 300.0, clock: Clock | None = None) -> APICache:
        raw_ttl = os.environ.get("BIONODULO_API_CACHE_TTL", "")
        try:
            ttl = float(raw_ttl) if raw_ttl else float(default_ttl_seconds)
        except ValueError:
            ttl = float(default_ttl_seconds)
        cache_dir = os.environ.get("BIONODULO_API_CACHE_DIR", "") or None
        return cls(ttl_seconds=ttl, cache_dir=cache_dir, clock=clock)

    def get(self, key: str) -> httpx.Response | None:
        if self.cache_dir is not None:
            return self._get_disk(key)
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._entries.pop(key, None)
            return None
        request = httpx.Request("GET", entry.url)
        return httpx.Response(
            entry.status_code,
            text=entry.text,
            headers=entry.headers,
            request=request,
        )

    def set(self, key: str, response: httpx.Response, *, ttl_seconds: float | None = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else float(ttl_seconds)
        if ttl <= 0:
            return
        entry = _CacheEntry(
            expires_at=self._clock() + ttl,
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response.text,
            url=str(response.url),
        )
        if self.cache_dir is not None:
            self._set_disk(key, entry)
            return
        self._entries[key] = entry

    def _cache_path(self, key: str) -> Path:
        assert self.cache_dir is not None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _get_disk(self, key: str) -> httpx.Response | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = _CacheEntry(
                expires_at=float(payload["expires_at"]),
                status_code=int(payload["status_code"]),
                headers={str(k): str(v) for k, v in dict(payload.get("headers", {})).items()},
                text=str(payload.get("text", "")),
                url=str(payload["url"]),
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None
        if entry.expires_at <= self._clock():
            path.unlink(missing_ok=True)
            return None
        request = httpx.Request("GET", entry.url)
        return httpx.Response(
            entry.status_code,
            text=entry.text,
            headers=entry.headers,
            request=request,
        )

    def _set_disk(self, key: str, entry: _CacheEntry) -> None:
        path = self._cache_path(key)
        payload = {
            "expires_at": entry.expires_at,
            "status_code": entry.status_code,
            "headers": entry.headers,
            "text": entry.text,
            "url": entry.url,
        }
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


class TokenBucketRateLimiter:
    """Async token bucket limiter for polite shared API access."""

    def __init__(
        self,
        *,
        rate_per_second: float,
        burst: int = 1,
        clock: Clock | None = None,
        sleep: Sleeper | None = None,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be greater than zero")
        if burst <= 0:
            raise ValueError("burst must be greater than zero")
        self.rate_per_second = float(rate_per_second)
        self.burst = int(burst)
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._tokens = float(burst)
        self._updated_at = self._clock()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._updated_at)
            self._tokens = min(float(self.burst), self._tokens + elapsed * self.rate_per_second)
            self._updated_at = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            wait_seconds = (1.0 - self._tokens) / self.rate_per_second
            await self._sleep(wait_seconds)
            self._updated_at = self._clock()
            self._tokens = 0.0


class APIHttpClient:
    """HTTP client with reusable retry, 429, cache, and rate-limit behavior."""

    def __init__(
        self,
        *,
        send: ResponseSender | None = None,
        cache: APICache | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self._send = send
        self.cache = cache
        self.rate_limiter = rate_limiter

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        timeout: float = 30.0,
        follow_redirects: bool = True,
        retries: int = 3,
        retry_delay: float = 1.0,
        cache_ttl: float | None = None,
    ) -> httpx.Response:
        method = method.upper()
        clean_params = params or {}
        cache_key = self._cache_key(method, url, clean_params, headers or {}) if cache_ttl and method in {"GET", "HEAD"} else ""
        if cache_key and self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        attempts = max(1, int(retries or 1))
        last_error: Exception | None = None
        for attempt in range(attempts):
            if self.rate_limiter is not None:
                await self.rate_limiter.acquire()
            try:
                response = await self._dispatch(
                    method,
                    url,
                    params=clean_params,
                    headers=headers or {},
                    json=json,
                    data=data,
                    timeout=timeout,
                    follow_redirects=follow_redirects,
                )
                if self._should_retry_response(response) and attempt < attempts - 1:
                    await asyncio.sleep(self._retry_delay(response, retry_delay, attempt))
                    continue
                response.raise_for_status()
                if cache_key and self.cache is not None:
                    self.cache.set(cache_key, response, ttl_seconds=cache_ttl)
                return response
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                if not self._should_retry_status(status) or attempt >= attempts - 1:
                    raise
                await asyncio.sleep(self._retry_delay(exc.response, retry_delay, attempt))
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    raise
                await asyncio.sleep(float(retry_delay) * (2 ** attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError("API request failed without a response")

    async def _dispatch(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._send is not None:
            return await self._send(method=method, url=url, **kwargs)
        # SSRF guard on EVERY hop: httpx fires the request hook for each redirect
        # it follows, so a 30x bounce to an internal/metadata host is rejected.
        from bionodulo.core.netguard import safe_request_event_hook

        async with httpx.AsyncClient(
            timeout=kwargs.pop("timeout"),
            follow_redirects=kwargs.pop("follow_redirects"),
            event_hooks={"request": [safe_request_event_hook()]},
        ) as client:
            return await client.request(method, url, **kwargs)

    @staticmethod
    def _should_retry_status(status_code: int) -> bool:
        return status_code == 429 or status_code >= 500

    def _should_retry_response(self, response: httpx.Response) -> bool:
        return self._should_retry_status(response.status_code)

    @staticmethod
    def _retry_delay(response: httpx.Response, base_delay: float, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return float(base_delay) * (2 ** attempt)

    @staticmethod
    def _cache_key(method: str, url: str, params: dict[str, Any], headers: dict[str, str]) -> str:
        request = httpx.Request(method, url, params=params, headers=headers)
        header_items = sorted((str(key).lower(), str(value)) for key, value in headers.items())
        header_digest = hashlib.sha256(json.dumps(header_items, separators=(",", ":")).encode("utf-8")).hexdigest()
        return f"{method} {request.url} {header_digest}"
