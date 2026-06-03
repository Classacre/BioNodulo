"""Primitive value, math, and logic utility nodes."""
from __future__ import annotations

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
    if text in {"", "0", "false", "f", "no", "n", "off", "none", "null"}:
        return False
    return True


class StringPrimitiveNode(BaseNode):
    """Primitive string value."""

    NODE_ID = "string_primitive"
    DISPLAY_NAME = "String"
    CATEGORY = "primitive"
    DESCRIPTION = "A string value that can be passed to other nodes"
    SEARCH_ALIASES = ["text", "string", "value", "literal", "constant"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": ("STRING", {"default": "", "multiline": True, "description": "String value"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        return (str(kwargs.get("value", "")),)


class IntegerPrimitiveNode(BaseNode):
    """Primitive integer value."""

    NODE_ID = "integer_primitive"
    DISPLAY_NAME = "Integer"
    CATEGORY = "primitive"
    DESCRIPTION = "An integer value with optional min/max/step constraints"
    SEARCH_ALIASES = ["int", "integer", "number", "whole", "count"]
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("value",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": (
                    "INT",
                    {
                        "default": 0,
                        "min": -2_147_483_648,
                        "max": 2_147_483_647,
                        "step": 1,
                        "description": "Integer value",
                    },
                ),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[int]:
        return (int(kwargs.get("value", 0)),)


class FloatPrimitiveNode(BaseNode):
    """Primitive floating-point value."""

    NODE_ID = "float_primitive"
    DISPLAY_NAME = "Float"
    CATEGORY = "primitive"
    DESCRIPTION = "A floating-point number with optional min/max/step constraints"
    SEARCH_ALIASES = ["float", "decimal", "number", "real", "double"]
    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("value",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": -1e12,
                        "max": 1e12,
                        "step": 0.01,
                        "description": "Float value",
                    },
                ),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float]:
        return (float(kwargs.get("value", 0.0)),)


class BooleanPrimitiveNode(BaseNode):
    """Primitive boolean value."""

    NODE_ID = "boolean_primitive"
    DISPLAY_NAME = "Boolean"
    CATEGORY = "primitive"
    DESCRIPTION = "A true/false toggle value"
    SEARCH_ALIASES = ["bool", "boolean", "toggle", "flag", "switch", "true", "false"]
    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("value",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "True",
                        "label_off": "False",
                        "description": "Boolean value",
                    },
                ),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[bool]:
        return (_to_bool(kwargs.get("value", False)),)


