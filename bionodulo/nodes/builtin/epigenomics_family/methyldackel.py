"""MethylDackel 0.6.1 extraction with explicit BAM/FASTA sidecars."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index
from bionodulo.nodes.builtin._reference_sidecars import validate_colocated_reference_index

from .adapter import EpigenomicsCommandNode, path_value, safe_output_stem, stage_file


class MethylDackelNode(EpigenomicsCommandNode):
    """Run text-mode M-bias QC and extract CpG bedGraph metrics."""

    NODE_ID = "methyldackel"
    DISPLAY_NAME = "MethylDackel"
    DESCRIPTION = "Extract CpG methylation metrics and a tabular M-bias report from indexed bisulfite alignments."
    SEARCH_ALIASES = ["methyldackel", "pileometh", "methylation", "bisulfite", "cpg", "extract"]
    RETURN_TYPES = ("BED", "TSV")
    RETURN_NAMES = ("methylation_bedgraph", "mbias_report")
    REQUIRED_EXECUTABLES = ["MethylDackel"]
    REQUIRED_CONDA_PACKAGES = ["methyldackel"]
    SHELL = True
    SIDECAR_POLICY = (
        "The BAM/BAI and FASTA/FAI inputs must be exact colocated siblings before "
        "they are staged under canonical names; MethylDackel 0.6.1 discovers both "
        "indexes by filename."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted bisulfite BAM"}),
                "bam_index": ("BAI", {"description": "BAI matching bam"}),
                "reference": ("FASTA", {"description": "Uncompressed reference FASTA"}),
                "reference_index": ("FASTA_INDEX", {"description": "FAI matching reference"}),
                "output_prefix": ("STRING", {"default": "methyldackel"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
                "merge_context": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Merge per-Cytosine metrics into per-CpG/CHG metrics",
                    },
                ),
                "min_depth": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "label": "Min Coverage",
                        "description": "Minimum coverage after filtering; applies to merged sites too",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for field in ("bam", "bam_index", "reference", "reference_index"):
            if path_value(inputs.get(field)) is None:
                return f"{field} is required"

        sidecar_validation = validate_colocated_bam_index(inputs)
        if sidecar_validation is not True:
            return sidecar_validation
        sidecar_validation = validate_colocated_reference_index(inputs)
        if sidecar_validation is not True:
            return sidecar_validation

        threads_value = inputs.get("threads", 1)
        if threads_value is None:
            threads_value = 1
        if isinstance(threads_value, bool) or not isinstance(threads_value, int):
            return "threads must be an integer"
        threads = threads_value
        if threads < 1:
            return "threads must be at least 1"

        min_depth_value = inputs.get("min_depth", 1)
        if min_depth_value is None:
            min_depth_value = 1
        if isinstance(min_depth_value, bool) or not isinstance(min_depth_value, int):
            return "min_depth must be an integer"
        min_depth = min_depth_value
        if min_depth < 1:
            return "min_depth must be at least 1"
        return True

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        stem = safe_output_stem(inputs.get("output_prefix"), "methyldackel")
        prefix = Path(output_dir) / stem
        return Path(f"{prefix}_CpG.bedGraph"), Path(f"{prefix}_mbias.tsv")

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._output_paths(inputs, node_out))

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        staged = outputs[0].parent / "inputs"
        staged_bam = staged / "alignment.bam"
        staged_reference = staged / "reference.fa"
        stage_file(str(inputs["bam"]), staged_bam)
        stage_file(str(inputs["bam_index"]), Path(f"{staged_bam}.bai"))
        stage_file(str(inputs["reference"]), staged_reference)
        stage_file(str(inputs["reference_index"]), Path(f"{staged_reference}.fai"))
        inputs["bam"] = str(staged_bam)
        inputs["reference"] = str(staged_reference)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output_bedgraph, output_mbias = cls._output_paths(inputs, inputs.get("output", "."))
        output_prefix = str(output_bedgraph).removesuffix("_CpG.bedGraph")
        reference = str(inputs["reference"])
        bam = str(inputs["bam"])
        threads = str(inputs.get("threads", 1))
        cmd = [
            "MethylDackel",
            "mbias",
            "--noSVG",
            "-@",
            threads,
            reference,
            bam,
            ">",
            str(output_mbias),
            "&&",
            "MethylDackel",
            "extract",
            "-@",
            threads,
            "-o",
            output_prefix,
        ]
        if inputs.get("merge_context", False):
            cmd.append("--mergeContext")
        cmd.extend(["--minDepth", str(inputs.get("min_depth", 1)), reference, bam])
        return cmd
