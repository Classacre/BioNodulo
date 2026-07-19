"""Shared validation and pinned source metadata for BAM/CRAM utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


GALAXY_ALIAS = "BioNodulo builtin"
CRAMINO_CITATION_DOI = "10.1093/bioinformatics/btad311"
CRAMINO_CITATION_TEXT = "NanoPack2: population-scale evaluation of long-read sequencing data."
BAMUTIL_CITATION_DOI = "10.1101/gr.176552.114"
BAMUTIL_CITATION_TEXT = "GotCloud: a sequence analysis pipeline for high-quality variant calls."


def path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def output_dir(inputs: dict[str, Any]) -> Path:
    return Path(str(inputs.get("output", inputs.get("output_dir", "."))))


class CraminoCommandNode(CommandNode):
    REQUIRED_CONDA_PACKAGES = ["cramino"]
    REQUIRED_EXECUTABLES = ["cramino"]
    VERSION = "1.3.0"
    GIT_URL = "https://github.com/wdecoster/cramino.git"
    GIT_COMMIT = "f073ae7e436acbe7157847f1a83d0087063d3131"
    DOCUMENTATION_URL = "https://github.com/wdecoster/cramino"
    SOURCE_URL = f"https://github.com/wdecoster/cramino/blob/{GIT_COMMIT}/src/main.rs"
    UPSTREAM_SOURCE = "src/main.rs"
    CONDA_PACKAGE_CONSTRAINTS = {"cramino": VERSION}
    CITATION_DOIS = [CRAMINO_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{CRAMINO_CITATION_DOI}"]
    CITATION_TEXT = CRAMINO_CITATION_TEXT
    SHELL = False


class BamUtilCommandNode(CommandNode):
    REQUIRED_CONDA_PACKAGES = ["bamutil"]
    REQUIRED_EXECUTABLES = ["bam"]
    VERSION = "1.0.15"
    GIT_URL = "https://github.com/statgen/bamUtil.git"
    GIT_COMMIT = "3ad3980a3a3a3fc35eca3636b7206676c8303ce6"
    CONDA_PACKAGE_CONSTRAINTS = {"bamutil": VERSION}
    CITATION_DOIS = [BAMUTIL_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{BAMUTIL_CITATION_DOI}"]
    CITATION_TEXT = BAMUTIL_CITATION_TEXT
    SHELL = False

    @staticmethod
    def add_value(command: list[str], flag: str, value: Any) -> None:
        if value not in (None, ""):
            command.extend([flag, str(value)])


__all__ = [
    "BAMUTIL_CITATION_DOI",
    "BAMUTIL_CITATION_TEXT",
    "CRAMINO_CITATION_DOI",
    "CRAMINO_CITATION_TEXT",
    "BamUtilCommandNode",
    "CraminoCommandNode",
    "GALAXY_ALIAS",
    "output_dir",
    "path_value",
]
