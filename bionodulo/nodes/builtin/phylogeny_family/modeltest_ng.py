"""ModelTest-NG 0.1.7 model-selection owner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import path_value, validate_choice, validate_int
from .evidence import source_pinned
from .legacy import _ModelTestNGContract


@source_pinned("modeltest_ng")
class ModelTestNGNode(_ModelTestNGContract):
    NODE_ID = "modeltest_ng"
    RETURN_TYPES = ("TEXT", "TEXT")
    RETURN_NAMES = ("results", "log")
    SHELL = False
    REQUIRED_PATH_INPUTS = ("alignment",)
    DATATYPES = ("nt", "aa")
    TEMPLATES = ("", "raxml", "phyml", "mrbayes", "paup")
    SCHEMES = (0, 3, 5, 7, 11, 203)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not path_value(inputs.get("alignment")):
            return "Input 'alignment' must be a non-empty path-like value"
        validation = validate_choice(inputs.get("datatype", "nt"), "datatype", cls.DATATYPES)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("template", ""), "template", cls.TEMPLATES)
        if validation is not True:
            return validation
        schemes = inputs.get("schemes", 0)
        validation = validate_int(schemes, "schemes", minimum=0)
        if validation is not True:
            return validation
        if schemes not in cls.SCHEMES:
            return "Input 'schemes' must be one of: 0, 3, 5, 7, 11, 203"
        selectors = [
            bool(inputs.get("template")),
            bool(str(inputs.get("models", "")).strip()),
            bool(schemes),
        ]
        if sum(selectors) > 1:
            return "ModelTest-NG options 'models', 'schemes', and 'template' are mutually exclusive"
        if inputs.get("ascertainment_bias"):
            return "ascertainment_bias requires an algorithm value not exposed by this stable node"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", ".")))
        output_prefix = output_dir / "modeltest"
        command = [
            "modeltest-ng",
            "-i",
            str(inputs.get("alignment", "")),
            "-d",
            str(inputs.get("datatype", "nt")),
            "-p",
            str(inputs.get("threads", 4)),
            "-o",
            str(output_prefix),
        ]
        if inputs.get("template"):
            command.extend(["-T", str(inputs["template"])])
        if inputs.get("models"):
            command.extend(["-m", str(inputs["models"])])
        if inputs.get("schemes"):
            command.extend(["-s", str(inputs["schemes"])])
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prefix = Path(output_dir) / cls.NODE_ID / "modeltest"
        prefix.parent.mkdir(parents=True, exist_ok=True)
        return [Path(f"{prefix}.out"), Path(f"{prefix}.log")]