class MathNode(BaseNode):
    """Basic arithmetic operations on two numbers."""

    NODE_ID = "math"
    DISPLAY_NAME = "Math"
    CATEGORY = "utils"
    DESCRIPTION = "Perform basic arithmetic: add, subtract, multiply, divide, power, modulo, min, max"
    SEARCH_ALIASES = ["math", "arithmetic", "calculate", "add", "subtract", "multiply", "divide", "power"]
    RETURN_TYPES = ("FLOAT", "INT")
    RETURN_NAMES = ("float_result", "int_result")
    REQUIRES_EXTERNAL_TOOLS = False

    _OPS: dict[str, Callable[[float, float], float]] = {
        "add": operator.add,
        "subtract": operator.sub,
        "multiply": operator.mul,
        "divide": operator.truediv,
        "power": operator.pow,
        "modulo": operator.mod,
        "min": min,
        "max": max,
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        operations = ["add", "subtract", "multiply", "divide", "power", "modulo", "min", "max"]
        return {
            "required": {
                "operation": (operations, {"default": "add", "description": "Arithmetic operation"}),
                "a": ("FLOAT", {"default": 0.0, "description": "First operand"}),
                "b": ("FLOAT", {"default": 0.0, "description": "Second operand"}),
            },
            "optional": {
                "output_type": (["auto", "int", "float"], {"default": "auto", "description": "Force output type"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float, int]:
        operation = str(kwargs.get("operation", "add"))
        if operation not in self._OPS:
            raise ValueError(f"Unsupported math operation: {operation}")

        a = float(kwargs.get("a", 0.0))
        b = float(kwargs.get("b", 0.0))
        if operation == "divide" and b == 0:
            raise ValueError("Division by zero")
        if operation == "modulo" and b == 0:
            raise ValueError("Modulo by zero")

        result = float(self._OPS[operation](a, b))
        output_type = str(kwargs.get("output_type", "auto") or "auto")
        if output_type == "int":
            result = float(int(result))
        elif output_type not in {"auto", "float"}:
            raise ValueError(f"Unsupported math output_type: {output_type}")
        return (result, int(result))


class CompareNode(BaseNode):
    """Compare two numeric values and return a boolean result."""

    NODE_ID = "compare"
    DISPLAY_NAME = "Compare"
    CATEGORY = "utils"
    DESCRIPTION = "Compare two values using ==, !=, <, >, <=, >= operators"
    SEARCH_ALIASES = ["compare", "equal", "less", "greater", "comparison", "condition", "==", "<", ">"]
    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("result",)
    REQUIRES_EXTERNAL_TOOLS = False

    _OPS: dict[str, Callable[[float, float], bool]] = {
        "==": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        ">": operator.gt,
        "<=": operator.le,
        ">=": operator.ge,
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (["==", "!=", "<", ">", "<=", ">="], {"default": "==", "description": "Comparison operator"}),
                "a": ("FLOAT", {"default": 0.0, "description": "First value"}),
                "b": ("FLOAT", {"default": 0.0, "description": "Second value"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[bool]:
        operation = str(kwargs.get("operation", "=="))
        if operation not in self._OPS:
            raise ValueError(f"Unsupported comparison operation: {operation}")
        return (bool(self._OPS[operation](float(kwargs.get("a", 0.0)), float(kwargs.get("b", 0.0)))),)


class ConstantsNode(BaseNode):
    """Common mathematical and bioinformatics constants."""

    NODE_ID = "constants"
    DISPLAY_NAME = "Constants"
    CATEGORY = "primitive"
    DESCRIPTION = "Common mathematical and bioinformatics constants"
    SEARCH_ALIASES = ["constant", "pi", "e", "genome", "value", "preset"]
    RETURN_TYPES = ("FLOAT", "INT", "STRING")
    RETURN_NAMES = ("float_value", "int_value", "name")
    REQUIRES_EXTERNAL_TOOLS = False

    _CONSTANTS: dict[str, float | int] = {
        "PI": math.pi,
        "E": math.e,
        "TAU": math.tau,
        "PHI": 1.618033988749895,
        "HG38_SIZE": 3_209_286_105,
        "HG19_SIZE": 3_095_677_412,
        "MM10_SIZE": 2_728_222_451,
        "ECOLI_SIZE": 4_641_652,
        "AVOGADRO": 6.02214076e23,
        "KB": 1_024,
        "MB": 1_048_576,
        "GB": 1_073_741_824,
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "constant": (list(cls._CONSTANTS), {"default": "PI", "description": "Select a constant value"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float, int, str]:
        name = str(kwargs.get("constant", "PI"))
        if name not in self._CONSTANTS:
            raise ValueError(f"Unsupported constant: {name}")
        value = self._CONSTANTS[name]
        return (float(value), int(value), name)


class SeedNode(BaseNode):
    """Random seed management for reproducibility."""

    NODE_ID = "seed"
    DISPLAY_NAME = "Seed"
    CATEGORY = "primitive"
    DESCRIPTION = "Set a random seed for reproducible results, or generate a new random seed"
    SEARCH_ALIASES = ["seed", "random", "rng", "reproducible", "deterministic"]
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": (["fixed", "random"], {"default": "fixed", "description": "Use a fixed seed or generate a random one"}),
                "seed": (
                    "INT",
                    {
                        "default": 42,
                        "min": 0,
                        "max": 2_147_483_647,
                        "description": "Fixed seed value (used when mode=fixed)",
                    },
                ),
            },
            "optional": {
                "increment": ("INT", {"default": 0, "description": "Add this to the seed"}),
            },
            "hidden": {},
        }

    @classmethod
    def IS_CHANGED(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("mode", "fixed")) == "random":
            return uuid.uuid4().hex[:16]
        return super().IS_CHANGED(inputs)

    async def run(self, **kwargs: Any) -> tuple[int]:
        mode = str(kwargs.get("mode", "fixed"))
        if mode not in {"fixed", "random"}:
            raise ValueError(f"Unsupported seed mode: {mode}")
        base_seed = random.randint(0, 2_147_483_647) if mode == "random" else int(kwargs.get("seed", 42))
        increment = int(kwargs.get("increment", 0))
        return ((base_seed + increment) % 2_147_483_648,)


class RandomSeedNode(SeedNode):
    """Planned random seed node ID, sharing SeedNode behavior."""

    NODE_ID = "random_seed"
    DISPLAY_NAME = "Random Seed"
    DESCRIPTION = "Set a random seed for reproducible results, or generate a new random seed"
    SEARCH_ALIASES = ["random seed", "seed", "random", "rng", "reproducible", "deterministic"]
