"""boolean — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
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


class BooleanPrimitiveNode(BaseNode):
    """Primitive boolean value."""
    NODE_ID = 'boolean_primitive'
    DISPLAY_NAME = 'Boolean'
    CATEGORY = 'primitive'
    DESCRIPTION = 'A true/false toggle value'
    SEARCH_ALIASES = ['bool', 'boolean', 'toggle', 'flag', 'switch', 'true', 'false']
    RETURN_TYPES = ('BOOLEAN',)
    RETURN_NAMES = ('value',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('BOOLEAN', {'default': False, 'label_on': 'True', 'label_off': 'False', 'description': 'Boolean value'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[bool]:
        return (_to_bool(kwargs.get('value', False)),)
