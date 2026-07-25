"""Line-preserving literal and regular-expression replacement."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapter import PythonDataTransformNode, node_output_dir, path_value, validate_int


OUTPUT_EXTENSION_PATTERN = re.compile(r"^\.[A-Za-z0-9][A-Za-z0-9._-]*$")


class ReplaceTextNode(PythonDataTransformNode):
    """Replace literal text or Python regular-expression matches line by line."""

    NODE_ID = "replace_text"
    DISPLAY_NAME = "Replace Text"
    DESCRIPTION = "Replace literal text or Python regular-expression matches in a UTF-8 text file."
    SEARCH_ALIASES = ["replace", "find and replace", "regex replace", "text substitution", "pattern replace"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("replaced_file",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/re.html#re.sub"
    UPSTREAM_SOURCE = "Lib/re; pathlib UTF-8 text I/O"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing or non-UTF-8 files, empty searches, invalid regular expressions, invalid replacement "
        "backreferences, limits, and output extensions are fatal; literal replacements treat backslashes "
        "literally."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "UTF-8 text input"}),
                "search": ("STRING", {"default": "", "description": "Literal text or regex pattern"}),
                "replace": ("STRING", {"default": "", "description": "Replacement text"}),
            },
            "optional": {
                "use_regex": ("BOOLEAN", {"default": False}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
                "whole_word": ("BOOLEAN", {"default": False}),
                "limit_per_line": ("INT", {"default": 0, "min": 0, "max": 9999}),
                "affected_lines_only": ("BOOLEAN", {"default": False}),
                "output_extension": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("file")):
            return "Input 'file' must be a non-empty path-like value"
        search = str(inputs.get("search", ""))
        if not search:
            return "Input 'search' must not be empty"
        validation = validate_int(
            inputs.get("limit_per_line", 0),
            "limit_per_line",
            minimum=0,
            maximum=9999,
        )
        if validation is not True:
            return validation
        extension = str(inputs.get("output_extension", "") or "")
        if extension:
            normalized = extension if extension.startswith(".") else f".{extension}"
            if not OUTPUT_EXTENSION_PATTERN.fullmatch(normalized):
                return "Input 'output_extension' must be a filename extension without path separators"
        pattern = search if bool(inputs.get("use_regex", False)) else re.escape(search)
        if bool(inputs.get("whole_word", False)):
            pattern = rf"\b{pattern}\b"
        try:
            re.compile(pattern, 0 if bool(inputs.get("case_sensitive", True)) else re.IGNORECASE)
        except re.error as exc:
            return f"Input 'search' is not a valid regular expression: {exc}"
        return True

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        input_path = Path(path_value(kwargs["file"])).expanduser()
        search = str(kwargs["search"])
        replacement = str(kwargs.get("replace", ""))
        use_regex = bool(kwargs.get("use_regex", False))
        pattern = search if use_regex else re.escape(search)
        if bool(kwargs.get("whole_word", False)):
            pattern = rf"\b{pattern}\b"
        flags = 0 if bool(kwargs.get("case_sensitive", True)) else re.IGNORECASE
        compiled = re.compile(pattern, flags)
        limit = int(kwargs.get("limit_per_line", 0))
        extension = str(kwargs.get("output_extension", "") or "") or input_path.suffix
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        output_path = node_output_dir(self, context) / f"{input_path.stem}.replaced{extension}"

        def literal_replacement(_match: re.Match[str]) -> str:
            return replacement

        replacement_value: str | Any
        if use_regex:
            replacement_value = replacement
        else:
            replacement_value = literal_replacement
        with input_path.open("r", encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
            for line in source:
                replaced, count = compiled.subn(replacement_value, line, count=limit)
                if count or not bool(kwargs.get("affected_lines_only", False)):
                    target.write(replaced)
        return (str(output_path),)
