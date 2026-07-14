"""math — utils node(s). One tool per file (extracted from utility_primitives.py)."""
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


class MathNode(BaseNode):
    """Basic arithmetic operations on two numbers."""
    NODE_ID = 'math'
    DISPLAY_NAME = 'Math'
    CATEGORY = 'utils'
    DESCRIPTION = 'Perform basic arithmetic: add, subtract, multiply, divide, power, modulo, min, max'
    SEARCH_ALIASES = ['math', 'arithmetic', 'calculate', 'add', 'subtract', 'multiply', 'divide', 'power']
    RETURN_TYPES = ('FLOAT', 'INT')
    RETURN_NAMES = ('float_result', 'int_result')
    REQUIRES_EXTERNAL_TOOLS = False
    _OPS: dict[str, Callable[[float, float], float]] = {'add': operator.add, 'subtract': operator.sub, 'multiply': operator.mul, 'divide': operator.truediv, 'power': operator.pow, 'modulo': operator.mod, 'min': min, 'max': max}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        operations = ['add', 'subtract', 'multiply', 'divide', 'power', 'modulo', 'min', 'max']
        return {'required': {'operation': (operations, {'default': 'add', 'description': 'Arithmetic operation'}), 'a': ('FLOAT', {'default': 0.0, 'description': 'First operand'}), 'b': ('FLOAT', {'default': 0.0, 'description': 'Second operand'})}, 'optional': {'output_type': (['auto', 'int', 'float'], {'default': 'auto', 'description': 'Force output type'})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[float, int]:
        operation = str(kwargs.get('operation', 'add'))
        if operation not in self._OPS:
            raise ValueError(f'Unsupported math operation: {operation}')
        a = float(kwargs.get('a', 0.0))
        b = float(kwargs.get('b', 0.0))
        if operation == 'divide' and b == 0:
            raise ValueError('Division by zero')
        if operation == 'modulo' and b == 0:
            raise ValueError('Modulo by zero')
        result = float(self._OPS[operation](a, b))
        output_type = str(kwargs.get('output_type', 'auto') or 'auto')
        if output_type == 'int':
            result = float(int(result))
        elif output_type not in {'auto', 'float'}:
            raise ValueError(f'Unsupported math output_type: {output_type}')
        return (result, int(result))
