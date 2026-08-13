"""Hosted assistant: run the AI through BioNodulo's cloud, not a user's own key.

The assistant is included free with the product: *we* hold the upstream
credential, and inference runs on a hosted state-of-the-art model behind a
shared daily fair-use quota. It follows that the desktop app must never see
the credential, and must never learn who the upstream provider is or which
model answered: the key and the provider's hostnames live only in the cloud,
behind an authenticated proxy that speaks the ordinary OpenAI Chat
Completions wire format.

So the local backend calls the cloud proxy and authenticates as the signed-in
user, borrowing the bearer token the editor already sends with every local
request. The token never leaves the machine except to our own API.

Users who prefer their own key still can: configuring `bionodulo.llm.apiKey`
selects a provider directly (GPT, Claude, or any LiteLLM-supported provider)
and bypasses all of this. Their own key always wins.
"""

from __future__ import annotations

import os
import re

# Default cloud host. Overridable for staging and for self-hosted deployments,
# but never pointing at the upstream provider -- that indirection is the point.
DEFAULT_CLOUD_API = "https://cloud.bionodulo.com"

#: Wire format the proxy exposes.
#:
#: The OpenAI format, deliberately: it honours our system prompts exactly and
#: is the only format the proxy serves. LiteLLM's openai provider appends
#: `/chat/completions` to the base, so the proxy path ends at `/v1`.
HOSTED_PROVIDER = "openai"

#: Requested model. The proxy substitutes the hosted model whatever we ask
#: for, so this is simply the neutral label the UI shows -- the hosted model's
#: real identity is never exposed to the app.
HOSTED_MODEL = "bionodulo-ai"

PROXY_PATH = "/api/ai/proxy/v1"


def cloud_api_base() -> str:
    """Root of the BioNodulo cloud API, without a trailing slash."""
    configured = os.environ.get("BIONODULO_CLOUD_API_URL", "").strip()
    return (configured or DEFAULT_CLOUD_API).rstrip("/")


def hosted_api_base() -> str:
    """Base URL LiteLLM should target for the hosted assistant."""
    return f"{cloud_api_base()}{PROXY_PATH}"


def bearer_from_headers(headers: object) -> str | None:
    """Extract the caller's cloud token from an inbound request's headers.

    Accepts anything with a mapping-style ``get``, so both Starlette's
    ``Headers`` and a plain dict work.
    """
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    raw = getter("authorization") or getter("Authorization") or ""
    if not isinstance(raw, str):
        return None
    prefix = "bearer "
    if raw[: len(prefix)].lower() != prefix:
        return None
    token = raw[len(prefix) :].strip()
    return token or None


def is_hosted_enabled() -> bool:
    """Whether the hosted assistant may be used at all.

    Off switch for self-hosted deployments that want to force a user's own key
    rather than silently routing prompts through our cloud.
    """
    return os.environ.get("BIONODULO_HOSTED_AI", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def hosted_unavailable_reason() -> str:
    """Why the assistant cannot run, phrased for the person reading it."""
    return (
        "The AI assistant is free to use — just sign in to BioNodulo from the "
        "account menu and it runs on our hosted model. Or add your own provider "
        "API key in Settings to use the assistant with a model of your choice."
    )


# Matches the ISO reset timestamp the proxy embeds in quota errors.
_RESET_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")


def friendly_hosted_error(exc: BaseException) -> str:
    """Translate a hosted-mode failure into a message safe to show a user.

    The hosted path must never leak the upstream provider or model, so raw
    LiteLLM/proxy error text is never passed through. The shared daily quota
    (which resets at 00:00 UTC) gets a specific, actionable message; every
    other failure gets a generic one.
    """
    text = str(exc)
    lowered = text.lower()
    if "global_quota_exhausted" in text or "429" in text or "rate limit" in lowered:
        match = _RESET_ISO_RE.search(text)
        when = match.group(0) if match else "00:00 UTC"
        return (
            "Our global free-AI quota for today has run out — it resets at "
            f"{when}. Please come back after the reset, or add your own "
            "provider API key in Settings → AI to continue right away with "
            "your own GPT or Claude model."
        )
    return (
        "The hosted AI assistant is temporarily unavailable. Please try again "
        "in a moment, or add your own provider API key in Settings → AI to "
        "use the assistant with your own model."
    )
