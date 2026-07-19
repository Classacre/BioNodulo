"""Bounded plain-text workflow output contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import PythonUtilityNode, path_value, validate_int, validate_regular_file


class ViewTextFileNode(PythonUtilityNode):
    """Return a bounded prefix of a regular text file."""

    NODE_ID = "view_text_file"
    DISPLAY_NAME = "View Text File"
    CATEGORY = "utils"
    DESCRIPTION = "Display a bounded prefix of a text file as a workflow output"
    SEARCH_ALIASES = ["view", "display", "cat", "text", "output"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("content",)
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/pathlib.html"
    UPSTREAM_SOURCE = "Lib/pathlib.py; Objects/bytesobject.c"
    MAX_OUTPUT_BYTES = 1024 * 1024

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"file": ("FILE", {"description": "Text file to display"})},
            "optional": {
                "max_lines": ("INT", {"default": 1000, "min": 1, "description": "Maximum lines to display"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = validate_regular_file(inputs.get("file"), label="Text file")
        if validation is not True:
            return validation
        return validate_int(inputs.get("max_lines", 1000), "max_lines", minimum=1, maximum=100000)

    async def run(self, **kwargs: Any) -> tuple[str]:
        kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        path = Path(path_value(kwargs["file"]))
        max_lines = int(kwargs.get("max_lines", 1000))
        with path.open("rb") as handle:
            raw = handle.read(self.MAX_OUTPUT_BYTES + 1)
        byte_truncated = len(raw) > self.MAX_OUTPUT_BYTES
        raw = raw[: self.MAX_OUTPUT_BYTES]
        lines = raw.decode("utf-8", errors="replace").splitlines()
        line_truncated = len(lines) > max_lines
        rendered = lines[:max_lines]
        if line_truncated:
            rendered.append(f"... ({max_lines} lines shown)")
        if byte_truncated:
            rendered.append(f"... (output truncated at {self.MAX_OUTPUT_BYTES} bytes)")
        return ("\n".join(rendered),)
