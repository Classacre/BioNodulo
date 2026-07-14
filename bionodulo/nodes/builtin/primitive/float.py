"""float — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
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


class FloatPrimitiveNode(BaseNode):
    """Primitive floating-point value."""
    NODE_ID = 'float_primitive'
    DISPLAY_NAME = 'Float'
    CATEGORY = 'primitive'
    DESCRIPTION = 'A floating-point number with optional min/max/step constraints'
    SEARCH_ALIASES = ['float', 'decimal', 'number', 'real', 'double']
    RETURN_TYPES = ('FLOAT',)
    RETURN_NAMES = ('value',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'value': ('FLOAT', {'default': 0.0, 'min': -1000000000000.0, 'max': 1000000000000.0, 'step': 0.01, 'description': 'Float value'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[float]:
        return (float(kwargs.get('value', 0.0)),)
