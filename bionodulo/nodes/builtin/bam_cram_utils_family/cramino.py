"""Cramino 1.3.0 long-read BAM/CRAM metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import CraminoCommandNode, GALAXY_ALIAS, output_dir, path_value


def metrics_name(inputs: dict[str, Any]) -> str:
    return {"json": "metrics.json", "tsv": "metrics.tsv", "text": "metrics.txt"}.get(
        str(inputs.get("outfmt", "text")),
        "metrics.txt",
    )


class CraminoNode(CraminoCommandNode):
    NODE_ID = "cramino"
    DISPLAY_NAME = "Cramino"
    CATEGORY = "qc"
    DESCRIPTION = "Extract long-read BAM/CRAM summary metrics and optional histogram or Arrow artifacts"
    SEARCH_ALIASES = [GALAXY_ALIAS, "cramino", "BAM CRAM QC", "long read QC", "NanoPack2"]
    RETURN_TYPES = ("STATS_FILE", "FILE", "TSV")
    RETURN_NAMES = ("metrics", "arrow_output", "histogram")
    STDOUT_OUTPUT_INDEX = 0

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("BAM", {"description": "BAM or CRAM file to inspect"})},
            "optional": {
                "reference": ("FASTA", {"default": "", "description": "Reference FASTA for CRAM"}),
                "threads": ("INT", {"default": 4, "min": 1}),
                "ubam": ("BOOLEAN", {"default": False}),
                "spliced": ("BOOLEAN", {"default": False}),
                "phased": ("BOOLEAN", {"default": False}),
                "karyotype": ("BOOLEAN", {"default": False}),
                "min_read_len": ("INT", {"default": 0, "min": 0}),
                "outfmt": ("STRING", {"default": "text", "options": ["text", "json", "tsv"]}),
                "arrow": ("BOOLEAN", {"default": False}),
                "histtype": ("STRING", {"default": "no", "options": ["no", "hist", "hist_count"]}),
                "scaled": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir_: str | Path) -> list[Path]:
        node_out = Path(output_dir_) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / metrics_name(inputs)]
        if inputs.get("arrow"):
            outputs.append(node_out / "reads.arrow")
        histtype = str(inputs.get("histtype", "no"))
        if histtype == "hist":
            outputs.append(node_out / "histogram.txt")
        elif histtype == "hist_count":
            outputs.append(node_out / "histogram_counts.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(inputs.get("input_file")) is None:
            return "input_file must be a non-empty path-like value"
        if inputs.get("reference") not in (None, "") and path_value(inputs.get("reference")) is None:
            return "reference must be a non-empty path-like value when supplied"
        threads = inputs.get("threads", 4)
        if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
            return "threads must be a positive integer"
        if str(inputs.get("outfmt", "text")) not in {"text", "json", "tsv"}:
            return "outfmt must be one of: text, json, tsv"
        if str(inputs.get("histtype", "no")) not in {"no", "hist", "hist_count"}:
            return "histtype must be one of: no, hist, hist_count"
        minimum = inputs.get("min_read_len", 0)
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
            return "min_read_len must be a non-negative integer"
        if inputs.get("scaled") and str(inputs.get("histtype", "no")) == "no":
            return "scaled requires hist or hist_count output"
        if inputs.get("ubam") and any(inputs.get(key) for key in ("spliced", "phased", "karyotype")):
            return "ubam cannot be combined with spliced, phased, or karyotype metrics"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = output_dir(inputs)
        command = [
            "cramino",
            str(inputs.get("input_file", "")),
            "--threads",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("reference"):
            command.extend(["--reference", str(inputs["reference"])])
        for key, flag in (
            ("ubam", "--ubam"),
            ("spliced", "--spliced"),
            ("phased", "--phased"),
            ("karyotype", "--karyotype"),
        ):
            if inputs.get(key):
                command.append(flag)
        if inputs.get("min_read_len") not in (None, "", 0):
            command.extend(["--min-read-len", str(inputs["min_read_len"])])
        command.extend(["--format", str(inputs.get("outfmt", "text"))])
        if inputs.get("arrow"):
            command.extend(["--arrow", str(out / "reads.arrow")])
        histtype = str(inputs.get("histtype", "no"))
        if histtype == "hist":
            command.append(f"--hist={out / 'histogram.txt'}")
        elif histtype == "hist_count":
            command.append(f"--hist-count={out / 'histogram_counts.tsv'}")
        if histtype != "no" and inputs.get("scaled"):
            command.append("--scaled")
        return command


__all__ = ["CraminoNode", "metrics_name"]
