"""constants — primitive node(s). One tool per file (extracted from utility_primitives.py)."""
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


class ConstantsNode(BaseNode):
    """Common mathematical and bioinformatics constants."""
    NODE_ID = 'constants'
    DISPLAY_NAME = 'Constants'
    CATEGORY = 'primitive'
    DESCRIPTION = 'Common mathematical and bioinformatics constants'
    SEARCH_ALIASES = ['constant', 'pi', 'e', 'genome', 'value', 'preset']
    RETURN_TYPES = ('FLOAT', 'INT', 'STRING')
    RETURN_NAMES = ('float_value', 'int_value', 'name')
    REQUIRES_EXTERNAL_TOOLS = False
    _CONSTANTS: dict[str, float | int] = {'PI': math.pi, 'E': math.e, 'TAU': math.tau, 'PHI': 1.618033988749895, 'HG38_SIZE': 3209286105, 'HG19_SIZE': 3095677412, 'MM10_SIZE': 2728222451, 'ECOLI_SIZE': 4641652, 'AVOGADRO': 6.02214076e+23, 'KB': 1024, 'MB': 1048576, 'GB': 1073741824}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'constant': (list(cls._CONSTANTS), {'default': 'PI', 'description': 'Select a constant value'})}, 'optional': {}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[float, int, str]:
        name = str(kwargs.get('constant', 'PI'))
        if name not in self._CONSTANTS:
            raise ValueError(f'Unsupported constant: {name}')
        value = self._CONSTANTS[name]
        return (float(value), int(value), name)
