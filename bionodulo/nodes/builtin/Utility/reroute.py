"""reroute — Utility node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class RerouteNode(CommandNode):
    """A pass-through node for routing connections cleanly."""
    NODE_ID = 'reroute'
    DISPLAY_NAME = 'Reroute'
    CATEGORY = 'Utility'
    DESCRIPTION = 'Pass a connection through a routing point'
    SEARCH_ALIASES = ['reroute', 'pass', 'through', 'junction', 'connection']
    RETURN_TYPES = ('ANY',)
    RETURN_NAMES = ('output',)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('*', {'description': 'Any input type'})}}

    async def run(self, **kwargs: Any) -> tuple:
        return (kwargs.get('input'),)
