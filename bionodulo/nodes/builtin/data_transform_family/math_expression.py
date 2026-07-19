"""Bounded numeric AST evaluation using Python 3.12 operators and math."""

from __future__ import annotations

import ast
import json
import math
import operator
from collections.abc import Callable
from typing import Any, ClassVar

from .adapter import PythonPrimitiveNode, format_scalar


MAX_EXPRESSION_LENGTH = 1000
MAX_AST_NODES = 128
MAX_ABSOLUTE_EXPONENT = 100.0


class MathExpressionNode(PythonPrimitiveNode):
    """Evaluate a bounded arithmetic expression without eval or arbitrary calls."""

    NODE_ID = "math_expression"
    DISPLAY_NAME = "Math Expression"
    DESCRIPTION = "Evaluate a bounded arithmetic expression with explicit numeric JSON variables."
    SEARCH_ALIASES = ["math", "expression", "calculate", "primitive", "number"]
    RETURN_TYPES = ("FLOAT", "INT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("float_result", "int_result", "boolean_result", "string_result")
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/ast.html"
    UPSTREAM_SOURCE = "Lib/ast.py; Modules/mathmodule.c; Python numeric operators"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Malformed JSON, non-numeric variables, unknown names, unsupported AST elements, excessive expression "
        "size, excessive exponents, domain errors, division by zero, and non-finite results are fatal."
    )
    BINARY_OPERATORS: ClassVar[dict[type[ast.operator], Callable[[float, float], float]]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    UNARY_OPERATORS: ClassVar[dict[type[ast.unaryop], Callable[[float], float]]] = {
        ast.UAdd: lambda value: value,
        ast.USub: operator.neg,
    }
    APPROVED_FUNCTIONS = frozenset({"abs", "ceil", "floor", "log", "max", "min", "round", "sqrt"})

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "expression": ("STRING", {"description": "Arithmetic expression such as a * 2 + b"}),
            },
            "optional": {
                "variables_json": (
                    "STRING",
                    {"default": "{}", "multiline": True, "description": "JSON object of numeric variables"},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float, int, bool, str]:
        kwargs.pop("context", None)
        expression = str(kwargs.get("expression", "")).strip()
        if not expression:
            raise ValueError("expression must be non-empty")
        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise ValueError(f"expression must not exceed {MAX_EXPRESSION_LENGTH} characters")
        try:
            variables_payload = json.loads(str(kwargs.get("variables_json", "{}") or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"variables_json must contain valid JSON: {exc.msg}") from exc
        if not isinstance(variables_payload, dict):
            raise ValueError("variables_json must be a JSON object")
        variables: dict[str, float] = {}
        for key, raw_value in variables_payload.items():
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError(f"Variable {key!r} must be a JSON number")
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError(f"Variable {key!r} must be finite")
            variables[str(key)] = value
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid math expression: {exc.msg}") from exc
        if sum(1 for _node in ast.walk(tree)) > MAX_AST_NODES:
            raise ValueError(f"expression must not exceed {MAX_AST_NODES} AST nodes")
        value = self.evaluate(tree.body, variables)
        self.require_finite(value)
        return value, int(value), bool(value), format_scalar(value)

    @classmethod
    def evaluate(cls, node: ast.AST, variables: dict[str, float]) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("Math expressions only support numeric constants")
            return cls.require_finite(float(node.value))
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"Unknown variable: {node.id}")
            return variables[node.id]
        if isinstance(node, ast.BinOp):
            operation = cls.BINARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            left = cls.evaluate(node.left, variables)
            right = cls.evaluate(node.right, variables)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_ABSOLUTE_EXPONENT:
                raise ValueError(f"Absolute exponent must not exceed {MAX_ABSOLUTE_EXPONENT:g}")
            try:
                return cls.require_finite(float(operation(left, right)))
            except (OverflowError, ValueError, ZeroDivisionError) as exc:
                raise ValueError(f"Math operation failed: {exc}") from exc
        if isinstance(node, ast.UnaryOp):
            operation = cls.UNARY_OPERATORS.get(type(node.op))
            if operation is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return cls.require_finite(float(operation(cls.evaluate(node.operand, variables))))
        if isinstance(node, ast.Call):
            if node.keywords:
                raise ValueError("Math functions do not accept keyword arguments")
            if not isinstance(node.func, ast.Name) or node.func.id not in cls.APPROVED_FUNCTIONS:
                raise ValueError("Only approved math functions are supported")
            arguments = [cls.evaluate(argument, variables) for argument in node.args]
            return cls.call_function(node.func.id, arguments)
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")

    @classmethod
    def call_function(cls, name: str, arguments: list[float]) -> float:
        try:
            if name in {"abs", "ceil", "floor", "sqrt"}:
                if len(arguments) != 1:
                    raise ValueError(f"{name} requires exactly one argument")
                function = {
                    "abs": abs,
                    "ceil": math.ceil,
                    "floor": math.floor,
                    "sqrt": math.sqrt,
                }[name]
                result = function(arguments[0])
            elif name == "log":
                if len(arguments) == 1:
                    result = math.log(arguments[0])
                elif len(arguments) == 2:
                    result = math.log(arguments[0], arguments[1])
                else:
                    raise ValueError("log requires one or two arguments")
            elif name in {"min", "max"}:
                if not arguments:
                    raise ValueError(f"{name} requires at least one argument")
                result = min(arguments) if name == "min" else max(arguments)
            else:
                if not 1 <= len(arguments) <= 2:
                    raise ValueError("round requires one or two arguments")
                if len(arguments) == 1:
                    result = round(arguments[0])
                else:
                    digits = arguments[1]
                    if not digits.is_integer():
                        raise ValueError("round digits must be an integer")
                    result = round(arguments[0], int(digits))
            return cls.require_finite(float(result))
        except (OverflowError, ValueError, ZeroDivisionError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith((name, "round")):
                raise
            raise ValueError(f"Math function {name} failed: {exc}") from exc

    @staticmethod
    def require_finite(value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Math result must be finite")
        return value
