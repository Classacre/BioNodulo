"""The assistant runs on BioNodulo's hosted models, without leaking the vendor.

We resell model capacity at half list price, so the upstream key and the
vendor's hostnames are commercial details that must never reach a desktop build.
The local backend therefore talks to our own cloud proxy, authenticating with
the token the signed-in editor already sends.
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
    """The vendor's Anthropic endpoint is shaped for the Claude Code CLI and
    prepends its own agent system prompt -- asked to extract a paper as JSON it
    answers "Let me look at the working directory". Our prompts lose that
    fight, so the OpenAI-format endpoint is the one we use."""
    assert hosted.HOSTED_PROVIDER == "openai"


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
    """The vendor's domain is a commercial detail and belongs only in the
    cloud's environment. A grep is the only check that actually holds: a
    hardcoded fallback would otherwise ship silently in the desktop bundle."""
    root = Path(hosted.__file__).resolve().parents[1]
    hits = subprocess.run(
        ["grep", "-rIl", "freemodel", str(root)],
        capture_output=True,
        text=True,
    ).stdout.split()

    assert hits == [], f"vendor domain referenced in shipped code: {hits}"


def test_no_shipped_python_embeds_a_vendor_key() -> None:
    root = Path(hosted.__file__).resolve().parents[1]
    hits = subprocess.run(
        ["grep", "-rIlE", r"fe_[a-z]{2}_[a-f0-9]{32}", str(root)],
        capture_output=True,
        text=True,
    ).stdout.split()

    assert hits == [], f"vendor API key referenced in shipped code: {hits}"
