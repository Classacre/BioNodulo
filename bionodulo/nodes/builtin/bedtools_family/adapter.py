"""Shared metadata and validation for BEDTools 2.31.1 nodes."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


class BEDToolsCommandNode(CommandNode):
    """Common source and environment identity for focused BEDTools operations."""

    CATEGORY = "genomics"
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
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_LIST_INPUTS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

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
    def require_path(inputs: Mapping[str, Any], key: str) -> bool | str:
        try:
            value = os.fsdecode(os.fspath(inputs.get(key)))
        except TypeError:
            return f"Input '{key}' must be a non-empty path-like value"
        if not value.strip():
            return f"Input '{key}' must be a non-empty path-like value"
        return True

    @staticmethod
    def path_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, os.PathLike)):
            values: Iterable[Any] = (value,)
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
    def require_path_list(cls, inputs: Mapping[str, Any], key: str) -> bool | str:
        paths = cls.path_list(inputs.get(key))
        if not paths:
            return f"Input '{key}' must contain at least one non-empty path-like value"
        return True

    @staticmethod
    def output_dir(inputs: Mapping[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))

    @staticmethod
    def optional_value(command: list[str], flag: str, value: Any) -> None:
        if value not in (None, ""):
            command.extend([flag, str(value)])

    @staticmethod
    def strand_flag(value: Any, *, same: str = "-s", opposite: str = "-S") -> str:
        return {"same": same, "opposite": opposite}.get(str(value or ""), "")

    @staticmethod
    def validate_choice(value: Any, choices: Iterable[str], key: str) -> bool | str:
        normalized = str(value)
        allowed = tuple(choices)
        if normalized not in allowed:
            return f"Input '{key}' must be one of: {', '.join(allowed)}"
        return True

    @staticmethod
    def validate_fraction(value: Any, key: str, *, allow_zero: bool = True) -> bool | str:
        if value in (None, ""):
            return True
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"Input '{key}' must be a number"
        minimum = 0.0 if allow_zero else 0.0
        if float(value) < minimum or float(value) > 1.0 or (not allow_zero and float(value) == 0.0):
            qualifier = "greater than 0 and at most 1" if not allow_zero else "between 0 and 1"
            return f"Input '{key}' must be {qualifier}"
        return True

    @staticmethod
    def validate_int(value: Any, key: str, *, minimum: int | None = None) -> bool | str:
        if value in (None, ""):
            return True
        if isinstance(value, bool) or not isinstance(value, int):
            return f"Input '{key}' must be an integer"
        if minimum is not None and value < minimum:
            return f"Input '{key}' must be at least {minimum}"
        return True

    @classmethod
    def validate_overlap_options(
        cls,
        inputs: Mapping[str, Any],
        *,
        a_key: str = "overlap",
        b_key: str = "overlap_b",
    ) -> bool | str:
        for key in (a_key, b_key):
            validation = cls.validate_fraction(inputs.get(key), key, allow_zero=False)
            if validation is not True:
                return validation
        if inputs.get("reciprocal") and inputs.get(a_key) in (None, ""):
            return f"Input '{a_key}' is required when reciprocal overlap is enabled"
        if inputs.get("either_fraction") and inputs.get(a_key) in (None, ""):
            return f"Input '{a_key}' is required when either-fraction overlap is enabled"
        if inputs.get("reciprocal") and inputs.get("either_fraction"):
            return "reciprocal and either-fraction overlap modes are mutually exclusive"
        return True

    @classmethod
    def add_overlap_options(
        cls,
        command: list[str],
        inputs: Mapping[str, Any],
        *,
        a_key: str = "overlap",
        b_key: str = "overlap_b",
    ) -> None:
        cls.optional_value(command, "-f", inputs.get(a_key))
        cls.optional_value(command, "-F", inputs.get(b_key))
        if inputs.get("reciprocal"):
            command.append("-r")
        elif inputs.get("either_fraction"):
            command.append("-e")

    @staticmethod
    def csv_values(value: Any) -> list[str]:
        if isinstance(value, (list, tuple)):
            raw = [str(item).strip() for item in value]
        else:
            raw = [item.strip() for item in str(value or "").split(",")]
        return [item for item in raw if item]

    @classmethod
    def validate_positive_columns(cls, value: Any, key: str) -> bool | str:
        values = cls.csv_values(value)
        if not values:
            return f"Input '{key}' must contain at least one 1-based column"
        try:
            columns = [int(item) for item in values]
        except ValueError:
            return f"Input '{key}' must contain comma-separated integers"
        if any(column < 1 for column in columns):
            return f"Input '{key}' columns must be positive and 1-based"
        return True

    @classmethod
    def validate_column_operations(
        cls,
        columns: Any,
        operations: Any,
        *,
        columns_key: str = "columns",
        operations_key: str = "operations",
    ) -> bool | str:
        validation = cls.validate_positive_columns(columns, columns_key)
        if validation is not True:
            return validation
        column_values = cls.csv_values(columns)
        operation_values = cls.csv_values(operations)
        if not operation_values:
            return f"Input '{operations_key}' must contain at least one operation"
        if len(operation_values) not in (1, len(column_values)):
            return (
                f"Input '{operations_key}' must contain one operation or exactly "
                f"one per '{columns_key}' column"
            )
        return True

    @classmethod
    def validate_colocated_bam_indexes(
        cls,
        inputs: Mapping[str, Any],
        *,
        bams_key: str = "bams",
        indexes_key: str = "bam_indexes",
    ) -> bool | str:
        bams = cls.path_list(inputs.get(bams_key))
        indexes = cls.path_list(inputs.get(indexes_key))
        if not bams:
            return f"Input '{bams_key}' must contain at least one non-empty path-like value"
        if len(indexes) != len(bams):
            return (
                f"Input '{indexes_key}' must contain exactly one colocated BAI "
                f"for each input in '{bams_key}'"
            )
        for bam, index in zip(bams, indexes, strict=True):
            expected = Path(os.path.abspath(os.path.normpath(f"{bam}.bai")))
            actual = Path(os.path.abspath(os.path.normpath(index)))
            if actual != expected:
                return (
                    f"Input '{indexes_key}' must contain exact <bam>.bai siblings; "
                    f"expected '{expected}' for '{bam}'"
                )
        return True

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], *prefix: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return list(prefix)

    @classmethod
    def stage_writable_fasta(
        cls,
        inputs: dict[str, Any],
        outputs: list[Path],
        *,
        key: str = "fasta",
    ) -> None:
        """Stage FASTA plus existing faidx siblings where BEDTools may create them."""
        if not outputs:
            raise ValueError(f"{cls.NODE_ID} requires a planned output before FASTA staging")
        source = Path(os.fsdecode(os.fspath(inputs[key])))
        suffixes = "".join(source.suffixes)
        staged = outputs[0].parent / f"reference{suffixes or '.fa'}"
        staged.parent.mkdir(parents=True, exist_ok=True)
        cls._replace_with_link_or_copy(source, staged)
        for sidecar_suffix in (".fai", ".gzi"):
            source_sidecar = Path(f"{source}{sidecar_suffix}")
            if source_sidecar.exists():
                cls._replace_with_link_or_copy(
                    source_sidecar,
                    Path(f"{staged}{sidecar_suffix}"),
                )
        inputs[key] = str(staged)

    @staticmethod
    def _replace_with_link_or_copy(source: Path, destination: Path) -> None:
        source_abs = Path(os.path.abspath(os.path.normpath(os.fspath(source))))
        destination_abs = Path(
            os.path.abspath(os.path.normpath(os.fspath(destination)))
        )
        if source_abs == destination_abs:
            return
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)


class BEDToolsStdoutNode(BEDToolsCommandNode):
    """BEDTools operation whose documented primary output is stdout."""

    STDOUT_OUTPUT_INDEX = 0
