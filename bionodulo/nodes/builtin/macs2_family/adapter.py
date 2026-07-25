"""Shared metadata and validation helpers for MACS2 2.2.9.1 nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


MACS2_VERSION = "2.2.9.1"
MACS2_GIT_URL = "https://github.com/macs3-project/MACS.git"
MACS2_GIT_COMMIT = "1afcae6a09ced8cf9bb1e87c44dd58f7d7e4891c"
MACS2_SOURCE_ROOT = f"https://github.com/macs3-project/MACS/blob/{MACS2_GIT_COMMIT}"
MACS2_PACKAGE_CONSTRAINT = f"macs2=={MACS2_VERSION}"


def macs2_source_urls(*paths: str) -> tuple[str, ...]:
    """Return immutable source URLs at the audited MACS2 revision."""
    return tuple(f"{MACS2_SOURCE_ROOT}/{path}" for path in paths)


class MACS2CommandNode(CommandNode):
    """Common source and environment identity for focused MACS2 operations."""

    CATEGORY = "chip_seq"
    REQUIRED_EXECUTABLES = ["macs2"]
    REQUIRED_CONDA_PACKAGES = ["macs2"]
    # The known-good Bioconda MACS2 build requires NumPy 1.x, while the pinned
    # deepTools runtime requires NumPy 2.x.  Keep MACS2 in a named environment
    # within the same committed workflow lock so both exact runtimes remain
    # reproducible without weakening either tool's package contract.
    ENVIRONMENT = {"type": "pixi", "name": "macs2"}
    CONDA_PACKAGE_CONSTRAINTS = {"macs2": MACS2_VERSION}
    PACKAGE_CONSTRAINTS = (MACS2_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = MACS2_PACKAGE_CONSTRAINT
    VERSION = MACS2_VERSION
    PACKAGE_VERSION = MACS2_VERSION
    GIT_URL = MACS2_GIT_URL
    GIT_COMMIT = MACS2_GIT_COMMIT
    GIT_TAG = "v2.2.9.1"
    SOURCE_REF = f"tag v2.2.9.1 at {MACS2_GIT_COMMIT}"
    SOURCE_REVISION = MACS2_GIT_COMMIT
    SOURCE_URL = f"https://github.com/macs3-project/MACS/tree/{MACS2_GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "argparse exits non-zero for malformed arguments; callpeak validation uses "
        "sys.exit(1), while unreadable inputs and processing errors propagate as non-zero "
        "process failures. BioNodulo requires staged non-empty input files, exit zero, "
        "and every declared output artifact to exist."
    )
    CITATION_DOIS = ["10.1186/gb-2008-9-9-r137"]
    CITATION_URLS = ["https://doi.org/10.1186/gb-2008-9-9-r137"]
    CITATION_TEXT = "Model-based Analysis of ChIP-Seq (MACS)."
    SHELL = False

    UPSTREAM_PARSER = "bin/macs2"
    UPSTREAM_SOURCE = ""

    @staticmethod
    def safe_output_stem(value: Any, default: str) -> str:
        """Return a predictable MACS2 filename stem without path components."""
        stem = "_".join(str(value or "").strip().split())
        stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in stem)
        stem = stem.strip("._-")
        return stem or default

    @staticmethod
    def require_path(inputs: dict[str, Any], key: str) -> bool | str:
        """Validate path-like CLI inputs without requiring local materialization."""
        try:
            path = os.fsdecode(os.fspath(inputs.get(key)))
        except TypeError:
            return f"Input '{key}' must be a non-empty path-like value"
        if not path.strip():
            return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def require_nonempty_file(cls, inputs: dict[str, Any], key: str) -> bool | str:
        """Require a staged file because MACS2 opens every declared input directly."""
        validation = cls.require_path(inputs, key)
        if validation is not True:
            return validation
        path = Path(os.fsdecode(os.fspath(inputs[key])))
        try:
            if not path.is_file():
                return f"Input '{key}' is not a materialized file: {path}"
            if path.stat().st_size == 0:
                return f"Input '{key}' is empty: {path}"
        except OSError as exc:
            return f"Input '{key}' could not be inspected: {path}: {exc}"
        return True

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))
