"""Shared Minimap2 2.30 metadata and validation helpers."""

from __future__ import annotations

import os
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


MINIMAP2_PRESETS = (
    "map-ont",
    "lr:hq",
    "map-hifi",
    "map-pb",
    "map-iclr",
    "asm5",
    "asm10",
    "asm20",
    "splice",
    "splice:hq",
    "splice:sr",
    "sr",
    "ava-pb",
    "ava-ont",
)


def path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


class Minimap2CommandNode(CommandNode):
    CATEGORY = "alignment"
    REQUIRED_CONDA_PACKAGES = ["minimap2"]
    REQUIRED_EXECUTABLES = ["minimap2"]
    VERSION = "2.30"
    GIT_URL = "https://github.com/lh3/minimap2.git"
    GIT_COMMIT = "79c9cc186b95f50bd899f69b48eba995ced810c6"
    DOCUMENTATION_URL = (
        "https://github.com/lh3/minimap2/blob/"
        f"{GIT_COMMIT}/README.md"
    )
    CITATION_DOIS = ["10.1093/bioinformatics/bty191"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/bty191"]
    CITATION_TEXT = "Minimap2: pairwise alignment for nucleotide sequences."
    SHELL = False
    UPSTREAM_SOURCE: ClassVar[str] = ""

    @staticmethod
    def validate_threads(inputs: dict[str, Any]) -> bool | str:
        threads = inputs.get("threads", 8)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"
        return True

    @staticmethod
    def validate_preset(inputs: dict[str, Any], default: str) -> bool | str:
        preset = str(inputs.get("preset", default) or default)
        if preset not in MINIMAP2_PRESETS:
            return f"preset must be one of: {', '.join(MINIMAP2_PRESETS)}"
        return True


__all__ = ["MINIMAP2_PRESETS", "Minimap2CommandNode", "path_value"]
