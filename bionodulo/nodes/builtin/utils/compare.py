"""compare — utils node(s). One tool per file (extracted from utility_primitives.py)."""
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


class CompareNode(BaseNode):
    """Compare two numeric values and return a boolean result."""
    NODE_ID = 'compare'
    DISPLAY_NAME = 'Compare'
    CATEGORY = 'utils'
    DESCRIPTION = 'Compare two values using ==, !=, <, >, <=, >= operators'
    SEARCH_ALIASES = ['compare', 'equal', 'less', 'greater', 'comparison', 'condition', '==', '<', '>']
    RETURN_TYPES = ('BOOLEAN',)
    RETURN_NAMES = ('result',)
    REQUIRES_EXTERNAL_TOOLS = False
    _OPS: dict[str, Callable[[float, float], bool]] = {'==': operator.eq, '!=': operator.ne, '<': operator.lt, '>': operator.gt, '<=': operator.le, '>=': operator.ge}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'operation': (['==', '!=', '<', '>', '<=', '>='], {'default': '==', 'description': 'Comparison operator'}), 'a': ('FLOAT', {'default': 0.0, 'description': 'First value'}), 'b': ('FLOAT', {'default': 0.0, 'description': 'Second value'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[bool]:
        operation = str(kwargs.get('operation', '=='))
        if operation not in self._OPS:
            raise ValueError(f'Unsupported comparison operation: {operation}')
        return (bool(self._OPS[operation](float(kwargs.get('a', 0.0)), float(kwargs.get('b', 0.0)))),)
