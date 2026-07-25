"""Narrow shared validation and source metadata for CRISPR command nodes."""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar, Mapping

from bionodulo.nodes.command_node import CommandNode


CAS_OFFINDER_COMMIT = "9816b94c20c4cba2e79b039e1e2a6dee684b7b66"
CRISPRESSO2_COMMIT = "1fc4b629e5400a48d6569b0ab4b8d1766f33636f"
MAGECK_COMMIT = "c491c3874dca39245d51394e83648dfd66820110"
GUIDE_DESIGN_BASELINE_COMMIT = "350d0f9c7de49f53741be365650f330cf5eeff24"
GUIDE_DESIGN_SOURCE_BLOB = "820459a802dd92a9c3e16970b43c66c7566eb8c2"

IUPAC_DNA = frozenset("ACGTRYSWKMBDHVN")
CRISPRESSO_DNA = frozenset("ACGTN")


def path_value(value: Any) -> str:
    """Return a non-empty filesystem value without requiring local existence."""

    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def path_list(value: Any) -> list[str]:
    """Normalize one path or an iterable of paths into separate argv values."""

    if value in (None, ""):
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        values: Iterable[Any] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        return []
    result = [path_value(item) for item in values]
    return result if result and all(result) else []


def mageck_read_paths(value: Any) -> list[str]:
    """Expand MAGeCK sample arguments into their materialized file members."""

    members: list[str] = []
    for sample in path_list(value):
        replicates = sample.split(",")
        if any(not replicate.strip() for replicate in replicates):
            return []
        members.extend(replicates)
    return members


def require_materialized_file(value: Any, key: str, *, allow_empty: bool = False) -> Path:
    """Require one worker-local regular file immediately before execution."""

    path = Path(path_value(value))
    try:
        if not path.is_file():
            raise ValueError(f"Input '{key}' is not a materialized file: {path}")
        if not allow_empty and path.stat().st_size == 0:
            raise ValueError(f"Input '{key}' is empty: {path}")
    except OSError as exc:
        raise ValueError(f"Input '{key}' cannot be inspected: {path}: {exc}") from exc
    return path


def require_materialized_sequence_source(value: Any, key: str) -> Path:
    """Require Cas-OFFinder's worker-local sequence file or direct-file directory."""

    path = Path(path_value(value))
    try:
        if path.is_file() and path.stat().st_size > 0:
            return path
        if path.is_dir() and any(child.is_file() and child.stat().st_size > 0 for child in path.iterdir()):
            return path
    except OSError as exc:
        raise ValueError(f"Input '{key}' cannot be inspected: {path}: {exc}") from exc
    raise ValueError(
        f"Input '{key}' must be a materialized non-empty sequence file or a directory "
        f"containing a non-empty direct file: {path}"
    )


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


def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    selected = str(value)
    if selected not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True


def validate_output_prefix(value: Any, key: str = "output_prefix") -> bool | str:
    prefix = str(value)
    if not prefix.strip():
        return f"Input '{key}' must be non-empty"
    if Path(prefix).name != prefix or prefix in {".", ".."}:
        return f"Input '{key}' must be a filename prefix, not a path"
    return True


def validate_iupac_sequence(
    value: Any,
    key: str,
    *,
    alphabet: frozenset[str] = IUPAC_DNA,
    comma_separated: bool = False,
) -> bool | str:
    sequence = str(value).upper()
    parts = sequence.split(",") if comma_separated else [sequence]
    if not parts or any(not part for part in parts):
        return f"Input '{key}' must be a non-empty DNA sequence"
    invalid = sorted({base for part in parts for base in part if base not in alphabet})
    if invalid:
        return f"Input '{key}' contains unsupported DNA symbols: {''.join(invalid)}"
    return True


def validate_integer_csv(value: Any, key: str, *, minimum: int | None = None) -> bool | str:
    parts = str(value).split(",")
    if not parts or any(not part for part in parts):
        return f"Input '{key}' must contain one or more comma-separated integers"
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return f"Input '{key}' must contain one or more comma-separated integers"
    if minimum is not None and any(number < minimum for number in numbers):
        return f"Input '{key}' values must be at least {minimum}"
    return True


def crispresso_slugify(value: str) -> str:
    """Match CRISPResso2 2.3.4's output-name normalization."""

    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore")
    normalized = re.sub(rb"[\s'*\"/\\\[\]:;|,<>?]", b"_", normalized).strip()
    normalized = re.sub(rb"_{2,}", b"_", normalized)
    return normalized.decode("ascii")


def crispresso_run_name(inputs: Mapping[str, Any]) -> str:
    name = str(inputs.get("name", "") or "")
    if name:
        return crispresso_slugify(name)
    r1_name = Path(path_value(inputs.get("r1"))).name
    r1_name = r1_name.replace(".fastq", "").replace(".gz", "").replace(".fq", "")
    r2 = path_value(inputs.get("r2"))
    if not r2:
        return r1_name
    r2_name = Path(r2).name.replace(".fastq", "").replace(".gz", "").replace(".fq", "")
    return f"{r1_name}_{r2_name}"


class CrisprCommandNode(CommandNode):
    """Common deterministic output planning for source-pinned CRISPR tools."""

    CATEGORY = "crispr"
    SEARCH_ALIASES = ["BioNodulo builtin", "CRISPR"]
    SHELL = False

    CONDA_PACKAGE_CONSTRAINTS: ClassVar[Mapping[str, str]] = {}
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_LIST_INPUTS: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""
    EXIT_SEMANTICS = "Exit code 0 is success; any non-zero code fails the node."

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
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        for key in cls.REQUIRED_PATH_LIST_INPUTS:
            if not path_list(inputs.get(key)):
                return f"Input '{key}' must contain at least one non-empty path-like value"
        return True

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], *prefix: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return list(prefix)


class MageckCommandNode(CrisprCommandNode):
    """Pinned MAGeCK 0.5.9.5 metadata shared by count and test."""

    REQUIRED_EXECUTABLES = ["mageck"]
    REQUIRED_CONDA_PACKAGES = ["mageck"]
    CONDA_PACKAGE_CONSTRAINTS = {"mageck": "0.5.9.5"}
    VERSION = "0.5.9.5"
    GIT_URL = "https://bitbucket.org/liulab/mageck.git"
    GIT_COMMIT = MAGECK_COMMIT
    DOCUMENTATION_URL = "https://sourceforge.net/p/mageck/wiki/Home/"
    CITATION_DOIS = ["10.1186/s13059-014-0554-4"]
    CITATION_URLS = ["https://doi.org/10.1186/s13059-014-0554-4"]
    CITATION_TEXT = "MAGeCK enables robust identification of essential genes from genome-scale CRISPR screens."
    SEARCH_ALIASES = ["BioNodulo builtin", "CRISPR", "MAGeCK", "pooled screen"]
    UPSTREAM_ARGUMENT_SOURCE = "mageck/argsParser.py"
    EXIT_SEMANTICS = "MAGeCK returns 0 on success and -1/non-zero for invalid inputs or failed analysis."
