"""Shared output planning and validation for focused annotation nodes."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def path_value(value: Any) -> str:
    """Return a direct-argv path, expanding a leading home-directory marker."""
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    result = result.strip()
    return os.path.expanduser(result) if result else ""


def normalized_path(value: Any) -> Path | None:
    path = path_value(value)
    if not path:
        return None
    return Path(os.path.abspath(os.path.normpath(path)))


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


def validate_choice(value: Any, key: str, choices: Iterable[str]) -> bool | str:
    allowed = tuple(choices)
    if str(value) not in allowed:
        return f"Input '{key}' must be one of: {', '.join(allowed)}"
    return True


def validate_filename(value: Any, key: str) -> bool | str:
    filename = str(value or "")
    if not _SAFE_FILENAME_RE.fullmatch(filename) or filename in {".", ".."}:
        return f"Input '{key}' must be a filename without directory components"
    return True


def validate_exact_path(value: Any, expected: Path, key: str) -> bool | str:
    actual = normalized_path(value)
    normalized_expected = normalized_path(expected)
    if actual is None or normalized_expected is None or actual != normalized_expected:
        return f"Input '{key}' must be the exact path '{normalized_expected}'"
    return True


class AnnotationCommandNode(CommandNode):
    """Common direct-argv runtime contract for external annotation tools."""

    CATEGORY = "annotation"
    SEARCH_ALIASES = ["BioNodulo builtin", "annotation"]
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""
    CONDA_PACKAGE_CONSTRAINTS: ClassVar[Mapping[str, str]] = {}
    EXIT_SEMANTICS = "A non-zero process exit is fatal; all planned outputs must exist."

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
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
