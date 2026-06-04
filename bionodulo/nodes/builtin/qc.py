"""Quality control nodes for BioNodulo.

Provides nodes for running FastQC, MultiQC, and QualiMap to assess
sequencing data and alignment quality.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class FastQCNode(CommandNode):
    """Run FastQC quality control on FASTQ reads."""
    NODE_ID = "fastqc"
    DISPLAY_NAME = "FastQC"
    REQUIRED_CONDA_PACKAGES = ['fastqc']
    CATEGORY = "qc"
    DESCRIPTION = "Run FastQC to generate per-base quality plots and reports"
    SEARCH_ALIASES = ["fastqc", "quality control", "qc", "reads qc"]
    RETURN_TYPES = ("QC_REPORT_DIR",)
    RETURN_NAMES = ("report_dir",)
    REQUIRED_EXECUTABLES = ["fastqc"]
    DOCUMENTATION_URL = "https://www.bioinformatics.babraham.ac.uk/projects/fastqc/"
    VERSION = "0.12.1"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        report_dir = Path(output_dir) / cls.NODE_ID / "report_dir.out"
        report_dir.mkdir(parents=True, exist_ok=True)
        return [report_dir]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        outdir = str(inputs.get("output", inputs.get("output_dir", ".")))
        outdir = f"{outdir}/report_dir.out"
        cmd = [
            "fastqc",
            "--threads", str(inputs.get("threads", 2)),
            "--outdir", outdir,
        ]
        if inputs.get("nogroup"):
            cmd.append("--nogroup")
        if inputs.get("kmers"):
            cmd.extend(["--kmers", str(inputs["kmers"])])
        if not inputs.get("extract", True):
            cmd.append("--noextract")
        if inputs.get("extract"):
            cmd.append("--extract")
        if inputs.get("format"):
            cmd.extend(["--format", str(inputs["format"])])
        if inputs.get("contaminants"):
            cmd.extend(["--contaminants", str(inputs["contaminants"])])
        if inputs.get("adapters"):
            cmd.extend(["--adapters", str(inputs["adapters"])])
        if inputs.get("limits"):
            cmd.extend(["--limits", str(inputs["limits"])])
        reads = inputs.get("reads", "")
        if isinstance(reads, list):
            cmd.extend(reads)
        else:
            cmd.append(str(reads))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "FASTQ read file(s)"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "nogroup": ("BOOLEAN", {"default": False, "description": "Disable grouping of bases", "advanced": True}),
                "kmers": ("INT", {"default": 7, "min": 2, "max": 10, "description": "K-mer length", "advanced": True}),
                "extract": ("BOOLEAN", {"default": True, "description": "Extract ZIP archive", "advanced": True}),
                "format": ("STRING", {"default": "", "description": "Format (bam, sam, bismark)", "advanced": True}),
                "contaminants": ("STRING", {"default": "", "description": "Contaminants file", "advanced": True}),
                "adapters": ("STRING", {"default": "", "description": "Adapters file", "advanced": True}),
                "limits": ("STRING", {"default": "", "description": "Limits file", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MultiQCNode(CommandNode):
    """Aggregate QC reports with MultiQC."""
    NODE_ID = "multiqc"
    DISPLAY_NAME = "MultiQC"
    REQUIRED_CONDA_PACKAGES = ['multiqc']
    CATEGORY = "qc"
    DESCRIPTION = "Aggregate multiple QC reports into a single HTML report"
    SEARCH_ALIASES = ["multiqc", "aggregate qc", "report", "summary"]
    RETURN_TYPES = ("MULTIQC_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["multiqc"]
    DOCUMENTATION_URL = "https://multiqc.info/"
    VERSION = "1.33"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        # MultiQC appends `.html` to whatever `--filename` we pass. Returning
        # the full `<filename>.html` so downstream `html_preview` nodes get a
        # real .html path (the old `report.out` returned a non-existent file
        # and silently failed the html_preview validation).
        filename = str(inputs.get("filename") or "report")
        if not filename.lower().endswith(".html"):
            filename = f"{filename}.html"
        return [Path(output_dir) / cls.NODE_ID / filename]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reports = inputs.get("reports", "")
        if isinstance(reports, str):
            reports = [reports]
        # Strip a trailing `.html` from --filename so MultiQC doesn't end up
        # producing `name.html.html` (it auto-appends the extension itself).
        filename_param = str(inputs.get("filename") or "report")
        if filename_param.lower().endswith(".html"):
            filename_param = filename_param[:-5]
        cmd = [
            "multiqc",
            *reports,
            "--outdir", str(inputs.get("output", inputs.get("output_dir", "."))),
            "--filename", filename_param,
        ]
        if inputs.get("title"):
            cmd.extend(["--title", str(inputs["title"])])
        if inputs.get("comment"):
            cmd.extend(["--comment", str(inputs["comment"])])
        if inputs.get("force"):
            cmd.append("--force")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reports": ("FILE_LIST", {"description": "Directory or list containing QC report files"}),
            },
            "optional": {
                "title": ("STRING", {"default": "BioNodulo QC Report", "label": "Report Title"}),
                "comment": ("STRING", {"default": "", "multiline": True, "label": "Comment", "advanced": True}),
                "force": ("BOOLEAN", {"default": False, "label": "Overwrite", "advanced": True}),
                "filename": ("STRING", {"default": "report", "label": "Output Filename (without extension)", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class QualiMapNode(CommandNode):
    """Run QualiMap BAM QC analysis."""
    NODE_ID = "qualimap_bamqc"
    DISPLAY_NAME = "QualiMap BAM QC"
    CATEGORY = "qc"
    DESCRIPTION = "Comprehensive BAM quality analysis with QualiMap"
    SEARCH_ALIASES = ["qualimap", "bamqc", "bam qc", "alignment qc"]
    RETURN_TYPES = ("HTML_REPORT", "QC_REPORT_DIR")
    RETURN_NAMES = ("report", "report_dir")
    REQUIRED_EXECUTABLES = ["qualimap"]
    REQUIRED_CONDA_PACKAGES = ['qualimap']
    DOCUMENTATION_URL = "http://qualimap.conesalab.org/"
    VERSION = "2.3"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [out / "report.html", out / "report_dir.out"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "qualimap", "bamqc",
            "-bam", str(inputs.get("bam", "")),
            "-outdir", f"{str(inputs.get('output', inputs.get('output_dir', '.')))}/report_dir.out",
            "-nt", str(inputs.get("threads", 2)),
        ]
        if inputs.get("feature_file"):
            cmd.extend(["-gff", str(inputs["feature_file"])])
        if inputs.get("paint_chromosome_limits"):
            cmd.append("--paint-chromosome-limits")
        if inputs.get("collect_overlap_pairs"):
            cmd.append("--collect-overlap-pairs")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM alignment file"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "feature_file": ("GFF_GTF", {"description": "Optional GFF/GTF for feature coverage", "advanced": True}),
                "paint_chromosome_limits": ("BOOLEAN", {"default": False, "advanced": True}),
                "collect_overlap_pairs": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run QualiMap and normalize its report filename."""
        result = await super().run(**kwargs)
        outputs = result.get("outputs", {}) if isinstance(result, dict) else {}
        report = Path(str(outputs.get("report", "")))
        report_dir = Path(str(outputs.get("report_dir", "")))
        src = report_dir / "qualimapReport.html"
        if src.exists():
            src.rename(report)
        return result


class QualiMapAliasNode(QualiMapNode):
    """Planner compatibility alias for QualiMap BAM QC."""
    NODE_ID = "qualimap"
    DISPLAY_NAME = "QualiMap"
    DESCRIPTION = "Run QualiMap BAM quality control for alignment reports."
    SEARCH_ALIASES = [
        "qualimap",
        "bamqc",
        "bam qc",
        "alignment qc",
        "quality report",
    ]
