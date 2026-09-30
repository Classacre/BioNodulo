"""Hosted failures must not invent a quota window or leak provider details."""
from __future__ import annotations

from bionodulo.ai.hosted import friendly_hosted_error


def test_generic_429_is_temporary_not_daily_exhaustion() -> None:
    message = friendly_hosted_error(RuntimeError("429 upstream provider rate limit: secret-model"))
    assert "temporarily rate-limited" in message
    assert "today" not in message.lower()
    assert "00:00 UTC" not in message
    assert "secret-model" not in message


def test_legacy_quota_type_without_reset_does_not_invent_one() -> None:
    message = friendly_hosted_error(RuntimeError('{"type":"global_quota_exhausted"}'))
    assert "temporarily rate-limited" in message
    assert "00:00 UTC" not in message
    assert "today" not in message.lower()


def test_explicit_valid_future_reset_may_be_shown() -> None:
    message = friendly_hosted_error(RuntimeError(
        '{"type":"global_quota_exhausted","reset_at":"2099-01-01T12:00:00Z"}'
    ))
    assert "2099-01-01T12:00:00Z" in message
    assert "today" not in message.lower()


def test_malformed_reset_is_ignored() -> None:
    message = friendly_hosted_error(RuntimeError(
        '{"type":"global_quota_exhausted","reset_at":"2099-99-99T12:00:00Z"}'
    ))
    assert "2099-99-99" not in message
