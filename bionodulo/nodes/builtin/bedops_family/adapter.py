"""Shared source-pinned contract for BEDOPS sort-bed."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._wrapped_tool_utils import (
    BEDOPS_CITATION_DOI,
    BEDOPS_CITATION_TEXT,
    BIONODULO_BUILTIN_ALIAS,
    DOI_URL,
)
from bionodulo.nodes.command_node import CommandNode


class BEDOPSSortBedBase(CommandNode):
    """BEDOPS 2.4.42 sort-bed contract shared by stable compatibility IDs."""

    CATEGORY = "genomics"
    DESCRIPTION = (
        "Sort one or more BED files into BEDOPS canonical order, optionally "
        "emitting only unique or duplicate records."
    )
    REQUIRED_CONDA_PACKAGES = ["bedops"]
    REQUIRED_EXECUTABLES = ["sort-bed"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("sorted_bed",)
    VERSION = "2.4.42"
    GIT_URL = "https://github.com/bedops/bedops.git"
    GIT_COMMIT = "51d2adac6a3aaae73268cf07d0c4127387d335fa"
    DOCUMENTATION_URL = (
        "https://bedops.readthedocs.io/en/latest/content/reference/"
        "file-management/sorting/sort-bed.html"
    )
    SOURCE_URL = (
        "https://github.com/bedops/bedops/blob/"
        f"{GIT_COMMIT}/docs/content/reference/file-management/sorting/sort-bed.rst"
    )
    UPSTREAM_SOURCE = "applications/bed/sort-bed/src/Sort.cpp"
    CITATION_DOIS = [BEDOPS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDOPS_CITATION_DOI}"]
    CITATION_TEXT = BEDOPS_CITATION_TEXT
    SHELL = False
    STDOUT_OUTPUT_INDEX = 0

    @staticmethod
    def _paths(value: Any) -> list[str]:
        if value is None:
            return []
        values: Iterable[Any]
        if isinstance(value, (str, bytes, os.PathLike)):
            values = (value,)
        elif isinstance(value, Iterable):
            values = value
        else:
            return []
        paths: list[str] = []
        for item in values:
            try:
                path = os.fsdecode(os.fspath(item))
            except TypeError:
                return []
            if not path.strip():
                return []
            paths.append(path)
        return paths

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "sort-bed",
            "--max-mem",
            f"{int(inputs.get('memory_mb', 1024))}M",
            "--tmpdir",
            os.fsdecode(os.fspath(inputs.get("tmpdir") or ".")),
        ]
        if inputs.get("unique"):
            command.append("--unique")
        elif inputs.get("duplicates"):
            command.append("--duplicates")
        return [*command, *cls._paths(inputs.get("inputs"))]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "sorted.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not cls._paths(inputs.get("inputs")):
            return "at least one BED input is required"
        if inputs.get("unique") and inputs.get("duplicates"):
            return "unique and duplicates modes are mutually exclusive"
        memory_mb = inputs.get("memory_mb", 1024)
        if isinstance(memory_mb, bool) or not isinstance(memory_mb, int) or memory_mb < 1:
            return "memory_mb must be a positive integer"
        try:
            tmpdir = os.fsdecode(os.fspath(inputs.get("tmpdir") or "."))
        except TypeError:
            return "tmpdir must be a non-empty path-like value"
        if not tmpdir.strip():
            return "tmpdir must be a non-empty path-like value"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"inputs": ("BED_LIST", {"description": "One or more BED files to sort"})},
            "optional": {
                "unique": ("BOOLEAN", {"default": False}),
                "duplicates": ("BOOLEAN", {"default": False}),
                "memory_mb": ("INT", {"default": 1024, "min": 1}),
                "tmpdir": ("DIRECTORY", {"default": ".", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


COMMON_SEARCH_ALIASES = [
    BIONODULO_BUILTIN_ALIAS,
    "bedops",
    "sort-bed",
    "BEDOPS sort-bed",
    "sort BED",
    "unique BED",
    "duplicate BED",
]
