"""Stable owner for ``vg_index``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import _path_value, _positive_int, _safe_output_stem
from .evidence import PangenomicsCommandContract


class VGIndexNode(PangenomicsCommandContract):
    """Build vg autoindex artifacts for graph read mapping."""

    NODE_ID = "vg_index"
    DISPLAY_NAME = "vg Autoindex"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Build vg autoindex files for Giraffe graph read mapping and downstream graph calling."
    SEARCH_ALIASES = ["vg", "autoindex", "giraffe", "gbz", "minimizer", "distance index", "pangenome index"]
    RETURN_TYPES = ("GBZ", "FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("gbz_index", "minimizer_index", "zipcode_index", "distance_index", "xg_index")
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg/wiki/Automatic-indexing-for-read-mapping-and-downstream-inference"
    VERSION = "1.62.0"
    SHELL = True

    _WORKFLOWS = {"giraffe"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        workflow = str(inputs.get("workflow", "giraffe") or "giraffe")
        if workflow not in cls._WORKFLOWS:
            return f"Unsupported vg Autoindex workflow: {workflow}"
        if not _path_value(inputs.get("graph_gfa")):
            return "graph_gfa must be a non-empty path-like value"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        target_mem = str(inputs.get("target_mem", "") or "")
        if target_mem and not re.fullmatch(r"[1-9][0-9]*[kMG]?", target_mem):
            return "target_mem must use vg's INT[kMG] format"
        return True

    @classmethod
    def _prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        node_out = Path(output_dir)
        fallback_stem = _safe_output_stem(inputs.get("graph_gfa"), "graph")
        stem = _safe_output_stem(inputs.get("output_prefix"), fallback_stem)
        return node_out / stem

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        prefix = cls._prefix(inputs, out_dir)
        workflow = str(inputs.get("workflow", "giraffe") or "giraffe")
        gbz_index = f"{prefix}.giraffe.gbz"
        xg_index = f"{prefix}.xg"

        cmd = [
            "vg",
            "autoindex",
            "--workflow",
            workflow,
            "--gfa",
            str(inputs.get("graph_gfa", "")),
        ]
        cmd.extend([
            "--prefix",
            str(prefix),
            "--threads",
            str(inputs.get("threads", 8)),
        ])
        if inputs.get("tmp_dir"):
            cmd.extend(["--tmp-dir", str(inputs["tmp_dir"])])
        if inputs.get("target_mem"):
            cmd.extend(["--target-mem", str(inputs["target_mem"])])
        cmd.extend([
            "&&",
            "vg",
            "convert",
            "-x",
            "--drop-haplotypes",
            gbz_index,
            ">",
            xg_index,
            "&&",
            "test",
            "-s",
            gbz_index,
            "&&",
            "test",
            "-s",
            f"{prefix}.shortread.withzip.min",
            "&&",
            "test",
            "-s",
            f"{prefix}.shortread.zipcodes",
            "&&",
            "test",
            "-s",
            f"{prefix}.dist",
            "&&",
            "test",
            "-s",
            xg_index,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = cls._prefix(inputs, node_out)
        return [
            Path(f"{prefix}.giraffe.gbz"),
            Path(f"{prefix}.shortread.withzip.min"),
            Path(f"{prefix}.shortread.zipcodes"),
            Path(f"{prefix}.dist"),
            Path(f"{prefix}.xg"),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "graph_gfa": ("GFA", {"description": "Input pangenome graph in GFA format"}),
            },
            "optional": {
                "workflow": ("STRING", {"default": "giraffe", "options": ["giraffe"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
                "output_prefix": ("STRING", {"default": "", "description": "Optional output filename stem"}),
                "tmp_dir": ("STRING", {"default": "", "description": "Optional temporary directory for vg autoindex"}),
                "target_mem": ("STRING", {"default": "", "description": "Optional target memory limit, for example 64G"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
