"""random — utility_primitives node(s). One tool per file (extracted from utility_primitives.py)."""
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


class RandomSeedNode(SeedNode):
    """Planned random seed node ID, sharing SeedNode behavior."""
    NODE_ID = 'random_seed'
    DISPLAY_NAME = 'Random Seed'
    DESCRIPTION = 'Set a random seed for reproducible results, or generate a new random seed'
    SEARCH_ALIASES = ['random seed', 'seed', 'random', 'rng', 'reproducible', 'deterministic']
