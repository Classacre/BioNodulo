"""Shared source identity and script preparation for Scanpy/Squidpy nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar, Mapping

from bionodulo.nodes.command_node import CommandNode


SCANPY_COMMIT = "b8c7d1083c518f9a57e325f0e6574f9cd41afa21"
SQUIDPY_COMMIT = "e36a6f833c7eccdce62a89c668f90dc12164ae6d"


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


def validate_run_id(value: Any, key: str = "run_id") -> bool | str:
    run_id = str(value)
    if not run_id or len(run_id) > 64:
        return f"Input '{key}' must contain 1 to 64 characters"
    if any(not (char.isalnum() or char in "_-") for char in run_id):
        return f"Input '{key}' may only contain letters, numbers, underscores, and hyphens"
    return True


class PythonScriptNode(CommandNode):
    """Prepare one bounded Python script and require its declared outputs."""

    REQUIRED_EXECUTABLES = ["python"]
    SHELL = False
    RUN_IN_NODE_OUTPUT_DIR = True
    CONDA_PACKAGE_CONSTRAINTS: ClassVar[Mapping[str, str]] = {}
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    SCRIPT_FILENAME = "run.py"
    PREVIEW_LABELS: ClassVar[tuple[str | None, ...]] = ()
    EXIT_SEMANTICS = "Python exit code 0 plus all planned outputs is success; otherwise the node fails."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

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

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.get("context")
        result = await super().run(**kwargs)
        paths = tuple(result)
        if context is not None and hasattr(context, "register_preview"):
            for path, label in zip(paths, self.PREVIEW_LABELS, strict=False):
                if label:
                    context.register_preview(Path(path), label=label)
        return paths
