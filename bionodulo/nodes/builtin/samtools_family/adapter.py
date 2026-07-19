"""Shared runtime contract for the first-wave Samtools nodes."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


GALAXY_ALIAS = "BioNodulo builtin"
SAMTOOLS_VERSION = "1.23.1"
SAMTOOLS_GIT_URL = "https://github.com/samtools/samtools.git"
SAMTOOLS_GIT_COMMIT = "6efb9b6da35224cf804921dedecf9fb8f411365d"
TOOLS_IUC_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
SAMTOOLS_CITATION_DOIS = [
    "10.1093/gigascience/giab008",
    "10.1093/bioinformatics/btp352",
]
SAMTOOLS_CITATION_URLS = [f"https://doi.org/{doi}" for doi in SAMTOOLS_CITATION_DOIS]
SAMTOOLS_CITATION_TEXT = "Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools."
SAMTOOLS_GALAXY_CITATION_DOIS = [
    "10.1093/gigascience/giab008",
    "10.1093/bioinformatics/btr076",
]
SAMTOOLS_GALAXY_CITATION_URLS = [f"https://doi.org/{doi}" for doi in SAMTOOLS_GALAXY_CITATION_DOIS]
SAMTOOLS_GALAXY_CITATION_TEXT = (
    "Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality."
)


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _as_csv_list(value: Any) -> list[str]:
    """Normalize repeated values while accepting comma-separated UI strings."""
    values: list[str] = []
    for item in _as_list(value):
        values.extend(part.strip() for part in item.split(",") if part.strip())
    return values


def _flag_sum(value: Any) -> int:
    total = 0
    for item in _as_list(value):
        for part in item.split(","):
            if part.strip():
                total += int(part.strip())
    return total


def _add_if_value(command: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != "":
        command.extend([flag, str(value)])


def _additional_threads(inputs: dict[str, Any], default: int = 1) -> int:
    return max(int(inputs.get("threads", default) or default) - 1, 0)


def _sort_memory(inputs: dict[str, Any], default_mb: int = 768) -> str:
    memory_mb = int(inputs.get("memory_mb", default_mb) or default_mb)
    return f"{max(memory_mb * 75 // 100, 1)}M"


def validate_path_list(
    inputs: dict[str, Any],
    key: str,
    *,
    minimum: int = 1,
) -> bool | str:
    """Validate one or more path-like values without touching the filesystem."""
    value = inputs.get(key)
    if isinstance(value, (str, os.PathLike)):
        raw_values: Sequence[Any] = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw_values = value
    else:
        return f"Input '{key}' must be a path or sequence of paths"

    if len(raw_values) < minimum:
        return f"Input '{key}' must contain at least {minimum} path(s)"
    for item in raw_values:
        try:
            path = os.fsdecode(os.fspath(item))
        except TypeError:
            return f"Input '{key}' must contain only path-like values"
        if not path.strip():
            return f"Input '{key}' must contain only non-empty paths"
    return True


def validate_index_pairs(
    inputs: dict[str, Any],
    *,
    data_key: str,
    index_key: str,
    required: bool,
    colocated_suffix: str | None = None,
) -> bool | str:
    """Validate explicit one-to-one data/index lists and optional colocation."""
    data_validation = validate_path_list(inputs, data_key)
    if data_validation is not True:
        return data_validation

    index_value = inputs.get(index_key)
    if index_value in (None, "", []):
        if required:
            return f"Input '{index_key}' is required for '{data_key}'"
        return True
    index_validation = validate_path_list(inputs, index_key)
    if index_validation is not True:
        return index_validation

    data_paths = _as_list(inputs[data_key])
    index_paths = _as_list(index_value)
    if len(data_paths) != len(index_paths):
        return f"Input '{index_key}' must contain one index for each path in '{data_key}'"
    if colocated_suffix is None:
        return True

    for data_path, index_path in zip(data_paths, index_paths, strict=True):
        expected = Path(os.path.abspath(os.path.normpath(f"{data_path}{colocated_suffix}")))
        actual = Path(os.path.abspath(os.path.normpath(index_path)))
        if actual != expected:
            return f"Input '{index_key}' must contain exact colocated indexes; expected '{expected}' for '{data_path}'"
    return True


class SamtoolsCommandNode(CommandNode):
    """Small adapter for metadata, output planning, and common validation."""

    CATEGORY = "samtools"
    REQUIRED_EXECUTABLES = ["samtools"]
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    VERSION = SAMTOOLS_VERSION
    GIT_URL = SAMTOOLS_GIT_URL
    GIT_COMMIT = SAMTOOLS_GIT_COMMIT
    RUNTIME_VERSION = SAMTOOLS_VERSION
    RUNTIME_GIT_URL = SAMTOOLS_GIT_URL
    RUNTIME_GIT_COMMIT = SAMTOOLS_GIT_COMMIT
    CITATION_DOIS = [
        "10.1093/gigascience/giab008",
        "10.1093/bioinformatics/btp352",
    ]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools."
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_MANPAGE: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_types = cls.INPUT_TYPES()
        normalized_inputs = dict(inputs)
        for name in input_types.get("optional", {}):
            if normalized_inputs.get(name) == "":
                normalized_inputs.pop(name)
        base_validation = super().VALIDATE_INPUTS(normalized_inputs)
        if base_validation is not True:
            return base_validation

        path_types = {
            "BAI",
            "BAM",
            "BED",
            "CRAM",
            "FASTA",
            "FASTA_INDEX",
            "FILE",
            "SAM",
        }
        for category in ("required", "optional"):
            for name, spec in input_types.get(category, {}).items():
                declared_type = spec[0] if isinstance(spec, (list, tuple)) else spec
                metadata = spec[1] if isinstance(spec, tuple) and len(spec) > 1 else {}
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared_types = (declared_type,) if isinstance(declared_type, str) else tuple(declared_type)

                if set(declared_types).intersection(path_types):
                    if not isinstance(value, (str, os.PathLike)):
                        return f"Input '{name}' must be a path-like value"
                    path_value = os.fsdecode(os.fspath(value))
                    if not path_value.strip():
                        return f"Input '{name}' must be a non-empty path"

                if declared_type in {"BAM_LIST", "FILE_LIST"}:
                    validation = validate_path_list(inputs, name)
                    if validation is not True:
                        return validation

                if declared_type == "INT":
                    if isinstance(value, bool) or not isinstance(value, int):
                        return f"{name} must be an integer"
                    minimum = metadata.get("min")
                    maximum = metadata.get("max")
                    if minimum is not None and value < minimum:
                        if name == "threads" and maximum is not None:
                            return f"threads must be between {minimum} and {maximum}"
                        return f"{name} must be at least {minimum}"
                    if maximum is not None and value > maximum:
                        if name == "threads" and minimum is not None:
                            return f"threads must be between {minimum} and {maximum}"
                        return f"{name} must be at most {maximum}"

                if declared_type == "FLOAT":
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        return f"{name} must be a number"
                    minimum = metadata.get("min")
                    maximum = metadata.get("max")
                    if minimum is not None and value < minimum:
                        return f"{name} must be at least {minimum}"
                    if maximum is not None and value > maximum:
                        return f"{name} must be at most {maximum}"

                options = metadata.get("options")
                if options and declared_type == "STRING" and value not in options:
                    return f"{name} must be one of: {', '.join(map(str, options))}"

                if options and declared_type == "STRING_LIST":
                    values = _as_list(value)
                    invalid = [item for item in values if item not in options]
                    if invalid:
                        return f"{name} contains unsupported value(s): {', '.join(invalid)}"

        for name, spec in input_types.get("required", {}).items():
            declared_type = spec[0] if isinstance(spec, (list, tuple)) else spec
            declared_types = (declared_type,) if isinstance(declared_type, str) else tuple(declared_type)
            if not {"SAM", "BAM"}.intersection(declared_types):
                continue
            value = inputs.get(name)
            if not isinstance(value, (str, os.PathLike)):
                return f"Input '{name}' must be a path-like value"
            path_value = os.fspath(value)
            if not isinstance(path_value, str) or not path_value.strip():
                return f"Input '{name}' must be a non-empty path"

        return True
