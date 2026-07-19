"""Shared metadata and validation for the RSeQC 5.0.3 sdist."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


class RSeQCCommandNode(CommandNode):
    """Pinned source identity and helpers shared by focused RSeQC scripts."""

    CATEGORY = "rna_seq"
    REQUIRED_CONDA_PACKAGES = ["rseqc"]
    VERSION = "5.0.3"
    GIT_URL = ""
    GIT_COMMIT = ""
    SOURCE_URL = (
        "https://files.pythonhosted.org/packages/8a/a0/"
        "49c6c15dd12c6219ea33d2286ec8ed7b77e793d3e817efab00bfd711dd85/"
        "RSeQC-5.0.3.tar.gz"
    )
    SOURCE_SHA256 = "869f542e08f50c8874280d58e4f5565857b0aebac66a8eceef3f23016175061e"
    DOCUMENTATION_URL = "http://rseqc.sourceforge.net/"
    CITATION_DOIS = ["10.1093/bioinformatics/bts356"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/bts356"]
    CITATION_TEXT = "RSeQC: quality control of RNA-seq experiments."
    SEARCH_ALIASES = ["BioNodulo builtin", "RSeQC", "RNA-seq QC"]
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_LIST_INPUTS: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SCRIPT = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / name for name in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in cls.REQUIRED_PATH_INPUTS:
            validation = cls.require_path(inputs, key)
            if validation is not True:
                return validation
        for key in cls.REQUIRED_PATH_LIST_INPUTS:
            validation = cls.require_path_list(inputs, key)
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
        if not cls.path_value(inputs.get(key)):
            return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def path_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, os.PathLike)):
            values: Iterable[Any] = (value,)
        elif isinstance(value, Iterable):
            values = value
        else:
            return []
        paths = [cls.path_value(item) for item in values]
        return paths if paths and all(paths) else []

    @classmethod
    def require_path_list(cls, inputs: Mapping[str, Any], key: str) -> bool | str:
        if not cls.path_list(inputs.get(key)):
            return f"Input '{key}' must contain at least one non-empty path-like value"
        return True

    @staticmethod
    def output_dir(inputs: Mapping[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))

    @classmethod
    def output_prefix(cls, inputs: Mapping[str, Any], stem: str = "output") -> Path:
        return cls.output_dir(inputs) / stem

    @staticmethod
    def add_value(command: list[str], flag: str, value: Any) -> None:
        if value not in (None, ""):
            command.extend([flag, str(value)])

    @staticmethod
    def validate_choice(value: Any, choices: Iterable[str], key: str) -> bool | str:
        allowed = tuple(choices)
        if str(value) not in allowed:
            return f"Input '{key}' must be one of: {', '.join(allowed)}"
        return True

    @staticmethod
    def validate_int(value: Any, key: str, *, minimum: int | None = None, maximum: int | None = None) -> bool | str:
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

    @classmethod
    def validate_bam_index(
        cls,
        inputs: Mapping[str, Any],
        *,
        bam_key: str = "input",
        index_key: str = "bam_index",
    ) -> bool | str:
        bam = cls.path_value(inputs.get(bam_key))
        index = cls.path_value(inputs.get(index_key))
        if not bam:
            return f"Input '{bam_key}' must be a non-empty path-like value"
        expected = Path(os.path.abspath(os.path.normpath(f"{bam}.bai")))
        if not index:
            return f"Input '{index_key}' must be the exact sibling '{expected}'"
        actual = Path(os.path.abspath(os.path.normpath(index)))
        if actual != expected:
            return f"Input '{index_key}' must be the exact sibling '{expected}'"
        return True

    @classmethod
    def validate_bam_indexes(
        cls,
        inputs: Mapping[str, Any],
        *,
        bams_key: str = "inputs",
        indexes_key: str = "bam_indexes",
    ) -> bool | str:
        bams = cls.path_list(inputs.get(bams_key))
        indexes = cls.path_list(inputs.get(indexes_key))
        if not bams:
            return f"Input '{bams_key}' must contain at least one BAM"
        if len(indexes) != len(bams):
            return f"Input '{indexes_key}' must contain one index for each '{bams_key}' BAM"
        for bam, index in zip(bams, indexes, strict=True):
            validation = cls.validate_bam_index(
                {"bam": bam, "index": index},
                bam_key="bam",
                index_key="index",
            )
            if validation is not True:
                return validation
        return True

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], *prefix: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return list(prefix)
