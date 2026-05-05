from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.command_node import CommandNode


class FastQCNode(CommandNode):
    NODE_ID = "fastqc"
    DISPLAY_NAME = "FastQC"
    CATEGORY = "Quality Control"
    DESCRIPTION = "Run FastQC on FASTQ files and pass reads through for downstream steps."
    SEARCH_ALIASES = ["qc", "quality control", "fastq qc", "read quality", "quality"]
    RETURN_TYPES = ("QC_REPORT_DIR", "FASTQ_LIST")
    RETURN_NAMES = ("report_dir", "reads")
    REQUIRED_EXECUTABLES = ["fastqc"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/fastqc/"
    COMMAND = ["fastqc", "--threads", "{params.threads}", "--outdir", "{outputs.report_dir}", "{inputs.reads[0]}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {"reads": ("FASTQ_LIST", {"description": "Input FASTQ or FASTQ.GZ files"})},
            "optional": {"threads": ("INT", {"default": 4, "min": 1, "max": 64})},
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {"report_dir": str(node_dir / "fastqc_reports"), "reads": inputs.get("reads", [])}


class MultiQCNode(CommandNode):
    NODE_ID = "multiqc"
    DISPLAY_NAME = "MultiQC"
    CATEGORY = "Quality Control"
    DESCRIPTION = "Aggregate QC reports into a MultiQC HTML report."
    SEARCH_ALIASES = ["multiqc", "qc summary", "aggregate reports", "quality"]
    RETURN_TYPES = ("MULTIQC_REPORT", "QC_REPORT_DIR")
    RETURN_NAMES = ("report", "report_dir")
    OUTPUT_NODE = True
    REQUIRED_EXECUTABLES = ["multiqc"]
    DOCUMENTATION_URL = "https://multiqc.info/"
    COMMAND = ["multiqc", "{inputs.reports}", "--outdir", "{outputs.report_dir}", "--filename", "multiqc_report.html"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {"reports": ("DIRECTORY", {"description": "Directory containing FastQC/fastp reports"})},
            "optional": {},
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        report_dir = node_dir / "multiqc"
        return {"report": str(report_dir / "multiqc_report.html"), "report_dir": str(report_dir)}
