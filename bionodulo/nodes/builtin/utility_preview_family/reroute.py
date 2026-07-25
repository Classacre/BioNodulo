"""Product-native pass-through connection node."""

from __future__ import annotations

from typing import Any

from .adapter import PythonUtilityNode


class RerouteNode(PythonUtilityNode):
    """Return the connected value unchanged."""

    NODE_ID = "reroute"
    DISPLAY_NAME = "Reroute"
    DESCRIPTION = "Pass a connection through a routing point"
    SEARCH_ALIASES = ["reroute", "pass", "through", "junction", "connection"]
    RETURN_TYPES = ("ANY",)
    RETURN_NAMES = ("output",)
    VERSION = "1.0.0"
    UPSTREAM_SOURCE = "BioNodulo native workflow representation"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {"required": {"input": ("*", {"description": "Any input type"})}}

    async def run(self, **kwargs: Any) -> tuple[Any]:
        kwargs.pop("context", None)
        return (kwargs.get("input"),)
