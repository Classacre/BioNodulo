"""Shared source identity and validation for MUMmer4 4.0.1."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


MUMMER4_COMMIT = "eb734606f2d516f42a0e0dce7a116bfb88ec1ebf"


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
    elif isinstance(value, Iterable):
        values = value
    else:
        return []
    result = [path_value(item) for item in values]
    return result if result and all(result) else []


def validate_choice(value: Any, key: str, choices: tuple[str, ...]) -> bool | str:
    selected = str(value)
    if selected not in choices:
        return f"Input '{key}' must be one of: {', '.join(choices)}"
    return True


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


def add_value(command: list[str], flag: str, value: Any) -> None:
    if value not in (None, ""):
        command.extend([flag, str(value)])


def add_flag(command: list[str], flag: str, enabled: Any) -> None:
    if enabled:
        command.append(flag)


def stage_file(source: Any, destination: Path) -> None:
    source_path = Path(path_value(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if source_path.exists() and os.path.samefile(source_path, destination):
            return
        destination.unlink()
    try:
        os.link(source_path, destination)
    except OSError:
        shutil.copy2(source_path, destination)


class Mummer4CommandNode(CommandNode):
    """Pinned metadata and deterministic output planning for MUMmer4."""

    CATEGORY = "genomics"
    REQUIRED_CONDA_PACKAGES = ["mummer4"]
    VERSION = "4.0.1"
    GIT_URL = "https://github.com/mummer4/mummer.git"
    GIT_COMMIT = MUMMER4_COMMIT
    DOCUMENTATION_URL = "https://mummer4.github.io/manual/manual.html"
    CITATION_DOIS = ["10.1371/journal.pcbi.1005944"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pcbi.1005944"]
    CITATION_TEXT = "MUMmer4: A fast and versatile genome alignment system."
    SEARCH_ALIASES = ["BioNodulo builtin", "MUMmer4"]
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_LIST_INPUTS: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""

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
