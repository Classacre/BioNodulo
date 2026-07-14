"""seed — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
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


class SeedNode(BaseNode):
    """Random seed management for reproducibility."""
    NODE_ID = 'seed'
    DISPLAY_NAME = 'Seed'
    CATEGORY = 'primitive'
    DESCRIPTION = 'Set a random seed for reproducible results, or generate a new random seed'
    SEARCH_ALIASES = ['seed', 'random', 'rng', 'reproducible', 'deterministic']
    RETURN_TYPES = ('INT',)
    RETURN_NAMES = ('seed',)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mode': (['fixed', 'random'], {'default': 'fixed', 'description': 'Use a fixed seed or generate a random one'}), 'seed': ('INT', {'default': 42, 'min': 0, 'max': 2147483647, 'description': 'Fixed seed value (used when mode=fixed)'})}, 'optional': {'increment': ('INT', {'default': 0, 'description': 'Add this to the seed'})}, 'hidden': {}}

    @classmethod
    def IS_CHANGED(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get('mode', 'fixed')) == 'random':
            return uuid.uuid4().hex[:16]
        return super().IS_CHANGED(inputs)

    async def run(self, **kwargs: Any) -> tuple[int]:
        mode = str(kwargs.get('mode', 'fixed'))
        if mode not in {'fixed', 'random'}:
            raise ValueError(f'Unsupported seed mode: {mode}')
        base_seed = random.randint(0, 2147483647) if mode == 'random' else int(kwargs.get('seed', 42))
        increment = int(kwargs.get('increment', 0))
        return ((base_seed + increment) % 2147483648,)
