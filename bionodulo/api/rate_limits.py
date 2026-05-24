"""Shared SlowAPI rate-limit integration."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])

__all__ = ["RateLimitExceeded", "SlowAPIMiddleware", "limiter"]
