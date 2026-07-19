"""Shared metadata and validation helpers for MACS2 2.2.9.1 nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class MACS2CommandNode(CommandNode):
    """Common source and environment identity for focused MACS2 operations."""

    CATEGORY = "chip_seq"
    REQUIRED_EXECUTABLES = ["macs2"]
    REQUIRED_CONDA_PACKAGES = ["macs2"]
    VERSION = "2.2.9.1"
    GIT_URL = "https://github.com/macs3-project/MACS.git"
    GIT_COMMIT = "1afcae6a09ced8cf9bb1e87c44dd58f7d7e4891c"
    CITATION_DOIS = ["10.1186/gb-2008-9-9-r137"]
    CITATION_URLS = ["https://doi.org/10.1186/gb-2008-9-9-r137"]
    CITATION_TEXT = "Model-based Analysis of ChIP-Seq (MACS)."
    SHELL = False

    UPSTREAM_PARSER = "bin/macs2"
    UPSTREAM_SOURCE = ""

    @staticmethod
    def safe_output_stem(value: Any, default: str) -> str:
        """Return a predictable MACS2 filename stem without path components."""
        stem = "_".join(str(value or "").strip().split())
        stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
        stem = stem.strip("._-")
        return stem or default

    @staticmethod
    def require_path(inputs: dict[str, Any], key: str) -> bool | str:
        """Validate path-like CLI inputs without requiring local materialization."""
        try:
            path = os.fsdecode(os.fspath(inputs.get(key)))
        except TypeError:
            return f"Input '{key}' must be a non-empty path-like value"
        if not path.strip():
            return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))
