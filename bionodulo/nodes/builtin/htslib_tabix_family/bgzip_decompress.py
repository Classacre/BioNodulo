"""HTSlib ``bgzip -d`` decompression node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import HtslibTabixBase, _looks_compressed, stage_input


class BgzipDecompressNode(HtslibTabixBase):
    """Decompress a BGZF (bgzip) file back to its original text."""

    NODE_ID = "bgzip_decompress"
    DISPLAY_NAME = "BGZip Decompress"
    DESCRIPTION = "Decompress a BGZF (bgzip) file back to its original text"
    SEARCH_ALIASES = [
        "bgzip",
        "bgzf",
        "decompress",
        "gunzip",
        "uncompress",
        "htslib",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("decompressed",)
    OUTPUT_FILENAMES = ("decompressed.txt",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bgzip.html"
    UPSTREAM_MANPAGE = "bgzip.1"
    UPSTREAM_SOURCE = "bgzip.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "compressed": (
                    "FILE",
                    {"description": "BGZF-compressed file produced by bgzip (.gz/.bgz)"},
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        value = inputs.get("compressed")
        if value is None:
            return "Input 'compressed' must be a non-empty path"
        if not _looks_compressed(str(value)):
            return (
                "Input 'compressed' must end in .gz, .bgz, or .bgzf; bgzip ignores "
                "unknown suffixes"
            )
        return True

    @classmethod
    def _staged_input(cls, outputs: list[Path]) -> Path:
        """Return the staged ``.gz`` name that decompresses to the planned output."""
        return Path(f"{outputs[0]}.gz")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ["bgzip", "-d", "-f", str(inputs.get("compressed", ""))]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged = stage_input(inputs["compressed"], cls._staged_input(outputs))
        inputs["compressed"] = str(staged)
