"""HTSlib ``tabix`` region-query node."""

from __future__ import annotations

from typing import Any

from .adapter import HtslibTabixBase, _REGION_RE, _looks_compressed


class TabixQueryNode(HtslibTabixBase):
    """Extract records overlapping one genomic region from a tabix-indexed file."""

    NODE_ID = "tabix_query"
    DISPLAY_NAME = "Tabix Query"
    DESCRIPTION = (
        "Extract records overlapping a genomic region from a tabix-indexed BGZF file"
    )
    SEARCH_ALIASES = [
        "tabix",
        "query",
        "region",
        "extract",
        "interval",
        "htslib",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("records",)
    OUTPUT_FILENAMES = ("records.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://www.htslib.org/doc/tabix.html"
    UPSTREAM_MANPAGE = "tabix.1"
    UPSTREAM_SOURCE = "tabix.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bgzf": (
                    "FILE",
                    {"description": "Bgzipped file with a colocated .tbi index"},
                ),
                "region": (
                    "STRING",
                    {
                        "description": (
                            "Region such as chr1:100-200 (1-based, inclusive); "
                            "chr1 or chr1:100 are also accepted"
                        )
                    },
                ),
            },
            "optional": {
                "print_header": (
                    "BOOLEAN",
                    {"default": False, "description": "Prepend the file header lines (-h)"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        value = inputs.get("bgzf")
        if value is None:
            return "Input 'bgzf' must be a non-empty path"
        if not _looks_compressed(str(value)):
            return (
                "Input 'bgzf' must be a bgzipped file ending in .gz, .bgz, or .bgzf"
            )
        region = inputs.get("region")
        if region is None or not str(region).strip():
            return "Input 'region' must be a non-empty region string"
        if _REGION_RE.fullmatch(str(region)) is None:
            return (
                "Input 'region' must be a contig or contig:start[-end] such as "
                "chr1, chr1:100, or chr1:100-200"
            )
        header = inputs.get("print_header", False)
        if not isinstance(header, bool):
            return "Input 'print_header' must be a boolean"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["tabix"]
        if inputs.get("print_header", False):
            command.append("-h")
        command.extend([str(inputs.get("bgzf", "")), str(inputs.get("region", ""))])
        return command
