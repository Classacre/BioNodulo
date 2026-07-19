"""Focused breseq node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class BreseqNode(CommandNode):
    """Detect and annotate mutations in haploid microbial resequencing data with breseq."""

    NODE_ID = "breseq"
    DISPLAY_NAME = "breseq"
    REQUIRED_CONDA_PACKAGES = ["breseq", "tar"]
    CATEGORY = "variant"
    DESCRIPTION = "Find mutations in haploid microbial genomes and annotate GenomeDiff variants with breseq and gdtools."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "breseq",
        "breseq mutation detection",
        "GenomeDiff",
        "gdtools ANNOTATE",
        "microbial resequencing",
        "haploid microbial genomes",
        "laboratory evolution",
    ]
    RETURN_TYPES = ("HTML_REPORT", "HTML_REPORT", "TSV", "TSV", "ZIP", "TXT", "TSV", "PHYLIP", "JSON")
    RETURN_NAMES = ("report", "annreport", "output", "genomediff", "zip_output", "log", "tabdelim", "phylipout", "jsonout")
    REQUIRED_EXECUTABLES = ["breseq", "gdtools", "tar"]
    DOCUMENTATION_URL = "https://barricklab.org/twiki/bin/view/Lab/ToolsBacterialGenomeResequencing"
    CITATION_DOIS = ["10.1007/978-1-4939-0554-6_12"]
    CITATION_URLS = [f"{DOI_URL}10.1007/978-1-4939-0554-6_12"]
    CITATION_TEXT = "Identification of mutations in laboratory-evolved microbes from next-generation sequencing data using breseq."
    VERSION = "0.35.5"
    SHELL = True

    DETECT_OUTPUTS = {
        "html": "report.html",
        "gd": "output.gd",
        "zip": "results.tar.gz",
        "log": "log.txt",
    }
    ANNOTATE_OUTPUTS = {
        "html": "annotated_report.html",
        "gd": "annotated.gd",
        "tsv": "annotated.tsv",
        "phylip": "comparison.phy",
        "json": "annotated.json",
    }

    @classmethod
    def _formats(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("formats", inputs.get("output_formats"))
        if raw is None or raw == "":
            return ["phylip"] if str(inputs.get("mode", "detect")) == "compare" else ["gd"]
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return [str(value) for value in raw if str(value)]

    @classmethod
    def _references(cls, inputs: dict[str, Any]) -> list[str]:
        refs = _as_list(inputs.get("references", inputs.get("own_genome")))
        refs.extend(_as_list(inputs.get("fixed_references", inputs.get("fixed_genome"))))
        return refs

    @classmethod
    def _add_references(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for reference in cls._references(inputs):
            cmd.extend(["--reference", reference])

    @classmethod
    def _detect_command(cls, inputs: dict[str, Any], out: str) -> list[str]:
        results_dir = f"{out}/results"
        cmd = ["breseq", "--num-processors", f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}", "-o", results_dir]
        cls._add_references(cmd, inputs)
        cmd.extend(_as_list(inputs.get("fastqs", inputs.get("reads"))))
        if inputs.get("name"):
            cmd.extend(["--name", str(inputs.get("name"))])
        polymorphism = inputs.get("polymorphism_prediction")
        if isinstance(polymorphism, str):
            if polymorphism.strip():
                cmd.append(polymorphism)
        elif polymorphism:
            cmd.append("--polymorphism-prediction")
        if inputs.get("predict_junctions") is False:
            cmd.append("--no-junction-prediction")

        formats = set(cls._formats(inputs))
        if "gd" in formats:
            cmd.extend(["&&", "cp", f"{results_dir}/output/output.gd", f"{out}/output.gd"])
        if "html" in formats:
            cmd.extend(
                [
                    "&&",
                    "cp",
                    f"{results_dir}/output/index.html",
                    f"{out}/report.html",
                    "&&",
                    "mkdir",
                    "-p",
                    f"{out}/report_extra_files",
                    "&&",
                    "cp",
                    "-R",
                    f"{results_dir}/output/.",
                    f"{out}/report_extra_files",
                ]
            )
        if "zip" in formats:
            cmd.extend(["&&", "tar", "-zcf", f"{out}/results.tar.gz", results_dir])
        if "log" in formats:
            cmd.extend(["&&", "cp", f"{results_dir}/output/log.txt", f"{out}/log.txt"])
        return cmd

    @classmethod
    def _annotate_output(cls, output_format: str, out: str) -> str:
        return f"{out}/{cls.ANNOTATE_OUTPUTS.get(output_format, f'annotated.{output_format}')}"

    @classmethod
    def _annotate_command(cls, inputs: dict[str, Any], out: str) -> list[str]:
        commands: list[str] = []
        for index, output_format in enumerate(cls._formats(inputs)):
            if index:
                commands.append("&&")
            commands.extend(["gdtools", "ANNOTATE", "--format", output_format, "-o", cls._annotate_output(output_format, out)])
            cls._add_references(commands, inputs)
            commands.extend(_as_list(inputs.get("gds", inputs.get("genomediffs"))))
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        if str(inputs.get("mode", "detect")) == "detect":
            return cls._detect_command(inputs, out)
        return cls._annotate_command(inputs, out)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        formats = set(cls._formats(inputs))
        if str(inputs.get("mode", "detect")) == "detect":
            return [out / cls.DETECT_OUTPUTS[fmt] for fmt in ["html", "gd", "zip", "log"] if fmt in formats]
        return [out / cls.ANNOTATE_OUTPUTS[fmt] for fmt in ["html", "gd", "tsv", "phylip", "json"] if fmt in formats]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "references": (
                    "FILE_LIST",
                    {"multiple": True, "description": "One or more FASTA or GenBank reference genomes"},
                ),
            },
            "optional": {
                "mode": ("STRING", {"default": "detect", "options": ["detect", "annotate", "compare"], "description": "Run breseq variant detection or gdtools annotation/comparison"}),
                "fastqs": ("FASTQ_LIST", {"description": "FASTQ reads for detect mode"}),
                "gds": ("TSV_LIST", {"description": "GenomeDiff files for annotate or compare mode"}),
                "formats": ("STRING_LIST", {"description": "Output formats selected in the Galaxy wrapper"}),
                "polymorphism_prediction": (
                    "BOOLEAN",
                    {"default": False, "description": "Detect polymorphic variants rather than consensus mutations"},
                ),
                "name": ("STRING", {"default": "", "description": "Human-readable analysis name"}),
                "predict_junctions": ("BOOLEAN", {"default": True, "description": "Predict new sequence junctions"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._references(inputs):
            return "at least one reference genome is required"
        mode = str(inputs.get("mode", "detect"))
        if mode == "detect" and not _as_list(inputs.get("fastqs", inputs.get("reads"))):
            return "at least one FASTQ read file is required for detect mode"
        if mode in {"annotate", "compare"}:
            gds = _as_list(inputs.get("gds", inputs.get("genomediffs")))
            if not gds:
                return "at least one GenomeDiff input is required for annotate or compare mode"
            if mode == "compare" and len(gds) < 2:
                return "compare mode requires at least two GenomeDiff inputs"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(BreseqNode)

__all__ = ['BreseqNode']
