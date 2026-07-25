"""Shared metadata and argument helpers for deepTools 3.5.6 nodes."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


DEEPTOOLS_VERSION = "3.5.6"
DEEPTOOLS_GIT_URL = "https://github.com/deeptools/deepTools.git"
DEEPTOOLS_GIT_COMMIT = "ea0f68bb4a1587d713dacb3791861308751ef7d0"
DEEPTOOLS_SOURCE_ROOT = f"https://github.com/deeptools/deepTools/blob/{DEEPTOOLS_GIT_COMMIT}"
DEEPTOOLS_PACKAGE_CONSTRAINT = f"deeptools=={DEEPTOOLS_VERSION}"


def deeptools_source_urls(*paths: str) -> tuple[str, ...]:
    return tuple(f"{DEEPTOOLS_SOURCE_ROOT}/{path}" for path in paths)


class DeepToolsCommandNode(CommandNode):
    """Common source and environment identity for focused deepTools operations."""

    CATEGORY = "epigenomics"
    REQUIRED_CONDA_PACKAGES = ["deeptools"]
    CONDA_PACKAGE_CONSTRAINTS = {"deeptools": DEEPTOOLS_VERSION}
    PACKAGE_CONSTRAINTS = (DEEPTOOLS_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = DEEPTOOLS_PACKAGE_CONSTRAINT
    VERSION = DEEPTOOLS_VERSION
    PACKAGE_VERSION = DEEPTOOLS_VERSION
    GIT_URL = DEEPTOOLS_GIT_URL
    GIT_COMMIT = DEEPTOOLS_GIT_COMMIT
    GIT_TAG = "3.5.6"
    SOURCE_REF = f"tag 3.5.6 at {DEEPTOOLS_GIT_COMMIT}"
    SOURCE_URL = f"https://github.com/deeptools/deepTools/tree/{DEEPTOOLS_GIT_COMMIT}"
    SOURCE_REVISION = DEEPTOOLS_GIT_COMMIT
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "argparse rejects malformed arguments with a non-zero exit; deepTools also "
        "uses SystemExit or uncaught processing errors for invalid data. BioNodulo "
        "requires exit 0 and every planned artifact to exist."
    )
    CITATION_DOIS = ["10.1093/nar/gkw257"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkw257"]
    CITATION_TEXT = "deepTools2: a next generation web server for deep-sequencing data analysis."
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @staticmethod
    def require_path(inputs: dict[str, Any], key: str) -> bool | str:
        try:
            path = os.fsdecode(os.fspath(inputs.get(key)))
        except TypeError:
            return f"Input '{key}' must be a non-empty path-like value"
        if not path.strip():
            return f"Input '{key}' must be a non-empty path-like value"
        return True

    @staticmethod
    def path_values(value: Any) -> list[str]:
        """Preserve each path as one argv token while accepting scalar inputs."""
        if isinstance(value, (str, bytes, os.PathLike)):
            raw_values = (value,)
        elif isinstance(value, (list, tuple)):
            raw_values = value
        else:
            return []

        paths: list[str] = []
        for item in raw_values:
            try:
                path = os.fsdecode(os.fspath(item))
            except TypeError:
                return []
            if not path.strip():
                return []
            paths.append(path)
        return paths

    @classmethod
    def require_paths(cls, inputs: dict[str, Any], key: str) -> bool | str:
        if not cls.path_values(inputs.get(key)):
            return f"Input '{key}' must contain one or more non-empty path-like values"
        return True

    @staticmethod
    def split_cli_values(value: Any) -> list[str]:
        """Convert a UI multi-value field into distinct subprocess arguments."""
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value if str(item).strip()]
        return shlex.split(str(value))

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))
