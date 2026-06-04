from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.ai.llm_backend import LLMConfig, call_llm


@pytest.mark.asyncio
async def test_call_llm_retries_provider_errors_then_returns_response(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    async def fake_completion(**kwargs: Any) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary rate limit")
        return {
            "model": kwargs["model"],
            "choices": [{"message": {"content": "Recovered"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 9},
        }

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_completion))

    response = await call_llm(
        LLMConfig(provider="mock", model="mock/retry-test"),
        [{"role": "user", "content": "hello"}],
        max_retries=3,
        retry_delay=0,
    )

    assert attempts == 3
    assert response.content == "Recovered"
    assert response.error == ""
    assert response.usage == {"total_tokens": 9}


@pytest.mark.asyncio
async def test_call_llm_returns_error_response_after_provider_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    async def fake_completion(**kwargs: Any) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("provider unavailable")

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_completion))

    response = await call_llm(
        LLMConfig(provider="mock", model="mock/failure-test"),
        [{"role": "user", "content": "hello"}],
        max_retries=2,
        retry_delay=0,
    )

    assert attempts == 2
    assert response.content == ""
    assert response.model == "mock/failure-test"
    assert response.error == "LLM provider error after 2 attempts: provider unavailable"
