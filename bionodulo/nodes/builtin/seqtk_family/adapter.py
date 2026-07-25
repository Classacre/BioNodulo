"""Shared source identity and validation for official Seqtk v1.4."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


class SeqtkCommandNode(CommandNode):
    """Pinned metadata and helpers shared by the focused Seqtk family."""

    CATEGORY = "sequence"
    REQUIRED_EXECUTABLES = ["seqtk"]
    REQUIRED_CONDA_PACKAGES = ["seqtk"]
    VERSION = "1.4"
    GIT_URL = "https://github.com/lh3/seqtk.git"
    GIT_COMMIT = "ae7defa8bead3ef77d241f12194dc66acdd40fca"
    GIT_TAG = "v1.4"
    UPSTREAM_VERSION = "1.4-r122"
    UPSTREAM_SOURCE = "seqtk.c"
    UPSTREAM_SOURCE_SHA256 = "411bbc5882c4f848ff7a0e46c7ea428ea68bf509dec7903cc4337c523326bb1d"
    UPSTREAM_README_SHA256 = "9f08b79d7ee9b1e4f61e212efb8e7235be3c3df5792aa89190cd0d947137a259"
    DOCUMENTATION_URL = "https://github.com/lh3/seqtk/tree/v1.4"
    CITATION_DOIS: list[str] = []
    CITATION_URLS = ["https://github.com/lh3/seqtk"]
    CITATION_TEXT = "Seqtk: a fast and lightweight toolkit for processing FASTA and FASTQ sequences."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "FASTA", "FASTQ"]
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in cls.REQUIRED_PATH_INPUTS:
            validation = cls.require_path(inputs, key)
            if validation is not True:
                return validation
        return True

    @staticmethod
    def path_value(value: Any) -> str:
        try:
            result = os.fsdecode(os.fspath(value))
        except TypeError:
            return ""
        return result if result.strip() else ""

    @classmethod
    def require_path(cls, inputs: Mapping[str, Any], key: str) -> bool | str:
        path = cls.path_value(inputs.get(key))
        if not path:
            return f"Input '{key}' must be a non-empty path-like value"
        if path == "-":
            return f"Input '{key}' must be a file path; this node has no stdin port"
        return True

    @staticmethod
    def output_dir(inputs: Mapping[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], *prefix: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return list(prefix)

    @staticmethod
    def add_value(command: list[str], flag: str, value: Any) -> None:
        if value not in (None, ""):
            command.extend([flag, str(value)])

    @staticmethod
    def validate_int(
        value: Any,
        key: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> bool | str:
        if isinstance(value, bool) or not isinstance(value, int):
            return f"Input '{key}' must be an integer"
        if minimum is not None and value < minimum:
            return f"Input '{key}' must be at least {minimum}"
        if maximum is not None and value > maximum:
            return f"Input '{key}' must be at most {maximum}"
        return True

    @staticmethod
    def validate_number(
        value: Any,
        key: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> bool | str:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"Input '{key}' must be a number"
        number = float(value)
        if minimum is not None and number < minimum:
            return f"Input '{key}' must be at least {minimum:g}"
        if maximum is not None and number > maximum:
            return f"Input '{key}' must be at most {maximum:g}"
        return True

    @staticmethod
    def validate_choice(value: Any, choices: Iterable[str], key: str) -> bool | str:
        allowed = tuple(choices)
        if str(value) not in allowed:
            return f"Input '{key}' must be one of: {', '.join(allowed)}"
        return True

    @staticmethod
    def reject_legacy(inputs: Mapping[str, Any], keys: Iterable[str]) -> bool | str:
        stale = sorted(key for key in keys if key in inputs)
        if stale:
            return f"Legacy Seqtk wrapper inputs are unsupported: {', '.join(stale)}"
        return True

    @classmethod
    def sequence_extension(cls, value: Any) -> str:
        path = Path(cls.path_value(value))
        suffixes = [suffix.lower() for suffix in path.suffixes]
        while suffixes and suffixes[-1] in (".gz", ".bgz", ".bgzf"):
            suffixes.pop()
        suffix = suffixes[-1] if suffixes else ""
        if suffix in (".fa", ".fna", ".fas", ".fasta"):
            return ".fasta"
        if suffix in (".fq", ".fastq"):
            return ".fastq"
        return ".seq"


class SeqtkStdoutNode(SeqtkCommandNode):
    """Seqtk operation whose declared primary artifact is written to stdout."""

    STDOUT_OUTPUT_INDEX = 0
