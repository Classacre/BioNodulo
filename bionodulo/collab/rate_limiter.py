"""Token-bucket rate limiter per WebSocket connection.

Different message types (CRDT updates, awareness, cursor) have their own
buckets with independent rates.  The limiter is designed to be called from
the single asyncio event-loop thread — no explicit locking is required.

Usage::

    limiter = RateLimiter()
    if limiter.check(websocket, "update"):
        await process_update(data)
    else:
        logger.warning("Rate limit exceeded for update")
    # On disconnect:
    limiter.reset(websocket)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Default rate configuration (messages per second, burst capacity)
DEFAULT_RATES: dict[str, tuple[float, float]] = {
    "update": (30.0, 60.0),      # 30 msg/s, burst 60
    "awareness": (20.0, 40.0),   # 20 msg/s, burst 40
    "cursor": (50.0, 100.0),     # 50 msg/s, burst 100
    "sync": (10.0, 20.0),        # 10 msg/s, burst 20
}


class TokenBucket:
    """A single token-bucket rate limiter.

    Tokens are added continuously based on elapsed time.  A ``consume``
    call succeeds only if enough tokens are available.
    """

    def __init__(self, rate: float, burst: float) -> None:
        """Initialise the bucket.

        Args:
            rate: Tokens added per second.
            burst: Maximum token capacity.
        """
        self._rate = rate
        self._burst = burst
        self._tokens: float = burst
        self._last_refill: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume *tokens* from the bucket.

        Args:
            tokens: Number of tokens to consume (default 1).

        Returns:
            ``True`` if the consumption succeeded, ``False`` if insufficient
            tokens are available.
        """
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def refill(self) -> None:
        """Explicitly refill the bucket based on elapsed time.

n        This is called automatically by :meth:`consume`, but can be invoked
        manually for bookkeeping.
        """
        self._refill()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now


class RateLimiter:
    """Per-WebSocket rate limiter with separate buckets per message type.

    Each websocket gets a dict of :class:`TokenBucket` instances keyed by
    message type.  Unknown types fall back to the ``update`` bucket.
    """

    def __init__(
        self,
        rates: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        """Initialise the limiter.

        Args:
            rates: Override the default rate configuration.  Keys are
                message types; values are ``(rate, burst)`` tuples.
        """
        self._rates = rates or DEFAULT_RATES
        # websocket -> {msg_type: TokenBucket}
        self._buckets: dict[WebSocket, dict[str, TokenBucket]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, websocket: WebSocket, msg_type: str) -> bool:
        """Check whether a message of *msg_type* is allowed.

        Args:
            websocket: The FastAPI WebSocket connection.
            msg_type: One of ``update``, ``awareness``, ``cursor``, ``sync``.

        Returns:
            ``True`` if the message is within rate limits.
        """
        buckets = self._ensure_buckets(websocket)
        bucket = buckets.get(msg_type)
        if bucket is None:
            # Unknown types fall back to "update" bucket
            bucket = buckets.get("update")
            if bucket is None:
                return True
        allowed = bucket.consume(1.0)
        if not allowed:
            logger.debug(
                "Rate limit exceeded for %s on websocket %s",
                msg_type,
                id(websocket),
            )
        return allowed

    def reset(self, websocket: WebSocket) -> None:
        """Remove all rate-limit state for *websocket* (call on disconnect).

        Args:
            websocket: The FastAPI WebSocket connection.
        """
        removed = self._buckets.pop(websocket, None)
        if removed is not None:
            logger.debug("Rate limiter reset for websocket %s", id(websocket))

    def get_status(self, websocket: WebSocket) -> dict[str, dict[str, float]]:
        """Return current token counts for debugging.

        Args:
            websocket: The FastAPI WebSocket connection.

        Returns:
            A dict mapping message type -> ``{"tokens": float, "rate": float}``.
        """
        buckets = self._buckets.get(websocket, {})
        result: dict[str, dict[str, float]] = {}
        for msg_type, bucket in buckets.items():
            bucket.refill()
            result[msg_type] = {
                "tokens": bucket._tokens,
                "rate": bucket._rate,
            }
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_buckets(self, websocket: WebSocket) -> dict[str, TokenBucket]:
        """Return (creating if necessary) the bucket dict for *websocket*."""
        buckets = self._buckets.get(websocket)
        if buckets is None:
            buckets = {
                msg_type: TokenBucket(rate, burst)
                for msg_type, (rate, burst) in self._rates.items()
            }
            self._buckets[websocket] = buckets
        return buckets
