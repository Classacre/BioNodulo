"""Hosted assistant: run the AI through BioNodulo's cloud, not a user's own key.

The assistant is sold as part of the product at half the model vendors' list
prices, which means *we* hold the upstream credential. It follows that the
desktop app must never see it, and must never learn who the upstream is: the
key and the vendor's hostnames live only in the cloud, behind an authenticated
proxy that speaks the ordinary Anthropic Messages wire format.

So the local backend calls the cloud proxy and authenticates as the signed-in
user, borrowing the bearer token the editor already sends with every local
request. The token never leaves the machine except to our own API, and it
identifies the team whose credits the call is billed to.

Users who prefer their own key still can: configuring `bionodulo.llm.apiKey`
selects a provider directly and bypasses all of this.
"""

from __future__ import annotations

import os

# Default cloud host. Overridable for staging and for self-hosted deployments,
# but never pointing at the upstream vendor -- that indirection is the point.
DEFAULT_CLOUD_API = "https://cloud.bionodulo.com"

#: Wire format the proxy exposes.
#:
#: The OpenAI format, deliberately. The upstream also serves an Anthropic
#: endpoint, but that one is shaped for the Claude Code CLI and prepends its own
#: agent system prompt: asked to extract a paper's methods as JSON it answers
#: "Let me look at the working directory to see what's already here", because it
#: believes it is a coding assistant in a checkout. Our own system prompts lose
#: that fight. The OpenAI endpoint honours them exactly.
#:
#: LiteLLM's openai provider appends `/chat/completions` to the base, so the
#: proxy path ends at `/v1`.
HOSTED_PROVIDER = "openai"

#: Requested model. The proxy validates it against what the vendor serves and
#: substitutes a default if it cannot, so this is a preference, not a promise.
HOSTED_MODEL = "gpt-5.5"

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
        "The AI assistant needs you to be signed in to BioNodulo, because it runs "
        "on our hosted models and bills your credits. Sign in from the account menu, "
        "or add your own provider API key in Settings to use the assistant offline."
    )
