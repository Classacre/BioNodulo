"""integer — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
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


class IntegerPrimitiveNode(BaseNode):
    """Primitive integer value."""
    NODE_ID = 'integer_primitive'
    DISPLAY_NAME = 'Integer'
    CATEGORY = 'primitive'
    DESCRIPTION = 'An integer value with optional min/max/step constraints'
    SEARCH_ALIASES = ['int', 'integer', 'number', 'whole', 'count']
    RETURN_TYPES = ('INT',)
    RETURN_NAMES = ('value',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('INT', {'default': 0, 'min': -2147483648, 'max': 2147483647, 'step': 1, 'description': 'Integer value'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[int]:
        return (int(kwargs.get('value', 0)),)
