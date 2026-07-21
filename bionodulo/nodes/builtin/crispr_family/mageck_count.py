"""MAGeCK 0.5.9.5 guide-count collection contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MageckCommandNode,
    mageck_read_paths,
    path_list,
    path_value,
    require_materialized_file,
    validate_output_prefix,
)


class MAGeCKCountNode(MageckCommandNode):
    """Count library sgRNAs from one or more FASTQ/SAM/BAM samples."""

    NODE_ID = "mageck_count"
    DISPLAY_NAME = "MAGeCK Count"
    DESCRIPTION = "Count sgRNA reads for pooled CRISPR screens and emit native raw and normalized count tables."
    SEARCH_ALIASES = ["BioNodulo builtin", "MAGeCK", "count", "CRISPR screen", "sgRNA", "pooled screen"]
    RETURN_TYPES = ("TSV", "TSV", "TSV")
    RETURN_NAMES = ("count_table", "normalized_counts", "count_summary")
    REQUIRED_EXECUTABLES = ["mageck", "RRA", "mageckGSEA"]
    REQUIRED_PATH_INPUTS = ("library_file",)
    REQUIRED_PATH_LIST_INPUTS = ("fastq_files",)
    UPSTREAM_SOURCE = (
        "mageck/argsParser.py:arg_count; mageck/mageckCount.py:mageckcount_main; "
        "mageck/mageckCountQC.py:mageckcount_printstat and day0 subprocesses"
    )
    DEFAULT_NORMALIZATION = "median"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "library_file": ("FILE", {"description": "sgRNA ID, sequence, and gene library"}),
                "fastq_files": (
                    "FILE",
                    {
                        "multiple": True,
                        "description": (
                            "FASTQ, gzip FASTQ, SAM, or BAM inputs; one argv entry per sample, "
                            "with commas denoting technical replicates"
                        ),
                    },
                ),
            },
            "optional": {
                "output_prefix": ("STRING", {"default": "sample1"}),
                "sample_labels": ("STRING", {"default": "", "description": "Comma-separated sample labels"}),
                "day0_label": ("STRING", {"default": "", "description": "Control label for negative-selection QC"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "sample1"))
        return [
            node_dir / f"{prefix}.count.txt",
            node_dir / f"{prefix}.count_normalized.txt",
            node_dir / f"{prefix}.countsummary.txt",
        ]

    @staticmethod
    def _sample_labels(value: Any) -> str:
        if isinstance(value, (list, tuple)):
            return ",".join(str(label) for label in value)
        return str(value or "")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_output_prefix(inputs.get("output_prefix", "sample1"))
        if validation is not True:
            return validation
        fastq_files = path_list(inputs.get("fastq_files"))
        if not mageck_read_paths(inputs.get("fastq_files")):
            return "Input 'fastq_files' must contain non-empty sample and technical-replicate paths"
        labels = cls._sample_labels(inputs.get("sample_labels", ""))
        label_list = labels.split(",") if labels else []
        if label_list and (any(not label for label in label_list) or len(label_list) != len(fastq_files)):
            return "Input 'sample_labels' must contain exactly one non-empty label per FASTQ sample"
        day0 = str(inputs.get("day0_label", "") or "")
        if day0:
            if not label_list:
                return "Input 'day0_label' requires explicit sample_labels"
            day0_labels = day0.split(",")
            if any(not label for label in day0_labels) or any(label not in label_list for label in day0_labels):
                return "Input 'day0_label' values must match sample_labels"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        require_materialized_file(inputs.get("library_file"), "library_file", allow_empty=True)
        for member in mageck_read_paths(inputs.get("fastq_files")):
            require_materialized_file(member, "fastq_files")
        if len(outputs) != len(cls.RETURN_TYPES):
            raise ValueError("mageck_count requires raw, normalized, and count-summary outputs")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        prefix = str(inputs.get("output_prefix", "sample1"))
        command = cls.checked_command(
            inputs,
            "mageck",
            "count",
            "-l",
            path_value(inputs.get("library_file")),
            "-n",
            str(output_dir / prefix),
            "--fastq",
        )
        command.extend(path_list(inputs.get("fastq_files")))
        labels = cls._sample_labels(inputs.get("sample_labels", ""))
        if labels:
            command.extend(["--sample-label", labels])
        if inputs.get("day0_label") not in (None, ""):
            command.extend(["--day0-label", str(inputs["day0_label"])])
        return command
