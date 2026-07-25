"""Python 3.12 format-string primitive with JSON variables."""

from __future__ import annotations

import json
from typing import Any

from .adapter import PythonPrimitiveNode


class StringFormatNode(PythonPrimitiveNode):
    """Apply Python's str.format mapping behavior to JSON-compatible values."""

    NODE_ID = "string_format"
    DISPLAY_NAME = "String Format"
    DESCRIPTION = "Render a Python format string with variables from a JSON object."
    SEARCH_ALIASES = ["string", "format", "template", "text", "primitive"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/string.html#format-string-syntax"
    UPSTREAM_SOURCE = "Objects/unicodeobject.c; Lib/string.py"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Malformed JSON, non-object variables, unknown fields, invalid conversions, and invalid format specs "
        "are fatal according to Python 3.12 str.format semantics."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "template": ("STRING", {"multiline": True, "description": "Python format string"}),
            },
            "optional": {
                "variables_json": (
                    "STRING",
                    {"default": "{}", "multiline": True, "description": "JSON object of variables"},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        kwargs.pop("context", None)
        try:
            variables = json.loads(str(kwargs.get("variables_json", "{}") or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"variables_json must contain valid JSON: {exc.msg}") from exc
        if not isinstance(variables, dict):
            raise ValueError("variables_json must be a JSON object")
        try:
            return (str(kwargs.get("template", "")).format(**variables),)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"String formatting failed: {exc}") from exc
