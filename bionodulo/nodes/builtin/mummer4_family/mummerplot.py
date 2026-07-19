"""MUMmer4 4.0.1 plot generation with ``mummerplot``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapter import Mummer4CommandNode, add_flag, path_value, validate_choice, validate_int


class Mummer4MummerplotNode(Mummer4CommandNode):
    """Generate a deterministic non-interactive plot and native plot sources."""

    NODE_ID = "mummer4_mummerplot"
    DISPLAY_NAME = "MUMmer4 Mummerplot"
    DESCRIPTION = "Generate a dotplot or reference-coverage plot from MUMmer alignment output."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "MUMmer4",
        "mummerplot",
        "dotplot",
        "coverage plot",
        "gnuplot",
    ]
    RETURN_TYPES = ("IMAGE", "FILE_LIST")
    RETURN_NAMES = ("plot", "plot_artifacts")
    REQUIRED_EXECUTABLES = ["mummerplot", "gnuplot"]
    REQUIRED_CONDA_PACKAGES = ["mummer4", "gnuplot"]
    REQUIRED_PATH_INPUTS = ("delta",)
    UPSTREAM_SOURCE = "scripts/mummerplot.pl"
    RUN_IN_NODE_OUTPUT_DIR = True

    COLOR_MODES = ("direction", "identity", "monochrome")
    SIZES = ("small", "medium", "large")
    TERMINALS = ("png", "postscript")
    _RANGE_RE = re.compile(r"^\[\d+[:,]\d+\]$")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "delta": (
                    "FILE",
                    {"description": "Mummer match list, nucmer/promer delta file, or show-tiling output"},
                ),
            },
            "optional": {
                "breaklen": ("INT", {"default": None, "min": 0}),
                "color_mode": ("STRING", {"default": "direction", "options": list(cls.COLOR_MODES)}),
                "coverage": ("BOOLEAN", {"default": False}),
                "filter": ("BOOLEAN", {"default": False}),
                "layout": ("BOOLEAN", {"default": False}),
                "fat": ("BOOLEAN", {"default": False}),
                "ref_id": ("STRING", {"default": None}),
                "query_id": ("STRING", {"default": None}),
                "reference_sequence": (
                    "FILE",
                    {"default": None, "description": "Optional -R FASTA or ordered reference ID list"},
                ),
                "query_sequence": (
                    "FILE",
                    {"default": None, "description": "Optional -Q FASTA or ordered query ID list"},
                ),
                "size": ("STRING", {"default": "small", "options": list(cls.SIZES)}),
                "snp": ("BOOLEAN", {"default": False}),
                "terminal": ("STRING", {"default": "png", "options": list(cls.TERMINALS)}),
                "title": ("STRING", {"default": None}),
                "xrange": ("STRING", {"default": None, "description": "Plot range such as [0:1000]"}),
                "yrange": ("STRING", {"default": None, "description": "Plot range such as [0:1000]"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def image_filename(cls, inputs: dict[str, Any]) -> str:
        return "out.ps" if inputs.get("terminal", "png") == "postscript" else "out.png"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        outputs = [
            node_dir / cls.image_filename(inputs),
            node_dir / "out.gp",
            node_dir / "out.fplot",
            node_dir / "out.rplot",
        ]
        if inputs.get("breaklen") is not None or inputs.get("snp", False):
            outputs.append(node_dir / "out.hplot")
        if inputs.get("filter", False) or inputs.get("layout", False) or inputs.get("fat", False):
            outputs.append(node_dir / "out.filter")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        images = [path for path in planned_paths if path.suffix in {".png", ".ps"}]
        artifacts = [path for path in planned_paths if path not in images]
        if len(images) != 1 or len(artifacts) < 3:
            raise ValueError("mummerplot planned an invalid source-native artifact set")
        return {"plot": images[0], "plot_artifacts": artifacts}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, value, choices in (
            ("color_mode", inputs.get("color_mode", "direction"), cls.COLOR_MODES),
            ("size", inputs.get("size", "small"), cls.SIZES),
            ("terminal", inputs.get("terminal", "png"), cls.TERMINALS),
        ):
            validation = validate_choice(value, key, choices)
            if validation is not True:
                return validation
        if inputs.get("breaklen") is not None:
            validation = validate_int(inputs["breaklen"], "breaklen", minimum=0)
            if validation is not True:
                return validation
        for key in ("xrange", "yrange"):
            value = inputs.get(key)
            if value not in (None, "") and not cls._RANGE_RE.fullmatch(str(value)):
                return f"Input '{key}' must use the source format '[min:max]' or '[min,max]' with non-negative integers"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(
            inputs,
            "mummerplot",
            "-p",
            "out",
            "-t",
            str(inputs.get("terminal", "png")),
        )
        if inputs.get("breaklen") is not None:
            command.extend(["-b", str(inputs["breaklen"])])
        color_mode = str(inputs.get("color_mode", "direction"))
        if color_mode == "identity":
            command.append("--color")
        elif color_mode == "monochrome":
            command.append("--nocolor")
        add_flag(command, "--coverage", inputs.get("coverage"))
        add_flag(command, "--filter", inputs.get("filter"))
        add_flag(command, "--layout", inputs.get("layout"))
        add_flag(command, "--fat", inputs.get("fat"))
        if inputs.get("ref_id") not in (None, ""):
            command.extend(["-r", str(inputs["ref_id"])])
        if inputs.get("query_id") not in (None, ""):
            command.extend(["-q", str(inputs["query_id"])])
        if path_value(inputs.get("reference_sequence")):
            command.extend(["-R", path_value(inputs["reference_sequence"])])
        if path_value(inputs.get("query_sequence")):
            command.extend(["-Q", path_value(inputs["query_sequence"])])
        command.extend(["-s", str(inputs.get("size", "small"))])
        add_flag(command, "--SNP", inputs.get("snp"))
        if inputs.get("title") not in (None, ""):
            command.extend(["--title", str(inputs["title"])])
        for key, flag in (("xrange", "-x"), ("yrange", "-y")):
            if inputs.get(key) not in (None, ""):
                command.extend([flag, str(inputs[key])])
        command.append(path_value(inputs.get("delta")))
        return command

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {
            "outputs": {
                "plot": str(mapped["plot"]),
                "plot_artifacts": [str(path) for path in mapped["plot_artifacts"]],
            }
        }
