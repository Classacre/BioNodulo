from __future__ import annotations

from typing import Any

import httpx
import pytest

from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter


def _response(status_code: int, *, text: str = "ok", headers: dict[str, str] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.example.test/resource")
    return httpx.Response(status_code, text=text, headers=headers or {}, request=request)


@pytest.mark.asyncio
async def test_api_client_retries_5xx_then_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_response(503, text="busy"), _response(200, text="ready")]
    sleeps: list[float] = []

    async def fake_send(**kwargs: Any) -> httpx.Response:
        return responses.pop(0)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("bionodulo.nodes.builtin.api.http.asyncio.sleep", fake_sleep)
    client = APIHttpClient(send=fake_send)

    response = await client.request("GET", "https://api.example.test/resource", retries=2, retry_delay=0.25)

    assert response.status_code == 200
    assert response.text == "ready"
    assert sleeps == [0.25]


@pytest.mark.asyncio
async def test_api_client_retries_429_after_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        _response(429, text="slow down", headers={"Retry-After": "2"}),
        _response(200, text="ok"),
    ]
    sleeps: list[float] = []

    async def fake_send(**kwargs: Any) -> httpx.Response:
        return responses.pop(0)

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("bionodulo.nodes.builtin.api.http.asyncio.sleep", fake_sleep)
    client = APIHttpClient(send=fake_send)

    response = await client.request("GET", "https://api.example.test/resource", retries=2, retry_delay=0.25)

    assert response.status_code == 200
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_api_cache_returns_cached_get_without_transport_call() -> None:
    calls = 0

    async def fake_send(**kwargs: Any) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(200, text=f"payload-{calls}", headers={"content-type": "text/plain"})

    client = APIHttpClient(send=fake_send, cache=APICache(ttl_seconds=60))

    first = await client.request("GET", "https://api.example.test/resource", cache_ttl=60)
    second = await client.request("GET", "https://api.example.test/resource", cache_ttl=60)

    assert calls == 1
    assert first.text == "payload-1"
    assert second.text == "payload-1"
    assert second.headers["content-type"] == "text/plain"


@pytest.mark.asyncio
async def test_api_cache_expires_entries_after_ttl() -> None:
    now = 100.0
    calls = 0

    async def fake_send(**kwargs: Any) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(200, text=f"payload-{calls}")

    cache = APICache(ttl_seconds=1, clock=lambda: now)
    client = APIHttpClient(send=fake_send, cache=cache)

    first = await client.request("GET", "https://api.example.test/resource", cache_ttl=1)
    now = 102.0
    second = await client.request("GET", "https://api.example.test/resource", cache_ttl=1)

    assert calls == 2
    assert first.text == "payload-1"
    assert second.text == "payload-2"


@pytest.mark.asyncio
async def test_api_cache_keys_include_request_headers() -> None:
    calls = 0

    async def fake_send(**kwargs: Any) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _response(200, text=f"payload-{calls}")

    client = APIHttpClient(send=fake_send, cache=APICache(ttl_seconds=60))

    first = await client.request(
        "GET",
        "https://api.example.test/resource",
        headers={"Authorization": "Bearer token-a"},
        cache_ttl=60,
    )
    second = await client.request(
        "GET",
        "https://api.example.test/resource",
        headers={"Authorization": "Bearer token-b"},
        cache_ttl=60,
    )

    assert calls == 2
    assert first.text == "payload-1"
    assert second.text == "payload-2"


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter_waits_when_capacity_is_exhausted() -> None:
    now = 10.0
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        nonlocal now
        sleeps.append(delay)
        now += delay

    limiter = TokenBucketRateLimiter(rate_per_second=2, burst=1, clock=lambda: now, sleep=fake_sleep)

    await limiter.acquire()
    await limiter.acquire()

    assert sleeps == [0.5]
