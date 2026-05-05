from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.command_node import CommandNode


class FastpNode(CommandNode):
    NODE_ID = "fastp"
    DISPLAY_NAME = "fastp"
    CATEGORY = "Read preprocessing"
    DESCRIPTION = "Trim adapters and filter FASTQ reads using fastp."
    SEARCH_ALIASES = ["trim", "filter reads", "fastq trim", "adapter trimming", "fastp"]
    RETURN_TYPES = ("FASTQ_LIST", "HTML_REPORT", "JSON_REPORT", "QC_REPORT_DIR")
    RETURN_NAMES = ("trimmed_reads", "html_report", "json_report", "report_dir")
    REQUIRED_EXECUTABLES = ["fastp"]
    DOCUMENTATION_URL = "https://github.com/OpenGene/fastp"
    COMMAND = [
        "fastp",
        "-i",
        "{inputs.reads[0]}",
        "-I",
        "{inputs.reads[1]}",
        "-o",
        "{outputs.trimmed_reads[0]}",
        "-O",
        "{outputs.trimmed_reads[1]}",
        "--html",
        "{outputs.html_report}",
        "--json",
        "{outputs.json_report}",
        "--thread",
        "{params.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {"reads": ("FASTQ_LIST", {"description": "Paired-end FASTQ files"})},
            "optional": {"threads": ("INT", {"default": 4, "min": 1, "max": 64})},
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {
            "trimmed_reads": [str(node_dir / "trimmed_R1.fastq.gz"), str(node_dir / "trimmed_R2.fastq.gz")],
            "html_report": str(node_dir / "fastp.html"),
            "json_report": str(node_dir / "fastp.json"),
            "report_dir": str(node_dir),
        }
