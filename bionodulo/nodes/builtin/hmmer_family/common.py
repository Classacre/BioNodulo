"""Shared HMMER 3.4 metadata and narrow command helpers."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.taxonomy_family.protein_contracts import (
    ValidatedCommandContract,
)

HMMER_VERSION = "3.4"
HMMER_GIT_URL = "https://github.com/EddyRivasLab/hmmer.git"
HMMER_GIT_COMMIT = "9acd8b6758a0ca5d21db6d167e0277484341929b"
HMMER_TAG_OBJECT = "e0b6aeb0eec19774c7484e690985af0eb0c98fe9"
HMMER_SOURCE_ROOT = f"https://github.com/EddyRivasLab/hmmer/blob/{HMMER_GIT_COMMIT}"
HMMER_CITATION_DOI = "10.1093/nar/gkr367"
HMMER_NUCLEOTIDE_CITATION_DOI = "10.1093/bioinformatics/btt403"
HMMER_PRESSED_SUFFIXES = (".h3f", ".h3i", ".h3m", ".h3p")
EASEL_VERSION = "0.49"
EASEL_GIT_COMMIT = "07ca83ba9ef0414dba9ce0a9331d465b5eb58f2b"
EASEL_TAG_OBJECT = "3986bd3fb3aaff1cead9548bdd5a713d848cb0ee"
EASEL_SOURCE_ROOT = f"https://github.com/EddyRivasLab/easel/blob/{EASEL_GIT_COMMIT}"
HMMER_PROTEIN_MATRICES = (
    "PAM30",
    "PAM70",
    "PAM120",
    "PAM240",
    "BLOSUM45",
    "BLOSUM50",
    "BLOSUM62",
    "BLOSUM80",
    "BLOSUM90",
)

_LINK_FALLBACK_ERRNOS = {errno.EXDEV, errno.EPERM, errno.ENOSYS}
for _errno_name in ("ENOTSUP", "EOPNOTSUPP"):
    _errno_value = getattr(errno, _errno_name, None)
    if _errno_value is not None:
        _LINK_FALLBACK_ERRNOS.add(_errno_value)


def output_dir(inputs: dict[str, Any]) -> str:
    return str(inputs.get("output", inputs.get("output_dir", ".")))


def add_value(command: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != "":
        command.extend([flag, str(value)])


def string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def planned_output(output_root: str | Path, node_id: str, filename: str) -> Path:
    directory = Path(output_root) / node_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory / filename


def plan_outputs(output_root: str | Path, node_id: str, filenames: tuple[str, ...]) -> list[Path]:
    """Plan a fixed output tuple in the same order as ``RETURN_NAMES``."""
    return [planned_output(output_root, node_id, filename) for filename in filenames]


def add_boolean_flags(command: list[str], inputs: dict[str, Any], pairs: tuple[tuple[str, str], ...]) -> None:
    for name, flag in pairs:
        if inputs.get(name):
            command.append(flag)


def add_output_flags(
    command: list[str],
    inputs: dict[str, Any],
    outputs: tuple[tuple[str, str], ...],
) -> None:
    """Add HMMER's direct output options; no shell redirection is required."""
    root = output_dir(inputs)
    for flag, filename in outputs:
        command.extend([flag, f"{root}/{filename}"])


def add_threshold_flags(
    command: list[str],
    inputs: dict[str, Any],
    *,
    include_default: float,
    domains: bool,
    allow_model_cutoffs: bool,
) -> None:
    """Render mutually exclusive HMMER reporting and inclusion thresholds."""
    if allow_model_cutoffs:
        selected = [name for name in ("cut_ga", "cut_nc", "cut_tc") if inputs.get(name)]
        if selected:
            command.append(f"--{selected[0]}")
            return

    if inputs.get("score_threshold") not in (None, ""):
        add_value(command, "-T", inputs["score_threshold"])
    else:
        add_value(command, "-E", inputs.get("evalue", 10.0))

    if inputs.get("incT") not in (None, ""):
        add_value(command, "--incT", inputs["incT"])
    else:
        add_value(command, "--incE", inputs.get("incE", include_default))

    if domains:
        if inputs.get("domT") not in (None, ""):
            add_value(command, "--domT", inputs["domT"])
        else:
            add_value(command, "--domE", inputs.get("domE", 10.0))
        if inputs.get("incdomT") not in (None, ""):
            add_value(command, "--incdomT", inputs["incdomT"])
        else:
            add_value(command, "--incdomE", inputs.get("incdomE", include_default))


