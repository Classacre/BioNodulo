"""range — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
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


class RangeListNode(BaseNode):
    """Generate integer ranges for loops and batch operations."""
    NODE_ID = 'range_list'
    DISPLAY_NAME = 'Range List'
    CATEGORY = 'primitive'
    DESCRIPTION = 'Generate a list of integers in a range with configurable step'
    SEARCH_ALIASES = ['range', 'range list', 'integer list', 'sequence', 'loop', 'batch']
    RETURN_TYPES = ('STRING', 'INT')
    RETURN_NAMES = ('values_json', 'count')
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'start': ('INT', {'default': 0, 'description': 'First integer in the range'}), 'stop': ('INT', {'default': 10, 'description': 'Stop value, exclusive'}), 'step': ('INT', {'default': 1, 'description': 'Step between values'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, int]:
        step = int(kwargs.get('step', 1))
        if step == 0:
            raise ValueError('step cannot be zero')
        values = list(range(int(kwargs.get('start', 0)), int(kwargs.get('stop', 10)), step))
        return (json.dumps(values), len(values))
