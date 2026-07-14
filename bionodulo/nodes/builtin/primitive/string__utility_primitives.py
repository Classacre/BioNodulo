"""string — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
from __future__ import annotations
import json
import math
import operator
import random
import uuid
from typing import Any, Callable
from bionodulo.nodes.base import BaseNode
def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {'', '0', 'false', 'f', 'no', 'n', 'off', 'none', 'null'}:
        return False
    return True


class StringPrimitiveNode(BaseNode):
    """Primitive string value."""
    NODE_ID = 'string_primitive'
    DISPLAY_NAME = 'String'
    CATEGORY = 'primitive'
    DESCRIPTION = 'A string value that can be passed to other nodes'
    SEARCH_ALIASES = ['text', 'string', 'value', 'literal', 'constant']
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('value',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('STRING', {'default': '', 'multiline': True, 'description': 'String value'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str]:
        return (str(kwargs.get('value', '')),)
