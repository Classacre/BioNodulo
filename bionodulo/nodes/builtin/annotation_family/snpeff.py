"""SnpEff 5.2 effect annotation with an explicit local genome database."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    AnnotationCommandNode,
    path_value,
    validate_exact_path,
    validate_int,
)


class SnpEffNode(AnnotationCommandNode):
    """Annotate a VCF using one explicitly staged SnpEff predictor database."""

    NODE_ID = "snpeff"
    DISPLAY_NAME = "SnpEff"
    DESCRIPTION = "Annotate VCF records and predict variant effects with SnpEff 5.2."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "SnpEff",
        "variant annotation",
        "effect prediction",
        "functional effect",
    ]
    RETURN_TYPES = ("VCF", "HTML_REPORT", "TSV")
    RETURN_NAMES = ("annotated_vcf", "summary_report", "genes_report")
    OUTPUT_FILENAMES = (
        "annotated_vcf.vcf",
        "summary_report.html",
        "summary_report.genes.txt",
    )
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["snpEff"]
    REQUIRED_CONDA_PACKAGES = ["snpeff", "openjdk"]
    CONDA_PACKAGE_CONSTRAINTS = {"snpeff": "5.2", "openjdk": "17.*"}
    VERSION = "5.2"
    GIT_URL = "https://github.com/pcingola/SnpEff.git"
    GIT_COMMIT = "0c5e74f9b6ca6ed3db720177eb1f95b9d47d45f2"
    DOCUMENTATION_URL = "https://pcingola.github.io/SnpEff/snpeff/running/"
    SOURCE_URL = (
        "https://github.com/pcingola/SnpEff/blob/v5.2/src/main/java/org/snpeff/snpEffect/commandLine/SnpEffCmdEff.java"
    )
    UPSTREAM_SOURCE = (
        "scripts/snpEff; src/main/java/org/snpeff/SnpEff.java; "
        "src/main/java/org/snpeff/snpEffect/commandLine/SnpEffCmdEff.java"
    )
    CITATION_DOIS = ["10.4161/fly.19695"]
    CITATION_URLS = ["https://doi.org/10.4161/fly.19695"]
    CITATION_TEXT = "A program for annotating and predicting the effects of SNPs."
    REQUIRED_PATH_INPUTS = ("vcf", "data_dir", "database")
    EXIT_SEMANTICS = (
        "SnpEff reports invalid options, unreadable VCFs, missing configs, and missing predictor "
        "databases as fatal errors; annotated VCF is captured directly from stdout."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (("VCF", "VCF_GZ"), {"description": "Input VCF or bgzip-compressed VCF"}),
                "genome": ("STRING", {"description": "SnpEff genome version identifier"}),
                "data_dir": ("DIRECTORY", {"description": "Root SnpEff data directory"}),
                "database": (
                    "FILE",
                    {"description": ("Exact <data_dir>/<genome>/snpEffectPredictor.bin database artifact")},
                ),
            },
            "optional": {
                "memory": ("INT", {"default": 8, "min": 1, "max": 128}),
                "canonical": ("BOOLEAN", {"default": False}),
                "no_upstream": ("BOOLEAN", {"default": False}),
                "no_downstream": ("BOOLEAN", {"default": False}),
                "no_intergenic": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        genome = str(inputs.get("genome", "")).strip()
        if not genome or "/" in genome or "\\" in genome or genome in {".", ".."}:
            return "Input 'genome' must be a non-empty SnpEff genome identifier"
        validation = validate_int(inputs.get("memory", 8), "memory", minimum=1, maximum=128)
        if validation is not True:
            return validation
        expected = Path(path_value(inputs["data_dir"])) / genome / "snpEffectPredictor.bin"
        return validate_exact_path(inputs.get("database"), expected, "database")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "snpEff",
            f"-Xmx{inputs.get('memory', 8)}g",
            "-noLog",
            "-v",
            "-dataDir",
            path_value(inputs["data_dir"]),
            "-stats",
            str(output / cls.OUTPUT_FILENAMES[1]),
        ]
        if inputs.get("canonical", False):
            command.append("-canon")
        if inputs.get("no_upstream", False):
            command.append("-no-upstream")
        if inputs.get("no_downstream", False):
            command.append("-no-downstream")
        if inputs.get("no_intergenic", False):
            command.append("-no-intergenic")
        command.extend([str(inputs["genome"]), path_value(inputs["vcf"])])
        return command
