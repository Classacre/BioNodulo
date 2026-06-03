"""String and collection utility nodes."""
from __future__ import annotations

import json
import random
import re
from typing import Any

from bionodulo.nodes.base import BaseNode


def _decode_delimiter(delimiter: Any, default: str = "\n") -> str:
    text = str(delimiter if delimiter is not None else default)
    return {"\\n": "\n", "\\t": "\t", "\\r": "\r"}.get(text, text)


def _parse_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]

    text = str(value if value is not None else "").strip()
    if not text:
        return []

    if text[0] in "[{":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"items must be valid JSON or comma/newline text: {exc.msg}") from exc
        if not isinstance(parsed, list):
            raise ValueError("items JSON must be a list")
        return [str(item) for item in parsed]

    separator = "\n" if "\n" in text else ","
    return [item.strip() for item in text.split(separator) if item.strip()]


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _parse_json_object(value: Any, field_name: str = "dictionary") -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)

    text = str(value if value is not None else "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON object: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return dict(parsed)


class StringOperationsNode(BaseNode):
    """Multi-mode string manipulation node."""

    NODE_ID = "string_operations"
    DISPLAY_NAME = "String Operations"
    CATEGORY = "utils"
    DESCRIPTION = "String manipulation: concat, case conversion, regex replace, split, length, contains"
    SEARCH_ALIASES = [
        "string",
        "text",
        "concat",
        "concatenate",
        "uppercase",
        "lowercase",
        "regex",
        "replace",
        "split",
        "length",
        "contains",
    ]
    RETURN_TYPES = ("STRING", "INT", "BOOLEAN")
    RETURN_NAMES = ("result", "length", "matched")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (
                    ["concat", "upper", "lower", "regex_replace", "split", "length", "contains"],
                    {"default": "concat", "description": "String operation"},
                ),
                "string": ("STRING", {"default": "", "multiline": True, "description": "Primary string"}),
            },
            "optional": {
                "string_b": ("STRING", {"default": "", "description": "Secondary string"}),
                "delimiter": ("STRING", {"default": "", "description": "Delimiter for concat or split"}),
                "pattern": ("STRING", {"default": "", "description": "Regex pattern"}),
                "replacement": ("STRING", {"default": "", "description": "Regex replacement"}),
                "index": ("INT", {"default": 0, "description": "Split item index"}),
                "substring": ("STRING", {"default": "", "description": "Substring to search for"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, int, bool]:
        operation = str(kwargs.get("operation", "concat"))
        text = str(kwargs.get("string", ""))

        if operation == "concat":
            delimiter = _decode_delimiter(kwargs.get("delimiter", ""), default="")
            result = f"{text}{delimiter}{kwargs.get('string_b', '')}"
            return (result, len(result), False)

        if operation == "upper":
            result = text.upper()
            return (result, len(result), False)

        if operation == "lower":
            result = text.lower()
            return (result, len(result), False)

        if operation == "regex_replace":
            pattern = str(kwargs.get("pattern", ""))
            if not pattern:
                raise ValueError("regex_replace requires a non-empty pattern")
            try:
                result, count = re.subn(pattern, str(kwargs.get("replacement", "")), text)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {exc}") from exc
            return (result, len(result), count > 0)

        if operation == "split":
            delimiter = _decode_delimiter(kwargs.get("delimiter", ","))
            if delimiter == "":
                raise ValueError("split requires a non-empty delimiter")
            parts = text.split(delimiter)
            index = int(kwargs.get("index", 0))
            if not -len(parts) <= index < len(parts):
                raise ValueError(f"split index {index} is out of range for {len(parts)} items")
            return (parts[index], len(parts), True)

        if operation == "length":
            return (text, len(text), False)

        if operation == "contains":
            substring = str(kwargs.get("substring", kwargs.get("string_b", "")))
            return ("", 0, substring in text)

        raise ValueError(f"Unsupported string operation: {operation}")


class RegexExtractNode(BaseNode):
    """Extract regex matches from text."""

    NODE_ID = "regex_extract"
    DISPLAY_NAME = "Regex Extract"
    CATEGORY = "utils"
    DESCRIPTION = "Extract text using regular expressions with capture group selection"
    SEARCH_ALIASES = ["regex", "extract", "capture", "pattern", "match", "text parse"]
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("matches_json", "count")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True, "description": "Text to search"}),
                "pattern": ("STRING", {"default": "", "description": "Regular expression pattern"}),
            },
            "optional": {
                "group": ("INT", {"default": 0, "min": 0, "description": "Capture group to return; 0 returns full match"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, int]:
        text = str(kwargs.get("text", ""))
        pattern = str(kwargs.get("pattern", "") or "")
        if not pattern:
            raise ValueError("pattern is required")
        group = int(kwargs.get("group", 0))

        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {exc}") from exc

        matches: list[str] = []
        for match in compiled.finditer(text):
            if group > len(match.groups()):
                raise ValueError(f"group {group} is out of range for {len(match.groups())} capture groups")
            matches.append(match.group(group))

        return (_to_json(matches), len(matches))


class ListOperationsNode(BaseNode):
    """Multi-mode list manipulation node."""

    NODE_ID = "list_operations"
    DISPLAY_NAME = "List Operations"
    CATEGORY = "utils"
    DESCRIPTION = "List manipulation: join, append, prepend, unique, sort, length, contains"
    SEARCH_ALIASES = ["list", "array", "collection", "join", "append", "prepend", "unique", "sort", "length", "contains"]
    RETURN_TYPES = ("STRING", "INT", "BOOLEAN")
    RETURN_NAMES = ("result", "length", "contains")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (
                    ["join", "append", "prepend", "unique", "sort", "length", "contains"],
                    {"default": "length", "description": "List operation"},
                ),
                "items": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "JSON list, comma text, or newline text"},
                ),
            },
            "optional": {
                "item": ("STRING", {"default": "", "description": "Item for append/prepend/contains"}),
                "delimiter": ("STRING", {"default": ",", "description": "Delimiter for join"}),
                "reverse": ("BOOLEAN", {"default": False, "description": "Reverse sort order"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, int, bool]:
        operation = str(kwargs.get("operation", "length"))
        items = _parse_items(kwargs.get("items", ""))

        if operation == "join":
            delimiter = _decode_delimiter(kwargs.get("delimiter", ","))
            return (delimiter.join(items), len(items), False)

        if operation == "append":
            result = [*items, str(kwargs.get("item", ""))]
            return (_to_json(result), len(result), False)

        if operation == "prepend":
            result = [str(kwargs.get("item", "")), *items]
            return (_to_json(result), len(result), False)

        if operation == "unique":
            result = list(dict.fromkeys(items))
            return (_to_json(result), len(result), False)

        if operation == "sort":
            reverse = bool(kwargs.get("reverse", False))
            result = sorted(items, key=_sort_key, reverse=reverse)
            return (_to_json(result), len(result), False)

        if operation == "length":
            return ("", len(items), False)

        if operation == "contains":
            return ("", len(items), str(kwargs.get("item", "")) in items)

        raise ValueError(f"Unsupported list operation: {operation}")


def _sort_key(item: str) -> tuple[int, float | str]:
    try:
        return (0, float(item))
    except ValueError:
        return (1, item)


class SelectFromListNode(BaseNode):
    """Select a single item from a list."""

    NODE_ID = "select_from_list"
    DISPLAY_NAME = "Select From List"
    CATEGORY = "utils"
    DESCRIPTION = "Select one item from a list by index, first, last, or random mode"
    SEARCH_ALIASES = ["select", "pick", "choose", "list", "index", "first", "last", "random"]
    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("item", "index")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": (["index", "first", "last", "random"], {"default": "index", "description": "Selection mode"}),
                "items": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "JSON list, comma text, or newline text"},
                ),
            },
            "optional": {
                "index": ("INT", {"default": 0, "description": "Index for index mode"}),
                "seed": ("INT", {"default": 0, "description": "Optional seed for random mode; 0 uses system randomness"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, int]:
        mode = str(kwargs.get("mode", "index"))
        items = _parse_items(kwargs.get("items", ""))
        if not items:
            raise ValueError("Cannot select from an empty list")

        if mode == "index":
            index = int(kwargs.get("index", 0))
        elif mode == "first":
            index = 0
        elif mode == "last":
            index = len(items) - 1
        elif mode == "random":
            seed = int(kwargs.get("seed", 0))
            rng = random.Random(seed) if seed else random
            index = rng.randrange(len(items))
        else:
            raise ValueError(f"Unsupported select mode: {mode}")

        if not -len(items) <= index < len(items):
            raise ValueError(f"index {index} is out of range for {len(items)} items")
        if index < 0:
            index += len(items)
        return (items[index], index)


class DictionaryNode(BaseNode):
    """JSON object dictionary operations."""

    NODE_ID = "dictionary"
    DISPLAY_NAME = "Dictionary"
    CATEGORY = "utils"
    DESCRIPTION = "JSON object operations: get, set, keys, values, merge, has_key"
    SEARCH_ALIASES = ["dict", "map", "dictionary", "key-value", "json", "object", "properties"]
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("result_json", "value", "count")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": (
                    ["get", "set", "keys", "values", "merge", "has_key"],
                    {"default": "get", "description": "Dictionary operation"},
                ),
                "dictionary": ("STRING", {"default": "{}", "multiline": True, "description": "Dictionary as JSON object"}),
            },
            "optional": {
                "key": ("STRING", {"default": "", "description": "Key"}),
                "value": ("STRING", {"default": "", "description": "Value for set"}),
                "dictionary_b": ("STRING", {"default": "{}", "multiline": True, "description": "Second JSON object for merge"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str, int]:
        operation = str(kwargs.get("operation", "get"))
        data = _parse_json_object(kwargs.get("dictionary", "{}"))
        key = str(kwargs.get("key", ""))
        result_json = _to_json(data)

        if operation == "get":
            return (result_json, _json_value(data.get(key, "")), len(data))

        if operation == "set":
            data[key] = str(kwargs.get("value", ""))
            return (_to_json(data), _json_value(data[key]), len(data))

        if operation == "keys":
            return (result_json, _to_json(list(data.keys())), len(data))

        if operation == "values":
            return (result_json, _to_json(list(data.values())), len(data))

        if operation == "merge":
            data.update(_parse_json_object(kwargs.get("dictionary_b", "{}"), field_name="dictionary_b"))
            return (_to_json(data), "", len(data))

        if operation == "has_key":
            return (result_json, "true" if key in data else "false", len(data))

        raise ValueError(f"Unsupported dictionary operation: {operation}")


def _json_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return _to_json(value)
