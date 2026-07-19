"""Modkit 0.4.3 pairwise DMR with explicitly staged tabix sidecars."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SparseOutputEpigenomicsNode, path_value, safe_output_stem, split_values, stage_file


class ModkitDMRNode(SparseOutputEpigenomicsNode):
    """Compare two bgzipped bedMethyl samples with optional segmentation."""

    NODE_ID = "modkit_dmr"
    DISPLAY_NAME = "Modkit DMR"
    DESCRIPTION = "Score pairwise differential methylation from indexed modkit bedMethyl pileups."
    SEARCH_ALIASES = ["modkit", "dmr", "dmr pair", "differential methylation", "methylation", "bedmethyl"]
    RETURN_TYPES = ("BED", "BED", "FILE")
    RETURN_NAMES = ("dmr", "segments", "log")
    REQUIRED_EXECUTABLES = ["modkit"]
    REQUIRED_CONDA_PACKAGES = ["ont-modkit"]
    SIDECAR_POLICY = (
        "Modkit 0.4.3 source opens tabix indexes by sibling discovery. Explicit index_a/index_b "
        "ports are staged as sample_a.bed.gz.tbi and sample_b.bed.gz.tbi; the documented "
        "--index-a/--index-b flags are intentionally not emitted because the pinned parser does not define them."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sample_a": ("BED", {"description": "First bgzipped modkit bedMethyl pileup"}),
                "index_a": ("FILE", {"description": "Tabix index matching sample_a"}),
                "sample_b": ("BED", {"description": "Second bgzipped modkit bedMethyl pileup"}),
                "index_b": ("FILE", {"description": "Tabix index matching sample_b"}),
                "reference": ("FASTA", {"description": "Reference used for both pileups"}),
                "base": ("STRING", {"default": "C", "description": "One or more canonical bases"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "optional": {
                "regions": ("BED", {"description": "BED3/4 regions; omit for single-site analysis"}),
                "segment": ("BOOLEAN", {"default": False, "description": "Write HMM segmentation during single-site analysis"}),
                "fine_grained": ("BOOLEAN", {"default": False, "description": "Use the fine-grained segmentation preset"}),
                "output_prefix": ("STRING", {"default": "modkit_dmr"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for field in ("sample_a", "index_a", "sample_b", "index_b", "reference"):
            if path_value(inputs.get(field)) is None:
                return f"{field} is required"
        bases = split_values(inputs.get("base"))
        if not bases:
            return "At least one base is required"
        if any(base not in {"A", "C", "G", "T"} for base in bases):
            return "base values must be one of A, C, G, or T"
        if int(inputs.get("threads", 4)) < 1:
            return "threads must be at least 1"
        if inputs.get("regions") and inputs.get("segment"):
            return "segment is only available when regions is omitted"
        if inputs.get("fine_grained") and not inputs.get("segment"):
            return "fine_grained requires segment"
        return True

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
        stem = safe_output_stem(inputs.get("output_prefix"), "modkit_dmr")
        out_dir = Path(output_dir)
        paths = {
            "dmr": out_dir / f"{stem}.dmr.bed",
            "log": out_dir / f"{stem}.dmr.log",
        }
        if inputs.get("segment"):
            paths["segments"] = out_dir / f"{stem}.segments.bed"
        return paths

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        paths = cls._output_paths(inputs, node_out)
        ordered = [paths["dmr"]]
        if "segments" in paths:
            ordered.append(paths["segments"])
        ordered.append(paths["log"])
        return ordered

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, inputs: dict[str, Any], planned_paths: list[Path]) -> dict[str, Path]:
        names = ["dmr"]
        if inputs.get("segment"):
            names.append("segments")
        names.append("log")
        return dict(zip(names, planned_paths, strict=True))

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged = outputs[0].parent / "inputs"
        sample_a = staged / "sample_a.bed.gz"
        sample_b = staged / "sample_b.bed.gz"
        stage_file(str(inputs["sample_a"]), sample_a)
        stage_file(str(inputs["index_a"]), Path(f"{sample_a}.tbi"))
        stage_file(str(inputs["sample_b"]), sample_b)
        stage_file(str(inputs["index_b"]), Path(f"{sample_b}.tbi"))
        inputs["sample_a"] = str(sample_a)
        inputs["sample_b"] = str(sample_b)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        paths = cls._output_paths(inputs, inputs.get("output", "."))
        cmd = [
            "modkit",
            "dmr",
            "pair",
            "-a",
            str(inputs["sample_a"]),
            "-b",
            str(inputs["sample_b"]),
            "-o",
            str(paths["dmr"]),
            "--ref",
            str(inputs["reference"]),
        ]
        for base in split_values(inputs.get("base")):
            cmd.extend(["--base", base])
        cmd.extend(["--threads", str(inputs.get("threads", 4)), "--log-filepath", str(paths["log"])])
        if inputs.get("regions"):
            cmd.extend(["-r", str(inputs["regions"])])
        if inputs.get("segment"):
            cmd.extend(["--segment", str(paths["segments"])])
        if inputs.get("fine_grained"):
            cmd.append("--fine-grained")
        return cmd
