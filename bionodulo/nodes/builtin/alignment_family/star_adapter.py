"""Shared STAR 2.7.11b source identity and path helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


STAR_INDEX_MARKERS = (
    "Genome",
    "SA",
    "SAindex",
    "chrName.txt",
    "genomeParameters.txt",
)


def path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def read_paths(value: Any) -> list[str]:
    if isinstance(value, (str, bytes, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return []
    paths: list[str] = []
    for item in values:
        path = path_value(item)
        if path is None:
            return []
        paths.append(path)
    return paths


class STARCommandNode(CommandNode):
    CATEGORY = "alignment"
    REQUIRED_CONDA_PACKAGES = ["star"]
    REQUIRED_EXECUTABLES = ["STAR"]
    VERSION = "2.7.11b"
    GIT_URL = "https://github.com/alexdobin/STAR.git"
    GIT_COMMIT = "b1edc1208d91a53bf40ebae8669f71d50b994851"
    DOCUMENTATION_URL = (
        "https://github.com/alexdobin/STAR/blob/"
        f"{GIT_COMMIT}/doc/STARmanual.pdf"
    )
    CITATION_DOIS = ["10.1093/bioinformatics/bts635"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/bts635"]
    CITATION_TEXT = "STAR: ultrafast universal RNA-seq aligner."
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
    def output_dir(inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))


__all__ = ["STAR_INDEX_MARKERS", "STARCommandNode", "path_value", "read_paths"]
