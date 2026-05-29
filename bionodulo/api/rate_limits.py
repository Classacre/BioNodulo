"""Shared SlowAPI rate-limit integration."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.environ.get("BIONODULO_RATE_LIMIT_REDIS_URL") or os.environ.get("BIONODULO_REDIS_URL") or None,
)

__all__ = ["RateLimitExceeded", "SlowAPIMiddleware", "limiter"]
