"""Seed utility node."""

from .adapter import SeedNode as _SeedContract


class SeedNode(_SeedContract):
    """Emit a fixed or newly generated bounded random seed."""

    NODE_ID = "seed"
