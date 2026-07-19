"""Shared deterministic execution helpers for source-pinned R nodes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, ClassVar, Mapping

from bionodulo.nodes.command_node import CommandNode


R_VERSION = "4.5.3"
R_GIT_COMMIT = "c5ddd2fcc67d751f51085e5a29f8158410fc0eaf"
R_GIT_URL = "https://github.com/wch/r-source.git"
R_DOCUMENTATION_URL = "https://stat.ethz.ch/R-manual/R-patched/library/utils/html/Rscript.html"


def path_value(value: Any) -> str:
    """Return one non-empty filesystem value without requiring local existence."""

    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def r_string(value: Any) -> str:
    """Encode a Python value as a quoted R string literal."""

    return json.dumps(str(value), ensure_ascii=True)


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


class PreparedRScriptNode(CommandNode):
    """Prepare one bounded R script and require all declared outputs."""

    CATEGORY = "r"
    SEARCH_ALIASES = ["BioNodulo builtin", "R"]
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base"]
    CONDA_PACKAGE_CONSTRAINTS: ClassVar[Mapping[str, str]] = {"r-base": R_VERSION}
    SHELL = False
    RUN_IN_NODE_OUTPUT_DIR = True
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    SCRIPT_FILENAME = "run.R"
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()
    PREVIEW_LABELS: ClassVar[tuple[str | None, ...]] = ()
    RUNTIME_GIT_URL = R_GIT_URL
    RUNTIME_GIT_COMMIT = R_GIT_COMMIT
    RUNTIME_VERSION = R_VERSION
    EXIT_SEMANTICS = (
        "Rscript exit code 0 plus all planned outputs is success; any non-zero exit "
        "or missing output fails the node."
    )

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
            outputs = [output / filename for filename in cls.OUTPUT_FILENAMES]
            script_path = cls._prepare_script(inputs, outputs)
        return ["Rscript", "--vanilla", str(script_path)]

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.get("context")
        result = await super().run(**kwargs)
        paths = tuple(result)
        if context is not None and hasattr(context, "register_preview"):
            for path, label in zip(paths, self.PREVIEW_LABELS, strict=False):
                if label:
                    context.register_preview(Path(path), label=label)
        return paths
