"""HTSlib ``bgzip`` block-compression node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import HtslibTabixBase, _looks_compressed, stage_input


class BgzipCompressNode(HtslibTabixBase):
    """Block-gzip a coordinate-sorted text file into a BGZF ``<name>.gz`` sibling."""

    NODE_ID = "bgzip_compress"
    DISPLAY_NAME = "BGZip Compress"
    DESCRIPTION = "Block-gzip (BGZF) a coordinate-sorted VCF, BED, or GFF file"
    SEARCH_ALIASES = [
        "bgzip",
        "bgzf",
        "block gzip",
        "compress",
        "vcf.gz",
        "htslib",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("compressed",)
    OUTPUT_FILENAMES = ("compressed.gz",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bgzip.html"
    UPSTREAM_MANPAGE = "bgzip.1"
    UPSTREAM_SOURCE = "bgzip.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": (
                    "FILE",
                    {
                        "description": (
                            "Uncompressed, coordinate-sorted text file (VCF, BED, or GFF)"
                        )
                    },
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
        value = inputs.get("file")
        if value is None:
            return "Input 'file' must be a non-empty path"
        text = str(value)
        if _looks_compressed(text):
            return (
                "Input 'file' must be an uncompressed text file; bgzip would append "
                "a second compression suffix"
            )
        return True

    @classmethod
    def _staged_input(cls, outputs: list[Path]) -> Path:
        """Return the staged source name whose ``.gz`` sibling is the planned output."""
        planned = str(outputs[0])
        if planned.endswith(".gz"):
            return Path(planned[: -len(".gz")])
        return Path(planned).with_suffix("")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ["bgzip", "-f", str(inputs.get("file", ""))]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged = stage_input(inputs["file"], cls._staged_input(outputs))
        inputs["file"] = str(staged)
