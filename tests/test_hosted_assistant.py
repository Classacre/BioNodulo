"""The assistant runs on BioNodulo's hosted model, without leaking the provider.

Hosted AI is free for users, so the upstream key and the provider's identity
are operational details that must never reach a desktop build. The local
backend therefore talks to our own cloud proxy, authenticating with the token
the signed-in editor already sends.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bionodulo.ai import hosted


def test_the_hosted_base_points_at_our_cloud_not_the_vendor() -> None:
    base = hosted.hosted_api_base()

    assert base.startswith("https://cloud.bionodulo.com")
    assert base.endswith("/api/ai/proxy/v1")


def test_the_openai_wire_format_is_the_default() -> None:
    """The OpenAI chat-completions format is the only one the proxy serves; it
    honours our system prompts exactly."""
    assert hosted.HOSTED_PROVIDER == "openai"


def test_the_hosted_model_label_is_neutral() -> None:
    """The proxy substitutes the real hosted model, so the app only ever asks
    for -- and displays -- a neutral label."""
    assert hosted.HOSTED_MODEL == "bionodulo-ai"


def test_the_cloud_host_is_overridable_for_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIONODULO_CLOUD_API_URL", "https://staging.example.com/")

    assert hosted.hosted_api_base() == "https://staging.example.com/api/ai/proxy/v1"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer abc.def", "abc.def"),
        ("bearer abc.def", "abc.def"),
        ("Basic abc", None),
        ("", None),
        ("Bearer   ", None),
    ],
)
def test_the_callers_token_is_read_from_the_authorization_header(
    header: str, expected: str | None
) -> None:
    assert hosted.bearer_from_headers({"authorization": header}) == expected


def test_headers_without_a_get_method_are_tolerated() -> None:
    # Defensive: a caller passing something odd must not crash the chat route.
    assert hosted.bearer_from_headers(object()) is None


def test_hosted_mode_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Self-hosted deployments may refuse to route prompts through our cloud."""
    assert hosted.is_hosted_enabled()
    monkeypatch.setenv("BIONODULO_HOSTED_AI", "0")
    assert not hosted.is_hosted_enabled()


def test_the_unavailable_message_offers_both_ways_forward() -> None:
    reason = hosted.hosted_unavailable_reason()

    assert "sign in" in reason.lower()
    assert "API key" in reason


def test_no_shipped_python_names_the_vendor() -> None:
    """A legacy vendor's domain belongs only in the cloud's environment. A
    grep is the only check that actually holds: a hardcoded fallback would
    otherwise ship silently in the desktop bundle."""
    root = Path(hosted.__file__).resolve().parents[1]
    hits = subprocess.run(
        ["grep", "-rIl", "freemodel", str(root)],
        capture_output=True,
        text=True,
    ).stdout.split()

    assert hits == [], f"vendor domain referenced in shipped code: {hits}"


def test_no_shipped_python_embeds_an_upstream_key() -> None:
    root = Path(hosted.__file__).resolve().parents[1]
    hits = subprocess.run(
        ["grep", "-rIlE", r"sk-or-[a-zA-Z0-9-]{32}", str(root)],
        capture_output=True,
        text=True,
    ).stdout.split()

    assert hits == [], f"upstream API key referenced in shipped code: {hits}"


def test_quota_errors_become_an_actionable_message_with_the_reset_time() -> None:
    class Boom(Exception):
        pass

    exc = Boom(
        '429 {"error": {"type": "global_quota_exhausted", '
        '"reset_at": "2026-08-13T00:00:00.000Z"}}'
    )

    message = hosted.friendly_hosted_error(exc)

    assert "quota" in message.lower()
    assert "2026-08-13T00:00:00.000Z" in message
    assert "API key" in message  # offers the bring-your-own-key way forward


def test_quota_errors_fall_back_to_the_daily_reset_time() -> None:
    message = hosted.friendly_hosted_error(Exception("429 too many requests"))

    assert "00:00 UTC" in message


def test_other_hosted_failures_never_leak_upstream_text() -> None:
    raw = "502 bad gateway from https://openrouter.ai/api/v1 for model nvidia/x"

    message = hosted.friendly_hosted_error(Exception(raw))

    assert raw not in message
    assert "openrouter" not in message.lower()
    assert "temporarily unavailable" in message.lower()
