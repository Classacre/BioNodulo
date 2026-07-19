"""Shared metadata for BEDTools 2.31.1 nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


class BEDToolsCommandNode(CommandNode):
    """Common source and environment identity for focused BEDTools operations."""

    CATEGORY = "annotation"
    REQUIRED_EXECUTABLES = ["bedtools"]
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    VERSION = "2.31.1"
    GIT_URL = "https://github.com/arq5x/bedtools2.git"
    GIT_COMMIT = "705ccfdf2c9a77d71560c8adcece0663c2f5e18e"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]
