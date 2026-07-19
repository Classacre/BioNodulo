"""Stable owner for ``vg_map``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import _path_value, _positive_int, _stage_file
from .evidence import PangenomicsCommandContract


class VGMapNode(PangenomicsCommandContract):
    """Map reads to variation graphs with vg map or giraffe."""
    NODE_ID = "vg_map"
    DISPLAY_NAME = "vg Map/Giraffe"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Map reads to a variation graph using vg map or vg giraffe. Produces GAM alignments."
    SEARCH_ALIASES = ["vg", "map", "giraffe", "pangenome align", "graph alignment", "gam"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("gam_alignment",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True
    SIDECAR_POLICY = (
        "Classic vg map loads the GCSA LCP array from <gcsa_index>.lcp; "
        "gcsa_index and gcsa_lcp are explicit inputs staged under that exact sibling name."
    )

    _MAPPERS = {"giraffe", "map"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not _path_value(inputs.get("reads")):
            return "reads must be a non-empty path-like value"
        mapper = str(inputs.get("mapper", "giraffe") or "giraffe")
        if mapper not in cls._MAPPERS:
            return f"Unsupported vg mapper: {mapper}"
        validation = _positive_int(inputs.get("threads", 8), "threads", 8)
        if isinstance(validation, str):
            return validation
        required = (
            ("gbz_index", "minimizer_index", "distance_index")
            if mapper == "giraffe"
            else ("xg_index", "gcsa_index", "gcsa_lcp")
        )
        for name in required:
            if not _path_value(inputs.get(name)):
                return f"{name} is required for mapper={mapper}"
        min_identity = inputs.get("min_identity", 0.0)
        if isinstance(min_identity, bool) or not isinstance(min_identity, (int, float)):
            return "min_identity must be a number"
        if not 0 <= float(min_identity) <= 1:
            return "min_identity must be between 0 and 1"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if str(inputs.get("mapper", "giraffe") or "giraffe") != "map":
            return
        stage_root = outputs[0].parent / "inputs"
        staged_gcsa = stage_root / "graph.gcsa"
        _stage_file(Path(_path_value(inputs["gcsa_index"])), staged_gcsa)
        staged_lcp = Path(f"{staged_gcsa}.lcp")
        _stage_file(Path(_path_value(inputs["gcsa_lcp"])), staged_lcp)
        inputs["gcsa_index"] = str(staged_gcsa)
        inputs["gcsa_lcp"] = str(staged_lcp)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get("output", ".")))
        mapper = inputs.get("mapper", "giraffe")
        reads = str(inputs.get("reads", ""))
        reads2 = str(inputs.get("reads2", ""))
        threads = str(inputs.get("threads", 8))

        if mapper == "giraffe":
            cmd = [
                "vg",
                "giraffe",
                "-Z",
                str(inputs.get("gbz_index", "")),
                "-m",
                str(inputs.get("minimizer_index", "")),
                "-d",
                str(inputs.get("distance_index", "")),
                "-f",
                reads,
                "-t",
                threads,
            ]
            if reads2:
                cmd.extend(["-f", reads2])
            if inputs.get("zipcode_index"):
                distance_index = cmd.index("-d")
                cmd[distance_index:distance_index] = ["-z", str(inputs["zipcode_index"])]
        else:
            cmd = [
                "vg",
                "map",
                "-x",
                str(inputs.get("xg_index", "")),
                "-g",
                str(inputs.get("gcsa_index", "")),
                "-f",
                reads,
                "-t",
                threads,
            ]
            if reads2:
                cmd.extend(["-f", reads2])
            if float(inputs.get("min_identity", 0.0) or 0.0) > 0:
                cmd.extend(["--min-ident", str(inputs["min_identity"])])
        if inputs.get("progress"):
            cmd.append("-p")
        cmd.extend([">", str(out_dir / "gam_alignment.gam")])
        cmd.extend(["&&", "test", "-s", str(out_dir / "gam_alignment.gam")])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "gam_alignment.gam"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Forward/single-end FASTQ"}),
                "mapper": ("STRING", {"default": "giraffe", "options": ["giraffe", "map"]}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "reads2": ("FASTQ", {"description": "Reverse FASTQ (paired)"}),
                "gbz_index": ("GBZ", {"description": "Giraffe GBZ graph"}),
                "minimizer_index": ("FILE", {"description": "Minimizer index"}),
                "zipcode_index": ("FILE", {"description": "Optional oversized-zipcode distance hints"}),
                "distance_index": ("FILE", {"description": "Distance index"}),
                "xg_index": ("FILE", {"description": "XG index (for vg map)"}),
                "gcsa_index": ("FILE", {"description": "GCSA index (for vg map)"}),
                "gcsa_lcp": (
                    "FILE",
                    {"description": "Exact <gcsa_index>.lcp sidecar required by vg map"},
                ),
                "min_identity": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "progress": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
