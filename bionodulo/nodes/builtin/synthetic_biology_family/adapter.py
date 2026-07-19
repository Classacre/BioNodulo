"""Shared validation for focused synthetic-biology commands."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


def path_value(value: Any) -> str:
    """Return one non-empty path-like value as text."""
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def validate_bool(value: Any, key: str) -> bool | str:
    if not isinstance(value, bool):
        return f"Input '{key}' must be a boolean"
    return True


def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    selected = str(value)
    if selected not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True


def validate_int(value: Any, key: str, *, minimum: int | None = None) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"Input '{key}' must be an integer"
    if minimum is not None and value < minimum:
        return f"Input '{key}' must be at least {minimum}"
    return True


class SyntheticBiologyCommandNode(CommandNode):
    """Runtime contract shared by focused synthetic-biology nodes."""

    CATEGORY = "synthetic_biology"
    SEARCH_ALIASES = ["BioNodulo builtin", "synthetic biology", "biocad"]
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    OPTIONAL_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""
    EXIT_SEMANTICS = "A non-zero process exit is fatal; every planned output must exist."

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in cls.REQUIRED_PATH_INPUTS:
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        for key in cls.OPTIONAL_PATH_INPUTS:
            value = inputs.get(key, "")
            if value not in (None, "") and not path_value(value):
                return f"Input '{key}' must be a path-like value when provided"
        return True

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

    @classmethod
    def node_output_dir(cls, output_dir: str | Path) -> Path:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return node_dir
