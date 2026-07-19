"""Shared validation and R-script helpers for focused metabolomics nodes."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


def path_value(value: Any) -> str:
    """Return a direct path value without applying shell quoting."""
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return os.path.expanduser(result.strip()) if result.strip() else ""


def split_paths(value: Any) -> list[str]:
    """Normalize a file-list input accepted as a sequence, CSV, or lines."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [path for item in value if (path := path_value(item))]
    return [part.strip() for part in re.split(r"[\n,]+", str(value)) if part.strip()]


def safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


def r_string(value: Any) -> str:
    text = str(value or "")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def r_string_vector(values: Iterable[str]) -> str:
    return "c(" + ", ".join(r_string(value) for value in values) + ")"


def validate_number(
    value: Any,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        kind = "an integer" if integer else "a number"
        return f"Input '{key}' must be {kind}"
    if integer and not isinstance(value, int):
        return f"Input '{key}' must be an integer"
    if minimum is not None and value < minimum:
        return f"Input '{key}' must be at least {minimum:g}"
    if maximum is not None and value > maximum:
        return f"Input '{key}' must be at most {maximum:g}"
    return True


def validate_choice(value: Any, key: str, choices: Iterable[str]) -> bool | str:
    allowed = tuple(choices)
    if str(value) not in allowed:
        return f"Input '{key}' must be one of: {', '.join(allowed)}"
    return True


class MetabolomicsCommandNode(CommandNode):
    """Common direct-argv contract for R-backed metabolomics operations."""

    CATEGORY = "metabolomics"
    SEARCH_ALIASES = ["BioNodulo builtin", "metabolomics"]
    SHELL = False
    OUTPUT_SUFFIXES: ClassVar[tuple[str, ...]] = ()
    CONDA_PACKAGE_CONSTRAINTS: ClassVar[Mapping[str, str]] = {}
    UPSTREAM_SOURCE = ""
    EXIT_SEMANTICS = "A non-zero Rscript exit is fatal; every planned artifact must exist."

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        return safe_output_stem(inputs.get("output_name"), fallback)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        stem = cls.output_stem(inputs, cls.NODE_ID)
        return [node_dir / f"{stem}{suffix}" for suffix in cls.OUTPUT_SUFFIXES]

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
