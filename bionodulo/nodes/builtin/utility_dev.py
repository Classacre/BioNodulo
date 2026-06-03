"""Developer-facing utility nodes for debugging, dates, and type conversion."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"", "0", "false", "f", "no", "n", "off", "none", "null"}:
        return False
    return True


class DebugNode(BaseNode):
    """Print any value to console for debugging while passing it through."""

    NODE_ID = "debug"
    DISPLAY_NAME = "Debug"
    CATEGORY = "utils/dev"
    DESCRIPTION = "Print any value to console for debugging - passes value through unchanged"
    SEARCH_ALIASES = ["debug", "print", "log", "inspect", "trace", "console", "echo"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True

    _logger = logging.getLogger("bionodulo.debug")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": ("STRING", {"default": "", "multiline": True, "description": "Value to debug"}),
            },
            "optional": {
                "label": ("STRING", {"default": "", "description": "Label for the debug output"}),
                "log_level": (["info", "warn", "error", "debug"], {"default": "info", "description": "Log level"}),
                "show_type": ("BOOLEAN", {"default": True, "description": "Show the value's type"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        value = kwargs.get("value", "")
        label = str(kwargs.get("label", "") or "")
        log_level = str(kwargs.get("log_level", "info") or "info")
        show_type = bool(kwargs.get("show_type", True))

        formatted = self._format_value(value)
        prefix = f"[{label}]" if label else "[DEBUG]"
        type_info = f" (type: {type(value).__name__})" if show_type else ""
        message = f"{prefix}{type_info}\n{formatted}"

        log_method = getattr(self._logger, "warning" if log_level == "warn" else log_level, self._logger.info)
        log_method(message)
        print(message)
        return (formatted,)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, ensure_ascii=True, default=str)
        return str(value)


class BreakpointNode(BaseNode):
    """Interactive debugging pause point with safe non-pausing bypass paths."""

    NODE_ID = "breakpoint"
    DISPLAY_NAME = "Breakpoint"
    CATEGORY = "utils/dev"
    DESCRIPTION = "Pause execution to inspect values - resume, step over, or abort"
    SEARCH_ALIASES = ["breakpoint", "pause", "inspect", "interactive", "stop", "halt"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": ("STRING", {"default": "", "multiline": True, "description": "Value to inspect"}),
            },
            "optional": {
                "enabled": ("BOOLEAN", {"default": True, "description": "Enable this breakpoint"}),
                "label": ("STRING", {"default": "", "description": "Breakpoint label"}),
                "condition": ("STRING", {"default": "", "description": "Only break if this string is in the value"}),
                "timeout": ("INT", {"default": 300, "min": 0, "description": "Auto-resume after N seconds (0 = never)"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        value = kwargs.get("value", "")
        text = str(value)
        enabled = bool(kwargs.get("enabled", True))
        condition = str(kwargs.get("condition", "") or "")
        if not enabled or (condition and condition not in text):
            return (text,)

        timeout = int(kwargs.get("timeout", 300) or 0)
        label = str(kwargs.get("label", "") or "default")
        print(f"[BREAKPOINT: {label}] execution paused\n{text}")
        if timeout > 0:
            await asyncio.sleep(timeout)
        return (text,)


class DateTimeNode(BaseNode):
    """Get current date/time, format timestamps, and add/subtract days."""

    NODE_ID = "datetime"
    DISPLAY_NAME = "Date / Time"
    CATEGORY = "utils/format"
    DESCRIPTION = "Get current date/time, format timestamps, add/subtract intervals"
    SEARCH_ALIASES = ["datetime", "date", "time", "timestamp", "now", "format date", "clock"]
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("formatted", "timestamp", "iso")
    REQUIRES_EXTERNAL_TOOLS = False

    _PARSE_FORMATS = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y%m%d",
        "%Y%m%d%H%M%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%a %b %d %H:%M:%S %Y",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        operations = ["now", "format", "parse", "add_days", "subtract_days", "timestamp", "iso"]
        return {
            "required": {
                "operation": (operations, {"default": "now", "description": "Date/time operation"}),
            },
            "optional": {
                "format_string": ("STRING", {"default": "%Y-%m-%d %H:%M:%S", "description": "strftime format pattern"}),
                "date_string": ("STRING", {"default": "", "description": "Date string to parse"}),
                "days": ("INT", {"default": 0, "description": "Number of days"}),
                "timezone": ("STRING", {"default": "local", "description": "Timezone: local or UTC"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, int, str]:
        operation = str(kwargs.get("operation", "now") or "now")
        format_string = str(kwargs.get("format_string", "%Y-%m-%d %H:%M:%S") or "%Y-%m-%d %H:%M:%S")
        days = int(kwargs.get("days", 0) or 0)
        tz = timezone.utc if str(kwargs.get("timezone", "local")).lower() == "utc" else None
        now = datetime.now(tz)

        if operation in {"now", "format"}:
            return self._render(now, format_string)
        if operation == "timestamp":
            return (str(int(now.timestamp())), int(now.timestamp()), now.isoformat())
        if operation == "iso":
            return (now.isoformat(), int(now.timestamp()), now.isoformat())
        if operation == "add_days":
            return self._render(now + timedelta(days=days), format_string)
        if operation == "subtract_days":
            return self._render(now - timedelta(days=days), format_string)
        if operation == "parse":
            parsed = self._parse_date(str(kwargs.get("date_string", "") or ""))
            if tz is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=tz)
            return self._render(parsed, format_string)
        raise ValueError(f"Unsupported datetime operation: {operation}")

    @classmethod
    def _parse_date(cls, value: str) -> datetime:
        if not value.strip():
            raise ValueError("date_string is required for parse operation")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        for fmt in cls._PARSE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"Could not parse date string: {value}")

    @staticmethod
    def _render(value: datetime, format_string: str) -> tuple[str, int, str]:
        return (value.strftime(format_string), int(value.timestamp()), value.isoformat())


class TypeCastNode(BaseNode):
    """Convert between primitive types and simple file content."""

    NODE_ID = "type_cast"
    DISPLAY_NAME = "Type Cast"
    CATEGORY = "utils/dev"
    DESCRIPTION = "Convert between types: STRING, INT, FLOAT, BOOLEAN, FILE"
    SEARCH_ALIASES = ["cast", "convert", "type", "to_string", "to_int", "to_float", "to_bool"]
    RETURN_TYPES = ("STRING", "INT", "FLOAT", "BOOLEAN", "FILE")
    RETURN_NAMES = ("as_string", "as_int", "as_float", "as_bool", "as_file")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "target_type": (
                    ["STRING", "INT", "FLOAT", "BOOLEAN", "FILE_CONTENT", "FILE_FROM_STRING"],
                    {"default": "STRING", "description": "Target type to convert to"},
                ),
                "value": ("STRING", {"default": "", "multiline": True, "description": "Value to convert"}),
            },
            "optional": {
                "default_on_error": ("STRING", {"default": "", "description": "Default if conversion fails"}),
                "encoding": ("STRING", {"default": "utf-8", "description": "File encoding"}),
                "output_name": ("STRING", {"default": "type_cast.txt", "description": "Filename for FILE_FROM_STRING"}),
            },
            "hidden": {
                "context": ("ANY", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, int, float, bool, str]:
        context = kwargs.get("context")
        target_type = str(kwargs.get("target_type", "STRING") or "STRING")
        value = kwargs.get("value", "")
        default = kwargs.get("default_on_error", "")
        encoding = str(kwargs.get("encoding", "utf-8") or "utf-8")

        as_string = "" if value is None else str(value)
        as_int = self._as_int(value, default)
        as_float = self._as_float(value, default)
        as_bool = _to_bool(value)
        as_file = ""

        if target_type == "STRING":
            pass
        elif target_type == "INT":
            as_string = str(as_int)
            as_float = float(as_int)
            as_bool = as_int != 0
        elif target_type == "FLOAT":
            as_string = str(as_float)
            as_int = int(as_float)
            as_bool = as_float != 0.0
        elif target_type == "BOOLEAN":
            as_string = "true" if as_bool else "false"
            as_int = 1 if as_bool else 0
            as_float = float(as_int)
        elif target_type == "FILE_CONTENT":
            file_path = Path(str(value))
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            as_string = file_path.read_text(encoding=encoding)
            as_int = self._as_int(as_string, default)
            as_float = self._as_float(as_string, default)
            as_bool = _to_bool(as_string)
            as_file = str(file_path)
        elif target_type == "FILE_FROM_STRING":
            filename = Path(str(kwargs.get("output_name", "type_cast.txt") or "type_cast.txt")).name
            output_path = _node_output_dir(self, context) / filename
            output_path.write_text(as_string, encoding=encoding)
            as_file = str(output_path)
        else:
            raise ValueError(f"Unsupported target_type: {target_type}")

        return (as_string, as_int, as_float, as_bool, as_file)

    @staticmethod
    def _as_int(value: Any, default: Any = "") -> int:
        try:
            if isinstance(value, bool):
                return 1 if value else 0
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return int(float(default)) if str(default).strip() else 0

    @staticmethod
    def _as_float(value: Any, default: Any = "") -> float:
        try:
            if isinstance(value, bool):
                return 1.0 if value else 0.0
            return float(str(value).strip())
        except (TypeError, ValueError):
            return float(default) if str(default).strip() else 0.0
