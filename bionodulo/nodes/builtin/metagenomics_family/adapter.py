"""Small shared helpers for source-pinned metagenomics commands."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
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


def path_list(value: Any) -> list[str]:
    """Normalize one path or an ordered iterable of paths."""
    if value in (None, ""):
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        values: Iterable[Any] = (value,)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = value
    else:
        return []
    paths = [path_value(item) for item in values]
    return paths if paths and all(paths) else []


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


def validate_number(
    value: Any,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"Input '{key}' must be a number"
    number = float(value)
    if minimum is not None and number < minimum:
        return f"Input '{key}' must be at least {minimum:g}"
    if maximum is not None and number > maximum:
        return f"Input '{key}' must be at most {maximum:g}"
    return True


def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    selected = str(value)
    if selected not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True


def add_flag(command: list[str], flag: str, enabled: Any) -> None:
    if enabled:
        command.append(flag)


class MetagenomicsCommandNode(CommandNode):
    """Shared output planning and path validation for focused operations."""

    CATEGORY = "metagenomics"
    SEARCH_ALIASES = ["BioNodulo builtin", "shotgun metagenomics"]
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_LIST_INPUTS: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_TAG: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""
    BIOCONDA_VERSION: ClassVar[str] = ""
    BIOCONDA_CONSTRAINT: ClassVar[str] = ""
    EXIT_SEMANTICS: ClassVar[str] = ""

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

    @staticmethod
    def output_dir(inputs: Mapping[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))
