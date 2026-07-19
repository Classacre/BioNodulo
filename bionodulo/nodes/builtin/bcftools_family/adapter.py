"""Shared BCFtools 1.24 metadata, output, and sidecar validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


BCFTOOLS_GIT_COMMIT = "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"


def as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def path_value(inputs: dict[str, Any], key: str, *aliases: str) -> str:
    for name in (key, *aliases):
        value = inputs.get(name)
        if value not in (None, ""):
            try:
                return os.fsdecode(os.fspath(value))
            except TypeError:
                return ""
    return ""


def require_path(inputs: dict[str, Any], key: str, *aliases: str) -> bool | str:
    if not path_value(inputs, key, *aliases).strip():
        return f"Input '{key}' must be a non-empty path-like value"
    return True


def require_paths(inputs: dict[str, Any], key: str, *, minimum: int = 1) -> bool | str:
    values = as_list(inputs.get(key))
    if len(values) < minimum or any(not value.strip() for value in values):
        return f"Input '{key}' requires at least {minimum} non-empty path value(s)"
    return True


def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    selected = str(value)
    if selected not in choices:
        return f"{key} must be one of: {', '.join(choices)}"
    return True


def validate_number(
    value: Any,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> bool | str:
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected):
        return f"{key} must be {'an integer' if integer else 'a number'}"
    number = float(value)
    if minimum is not None and number < minimum:
        return f"{key} must be at least {minimum:g}"
    if maximum is not None and number > maximum:
        return f"{key} must be at most {maximum:g}"
    return True


def add_value(command: list[str], flag: str, value: Any) -> None:
    if value not in (None, ""):
        command.extend([flag, str(value)])


def add_flag(command: list[str], flag: str, enabled: Any) -> None:
    if enabled:
        command.append(flag)


def add_common_filters(
    command: list[str],
    inputs: dict[str, Any],
    *,
    samples: bool = False,
    regions: bool = True,
    targets: bool = True,
) -> None:
    add_value(command, "--include", inputs.get("include"))
    add_value(command, "--exclude", inputs.get("exclude"))
    if samples:
        add_value(command, "--samples", inputs.get("samples"))
        add_value(command, "--samples-file", inputs.get("samples_file"))
    if regions:
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--regions-overlap", inputs.get("regions_overlap"))
    if targets:
        add_value(command, "--targets", inputs.get("targets"))
        add_value(command, "--targets-file", inputs.get("targets_file"))
        add_value(command, "--targets-overlap", inputs.get("targets_overlap"))


def validate_exclusive(inputs: dict[str, Any], left: str, right: str) -> bool | str:
    if inputs.get(left) not in (None, "") and inputs.get(right) not in (None, ""):
        return f"{left} and {right} are mutually exclusive"
    return True


def uses_regions(inputs: dict[str, Any]) -> bool:
    return bool(inputs.get("regions") or inputs.get("regions_file"))


def _absolute(value: Any, *, key: str) -> Path | str:
    try:
        decoded = os.fsdecode(os.fspath(value))
    except TypeError:
        return f"Input '{key}' must be a non-empty path-like value"
    if not decoded.strip():
        return f"Input '{key}' must be a non-empty path-like value"
    return Path(os.path.abspath(os.path.normpath(decoded)))


def validate_reference_index(
    inputs: dict[str, Any],
    *,
    reference_key: str = "reference",
    index_key: str = "reference_index",
) -> bool | str:
    reference = _absolute(inputs.get(reference_key), key=reference_key)
    if isinstance(reference, str):
        return reference
    index = _absolute(inputs.get(index_key), key=index_key)
    expected = Path(f"{reference}.fai")
    if isinstance(index, str):
        return f"{index}; expected '{expected}' for input '{reference_key}'"
    if index != expected:
        return f"Input '{index_key}' must be the exact colocated index for input '{reference_key}'; expected '{expected}'"
    return True


def validate_data_index(
    inputs: dict[str, Any],
    *,
    data_key: str = "input_file",
    index_key: str = "input_index",
    alignment: bool = False,
) -> bool | str:
    data = _absolute(inputs.get(data_key), key=data_key)
    if isinstance(data, str):
        return data
    index = _absolute(inputs.get(index_key), key=index_key)
    if isinstance(index, str):
        return index
    suffix = data.suffix.lower()
    expected = {Path(f"{data}.csi"), Path(f"{data}.tbi")}
    if suffix == ".bcf":
        expected = {Path(f"{data}.csi")}
    if alignment:
        expected = {Path(f"{data}.bai"), Path(f"{data}.csi")}
        if suffix == ".cram":
            expected = {Path(f"{data}.crai")}
    if index not in expected:
        rendered = ", ".join(str(path) for path in sorted(expected, key=str))
        return f"Input '{index_key}' must be a colocated index for input '{data_key}'; expected one of: {rendered}"
    return True


def validate_data_indexes(
    inputs: dict[str, Any],
    *,
    data_key: str,
    index_key: str,
    alignment: bool = False,
) -> bool | str:
    data_values = as_list(inputs.get(data_key))
    index_values = as_list(inputs.get(index_key))
    if len(index_values) != len(data_values):
        return f"Input '{index_key}' must contain one index for each '{data_key}' value"
    for data, index in zip(data_values, index_values, strict=True):
        validation = validate_data_index(
            {"data": data, "index": index},
            data_key="data",
            index_key="index",
            alignment=alignment,
        )
        if validation is not True:
            return str(validation).replace("'data'", f"'{data_key}'").replace("'index'", f"'{index_key}'")
    return True


COMMON_FILTER_INPUTS: dict[str, tuple[str, dict[str, Any]]] = {
    "include": ("STRING", {"default": "", "description": "Include-expression filter"}),
    "exclude": ("STRING", {"default": "", "description": "Exclude-expression filter"}),
    "regions": ("STRING", {"default": "", "description": "Comma-separated random-access regions"}),
    "regions_file": ("FILE", {"default": "", "description": "Random-access regions file"}),
    "regions_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2", "pos", "record", "variant"]}),
    "targets": ("STRING", {"default": "", "description": "Streaming targets"}),
    "targets_file": ("FILE", {"default": "", "description": "Streaming targets file"}),
    "targets_overlap": ("STRING", {"default": "", "options": ["", "0", "1", "2", "pos", "record", "variant"]}),
    "input_index": ("VCF_INDEX", {"default": "", "description": "Colocated TBI or CSI used for random access"}),
}


def common_input_types(*, input_type: str = "VCF") -> dict[str, dict[str, Any]]:
    return {
        "required": {"input_file": (input_type, {"description": "Input VCF or BCF"})},
        "optional": dict(COMMON_FILTER_INPUTS),
        "hidden": {"output": ("STRING", {})},
    }


class BCFtoolsCommandNode(CommandNode):
    """Pinned source and environment identity shared by the focused family."""

    CATEGORY = "variant"
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ["bcftools", "htslib"]
    VERSION = "1.24"
    GIT_URL = "https://github.com/samtools/bcftools.git"
    GIT_COMMIT = BCFTOOLS_GIT_COMMIT
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html"
    CITATION_DOIS = ["10.1093/gigascience/giab008", "10.1093/bioinformatics/btp352"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools."
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools"]
    SHELL = False

    UPSTREAM_DOC = "doc/bcftools.txt"
    UPSTREAM_SOURCE = ""
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))

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
        return validate_exclusive(inputs, "include", "exclude")


class FixedVcfOutputNode(BCFtoolsCommandNode):
    """BCFtools transform with a fixed compressed-VCF artifact."""

    RETURN_TYPES = ("VCF_GZ",)
    OUTPUT_FILENAME: ClassVar[str] = "output.vcf.gz"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / cls.OUTPUT_FILENAME]

    @classmethod
    def output_path(cls, inputs: dict[str, Any]) -> Path:
        return cls.output_dir(inputs) / cls.OUTPUT_FILENAME


def add_fixed_vcf_output(command: list[str], node: type[FixedVcfOutputNode], inputs: dict[str, Any]) -> None:
    command.extend(["-Oz", "-o", str(node.output_path(inputs))])


def add_plugin_separator(command: list[str], plugin_arguments: list[str]) -> None:
    if plugin_arguments:
        command.append("--")
        command.extend(plugin_arguments)


def add_plugin_output(command: list[str], node: type[FixedVcfOutputNode], inputs: dict[str, Any]) -> None:
    add_fixed_vcf_output(command, node, inputs)
