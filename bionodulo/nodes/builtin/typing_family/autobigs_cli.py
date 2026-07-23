"""Focused registered node for ``autobigs-cli``."""

from .adapter import AutoBIGSCliNode as _NodeContract


class AutoBIGSCliNode(_NodeContract):
    NODE_ID = "autobigs-cli"