def add_heuristic_flags(
    command: list[str],
    inputs: dict[str, Any],
    *,
    defaults: tuple[float, float, float],
) -> None:
    """Render HMMER filters without combining ``--max`` with incompatible flags."""
    if inputs.get("max"):
        command.append("--max")
        return
    for name, default in zip(("F1", "F2", "F3"), defaults, strict=True):
        add_value(command, f"--{name}", inputs.get(name, default))
    if inputs.get("nobias"):
        command.append("--nobias")


def common_output_inputs() -> dict[str, tuple[str, dict[str, Any]]]:
    return {
        "acc": ("BOOLEAN", {"default": False, "description": "Prefer accessions over names"}),
        "noali": ("BOOLEAN", {"default": False, "description": "Suppress alignment blocks"}),
        "notextw": ("BOOLEAN", {"default": False, "description": "Use unlimited text output width"}),
    }


def common_threshold_inputs(
    *,
    include_default: float,
    domains: bool,
    model_cutoffs: bool,
) -> dict[str, tuple[str, dict[str, Any]]]:
    inputs: dict[str, tuple[str, dict[str, Any]]] = {
        "evalue": ("FLOAT", {"default": 10.0, "min": 0, "description": "Per-hit reporting E-value (-E)"}),
        "score_threshold": (
            "FLOAT",
            {"default": "", "description": "Per-hit reporting bit score (-T); overrides evalue"},
        ),
        "incE": ("FLOAT", {"default": include_default, "min": 0, "description": "Per-hit inclusion E-value"}),
        "incT": (
            "FLOAT",
            {"default": "", "description": "Per-hit inclusion bit score; overrides incE"},
        ),
    }
    if domains:
        inputs.update(
            {
                "domE": ("FLOAT", {"default": 10.0, "min": 0, "description": "Per-domain reporting E-value"}),
                "domT": (
                    "FLOAT",
                    {"default": "", "description": "Per-domain reporting bit score; overrides domE"},
                ),
                "incdomE": (
                    "FLOAT",
                    {"default": include_default, "min": 0, "description": "Per-domain inclusion E-value"},
                ),
                "incdomT": (
                    "FLOAT",
                    {"default": "", "description": "Per-domain inclusion bit score; overrides incdomE"},
                ),
            }
        )
    if model_cutoffs:
        inputs.update(
            {
                "cut_ga": ("BOOLEAN", {"default": False, "description": "Use model GA cutoffs"}),
                "cut_nc": ("BOOLEAN", {"default": False, "description": "Use model NC cutoffs"}),
                "cut_tc": ("BOOLEAN", {"default": False, "description": "Use model TC cutoffs"}),
            }
        )
    return inputs


def common_heuristic_inputs(
    defaults: tuple[float, float, float],
) -> dict[str, tuple[str, dict[str, Any]]]:
    return {
        "max": ("BOOLEAN", {"default": False, "description": "Disable the heuristic filters", "advanced": True}),
        "F1": ("FLOAT", {"default": defaults[0], "min": 0, "max": 1, "advanced": True}),
        "F2": ("FLOAT", {"default": defaults[1], "min": 0, "max": 1, "advanced": True}),
        "F3": ("FLOAT", {"default": defaults[2], "min": 0, "max": 1, "advanced": True}),
        "nobias": (
            "BOOLEAN",
            {"default": False, "description": "Disable the composition-bias filter", "advanced": True},
        ),
    }


def validate_search_options(
    inputs: dict[str, Any],
    *,
    domains: bool,
    model_cutoffs: bool,
) -> bool | str:
    if inputs.get("max") and inputs.get("nobias"):
        return "max and nobias are mutually exclusive in HMMER 3.4"
    if model_cutoffs:
        selected = [name for name in ("cut_ga", "cut_nc", "cut_tc") if inputs.get(name)]
        if len(selected) > 1:
            return "Only one of cut_ga, cut_nc, and cut_tc may be enabled"
    positive = ["evalue", "incE", "z"]
    if domains:
        positive.extend(["domE", "incdomE", "domz"])
    for name in positive:
        if inputs.get(name) not in (None, "") and float(inputs[name]) <= 0:
            return f"Input '{name}' must be greater than 0"
    return True


