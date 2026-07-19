"""Shared metadata and argument helpers for deepTools 3.5.6 nodes."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


class DeepToolsCommandNode(CommandNode):
    """Common source and environment identity for focused deepTools operations."""

    CATEGORY = "epigenomics"
    REQUIRED_CONDA_PACKAGES = ["deeptools"]
    VERSION = "3.5.6"
    GIT_URL = "https://github.com/deeptools/deepTools.git"
    GIT_COMMIT = "ea0f68bb4a1587d713dacb3791861308751ef7d0"
    CITATION_DOIS = ["10.1093/nar/gkw257"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkw257"]
    CITATION_TEXT = "deepTools2: a next generation web server for deep-sequencing data analysis."
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @staticmethod
    def require_path(inputs: dict[str, Any], key: str) -> bool | str:
        try:
            path = os.fsdecode(os.fspath(inputs.get(key)))
        except TypeError:
            return f"Input '{key}' must be a non-empty path-like value"
        if not path.strip():
            return f"Input '{key}' must be a non-empty path-like value"
        return True

    @staticmethod
    def split_cli_values(value: Any) -> list[str]:
        """Convert a UI multi-value field into distinct subprocess arguments."""
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if str(item).strip()]
        return shlex.split(str(value))

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))
