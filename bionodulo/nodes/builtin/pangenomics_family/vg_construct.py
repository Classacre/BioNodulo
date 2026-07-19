"""Stable owner for ``vg_construct``."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .common import _path_value, _positive_int, _stage_file
from .evidence import PangenomicsCommandContract


class VGConstructNode(PangenomicsCommandContract):
    """Construct variation graphs from a reference FASTA and VCF."""
    NODE_ID = "vg_construct"
    DISPLAY_NAME = "vg Construct"
    CATEGORY = "pangenomics"
    DESCRIPTION = "Construct a variation graph from reference FASTA and VCF variants. Foundation for pangenome alignment."
    SEARCH_ALIASES = ["vg", "construct", "variation graph", "pangenome", "graph genome"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("vg_graph",)
    REQUIRED_EXECUTABLES = ["vg"]
    REQUIRED_CONDA_PACKAGES = ["vg"]
    DOCUMENTATION_URL = "https://github.com/vgteam/vg"
    VERSION = "1.62.0"
    SHELL = True
    SIDECAR_POLICY = (
        "vg 1.63.1 fastahack reads <reference>.fai when present and otherwise writes a new sibling index. "
        "BioNodulo stages the reference in a writable node-local directory so no invented reference-index port is needed. "
        "The vendored vcflib/tabixpp path requires an exact <compressed-vcf>.tbi sibling, exposed as vcf_index."
    )

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ("reference", "vcf"):
            if not _path_value(inputs.get(name)):
                return f"{name} must be a non-empty path-like value"
        reference = _path_value(inputs.get("reference")).lower()
        if reference.endswith((".gz", ".bgz")):
            return "reference must be an uncompressed FASTA because vg fastahack opens it as plain text"
        vcf = _path_value(inputs.get("vcf"))
        compressed_vcf = vcf.lower().endswith((".gz", ".bgz"))
        vcf_index = _path_value(inputs.get("vcf_index"))
        if compressed_vcf and not vcf_index:
            return "vcf_index is required for a bgzip-compressed VCF"
        if not compressed_vcf and vcf_index:
            return "vcf_index is only valid when vcf is bgzip-compressed"
        for name, default in (("max_node_size", 32), ("threads", 1)):
            validation = _positive_int(inputs.get(name, default), name, default)
            if isinstance(validation, str):
                return validation
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        stage_root = outputs[0].parent / "inputs"
        if stage_root.exists():
            shutil.rmtree(stage_root)

        staged_reference = stage_root / "reference.fa"
        _stage_file(Path(_path_value(inputs["reference"])), staged_reference)
        inputs["reference"] = str(staged_reference)

        source_vcf = Path(_path_value(inputs["vcf"]))
        compressed_vcf = source_vcf.name.lower().endswith((".gz", ".bgz"))
        staged_vcf = stage_root / ("variants.vcf.gz" if compressed_vcf else "variants.vcf")
        _stage_file(source_vcf, staged_vcf)
        inputs["vcf"] = str(staged_vcf)
        if compressed_vcf:
            _stage_file(Path(_path_value(inputs["vcf_index"])), Path(f"{staged_vcf}.tbi"))
            inputs["vcf_index"] = f"{staged_vcf}.tbi"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = inputs.get("output", ".")
        cmd = [
            "vg",
            "construct",
            "-r",
            str(inputs.get("reference", "")),
            "-v",
            str(inputs.get("vcf", "")),
        ]
        if inputs.get("alt_paths", True):
            cmd.append("-a")
        if inputs.get("flat_alts", True):
            cmd.append("-f")
        if inputs.get("handle_sv", True):
            cmd.append("-S")
        if inputs.get("region"):
            cmd.extend(["-R", str(inputs["region"])])
        cmd.extend(["-m", str(inputs.get("max_node_size", 32))])
        cmd.extend(["-t", str(inputs.get("threads", 1))])
        if inputs.get("progress"):
            cmd.append("-p")
        cmd.extend([">", f"{out_dir}/vg_graph.vg"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "vg_graph.vg"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "vcf": ("FILE", {"description": "Plain or bgzip-compressed VCF to embed"}),
            },
            "optional": {
                "vcf_index": (
                    "VCF_INDEX",
                    {
                        "default": "",
                        "description": "Exact tabix <vcf>.tbi sidecar required when vcf is bgzip-compressed",
                    },
                ),
                "region": ("STRING", {"default": "", "description": "Region (e.g., chr1:1-1000000)"}),
                "max_node_size": ("INT", {"default": 32, "min": 1}),
                "threads": ("INT", {"default": 1, "min": 1}),
                "alt_paths": ("BOOLEAN", {"default": True, "description": "Retain hashed alternate paths (-a)"}),
                "flat_alts": ("BOOLEAN", {"default": True, "description": "Do not chop alternate alleles (-f)"}),
                "handle_sv": ("BOOLEAN", {"default": True, "description": "Include structural variants (-S)"}),
                "progress": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