def validate_pressed_hmm_bundle(inputs: dict[str, Any], database_key: str = "hmmdb") -> bool | str:
    """Require the four exact sibling files created by ``hmmpress``."""
    database = str(inputs.get(database_key, "")).strip()
    if not database:
        return f"Input '{database_key}' must be a non-empty path"
    if database == "-":
        return f"Input '{database_key}' cannot be read from stdin because pressed sidecars are required"
    normalized_database = Path(os.path.abspath(os.path.normpath(database)))
    for suffix in HMMER_PRESSED_SUFFIXES:
        key = f"{database_key}_{suffix[1:]}"
        value = str(inputs.get(key, "")).strip()
        expected = Path(f"{normalized_database}{suffix}")
        if not value:
            return f"Input '{key}' is required; expected '{expected}'"
        actual = Path(os.path.abspath(os.path.normpath(value)))
        if actual != expected:
            return f"Input '{key}' must be the exact sibling '{expected}'"
    return True


def _stage_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        return
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            raise
        shutil.copy2(source, destination)


def stage_pressed_hmm_bundle(inputs: dict[str, Any], destination: Path, database_key: str = "hmmdb") -> None:
    """Stage a pressed database and rewrite the base path used by HMMER."""
    source_database = Path(str(inputs[database_key]))
    staged_database = destination / source_database.name
    _stage_file(source_database, staged_database)
    inputs[database_key] = str(staged_database)
    for suffix in HMMER_PRESSED_SUFFIXES:
        key = f"{database_key}_{suffix[1:]}"
        staged_sidecar = Path(f"{staged_database}{suffix}")
        _stage_file(Path(str(inputs[key])), staged_sidecar)
        inputs[key] = str(staged_sidecar)


class HMMERContractNode(ValidatedCommandContract):
    """Base metadata shared by HMMER 3.4 command nodes."""

    VERSION = HMMER_VERSION
    GIT_URL = HMMER_GIT_URL
    GIT_COMMIT = HMMER_GIT_COMMIT
    GIT_TAG_OBJECT = HMMER_TAG_OBJECT
    SOURCE_URL = f"https://github.com/EddyRivasLab/hmmer/tree/{HMMER_GIT_COMMIT}"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CONDA_PACKAGE_CONSTRAINTS = {"hmmer": HMMER_VERSION}
    PACKAGE_CONSTRAINT = f"hmmer=={HMMER_VERSION}"
    CITATION_DOIS = [HMMER_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{HMMER_CITATION_DOI}"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    OPTION_PARSER_VERSION = EASEL_VERSION
    OPTION_PARSER_GIT_URL = "https://github.com/EddyRivasLab/easel.git"
    OPTION_PARSER_GIT_COMMIT = EASEL_GIT_COMMIT
    OPTION_PARSER_TAG_OBJECT = EASEL_TAG_OBJECT
    OPTION_PARSER_SOURCE_URL = f"{EASEL_SOURCE_ROOT}/esl_getopts.c"
    OPTION_PARSER_SOURCE = "esl_getopts.c::esl_opt_VerifyConfig"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "HMMER option parsing, input parsing, and command failures are fatal; "
        "BioNodulo also fails when the declared output artifact is absent."
    )

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        normalized = dict(inputs)
        optional = cls.INPUT_TYPES().get("optional", {})
        for name, spec in optional.items():
            if normalized.get(name) == "" and spec[0] in {"FLOAT", "INT", "FILE"}:
                normalized.pop(name)
        return super().VALIDATE_INPUTS(normalized)


__all__ = [
    "EASEL_GIT_COMMIT",
    "EASEL_SOURCE_ROOT",
    "EASEL_TAG_OBJECT",
    "EASEL_VERSION",
    "HMMERContractNode",
    "HMMER_GIT_COMMIT",
    "HMMER_NUCLEOTIDE_CITATION_DOI",
    "HMMER_PRESSED_SUFFIXES",
    "HMMER_PROTEIN_MATRICES",
    "HMMER_SOURCE_ROOT",
    "HMMER_VERSION",
    "add_boolean_flags",
    "add_heuristic_flags",
    "add_output_flags",
    "add_threshold_flags",
    "add_value",
    "common_heuristic_inputs",
    "common_output_inputs",
    "common_threshold_inputs",
    "output_dir",
    "plan_outputs",
    "planned_output",
    "stage_pressed_hmm_bundle",
    "string_list",
    "validate_pressed_hmm_bundle",
    "validate_search_options",
]
