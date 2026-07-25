"""Shared validation for focused proteomics commands."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


def path_value(value: Any) -> str:
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def path_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        values: Iterable[Any] = (value,)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = value
    else:
        return []
    result = [path_value(item) for item in values]
    return result if result and all(result) else []


def require_file(value: Any, key: str) -> Path:
    path = Path(path_value(value))
    if not path.is_file():
        raise ValueError(f"Input '{key}' must be an existing file")
    return path


def stage_file(value: Any, key: str, directory: Path, *, name: str | None = None) -> Path:
    source = require_file(value, key).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (name or source.name)
    if target.exists() or target.is_symlink():
        if target.resolve() != source:
            raise ValueError(f"Input '{key}' collides with another staged basename: {target.name}")
        return target
    target.symlink_to(source)
    return target


def replace_assignments(text: str, replacements: Mapping[str, Any]) -> str:
    """Replace existing ``key = value`` entries while preserving comments."""

    pending = {str(key): str(value) for key, value in replacements.items()}
    rendered: list[str] = []
    for line in text.splitlines():
        body, marker, comment = line.partition("#")
        if "=" in body and not body.lstrip().startswith("#"):
            key, _value = body.split("=", 1)
            normalized = key.strip()
            if normalized in pending:
                line = f"{key.rstrip()} = {pending.pop(normalized)}"
                if marker:
                    line += f"  # {comment.strip()}"
        rendered.append(line)
    if pending:
        missing = ", ".join(sorted(pending))
        raise ValueError(f"Parameter template is missing required entries: {missing}")
    return "\n".join(rendered) + "\n"


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


class ProteomicsCommandNode(CommandNode):
    """Direct-argv runtime contract shared by focused proteomics nodes."""

    CATEGORY = "proteomics"
    SEARCH_ALIASES = ["BioNodulo builtin", "proteomics"]
    SHELL = False
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_LIST_INPUTS: ClassVar[tuple[str, ...]] = ()
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""
    EXIT_SEMANTICS = "A non-zero process exit is fatal; every planned output must exist."

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
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
