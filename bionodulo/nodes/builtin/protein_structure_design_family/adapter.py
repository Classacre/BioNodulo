"""Shared validation and script preparation for structure/design nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar, Mapping

from bionodulo.nodes.command_node import CommandNode


def path_value(value: Any) -> str:
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


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


class PythonScriptNode(CommandNode):
    """Prepare one bounded Python wrapper and require its declared outputs."""

    REQUIRED_EXECUTABLES = ["python"]
    SHELL = False
    RUN_IN_NODE_OUTPUT_DIR = True
    CONDA_PACKAGE_CONSTRAINTS: ClassVar[Mapping[str, str]] = {}
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    SCRIPT_FILENAME = "run.py"

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
        return True

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        raise NotImplementedError

    @classmethod
    def _prepare_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> Path:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        script_path = outputs[0].parent / cls.SCRIPT_FILENAME
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(cls.build_script(inputs, outputs), encoding="utf-8")
        inputs["_script_path"] = str(script_path)
        return script_path

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls._prepare_script(inputs, outputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        script_path = inputs.get("_script_path")
        if not script_path:
            output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
            outputs = [output / name for name in cls.OUTPUT_FILENAMES]
            script_path = cls._prepare_script(inputs, outputs)
        return ["python", str(script_path)]
