"""FreeBayes 1.3.10 haplotype-based small-variant calling."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import IndexedBamReferenceNode, option_value, validate_integer


class FreeBayesNode(IndexedBamReferenceNode):
    """Call variants with FreeBayes using its native VCF file output option."""

    NODE_ID = "freebayes"
    DISPLAY_NAME = "FreeBayes"
    DESCRIPTION = "Bayesian haplotype-based small-variant caller"
    SEARCH_ALIASES = ["freebayes", "variant caller", "bayesian", "snp", "indel"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    OUTPUT_FILENAMES = ("vcf.vcf",)
    REQUIRED_EXECUTABLES = ["freebayes"]
    REQUIRED_CONDA_PACKAGES = ["freebayes"]
    DOCUMENTATION_URL = "https://github.com/freebayes/freebayes"
    VERSION = "1.3.10"
    GIT_URL = "https://github.com/freebayes/freebayes.git"
    GIT_COMMIT = "b0d8efd9fa7f6612c883ec5ff79e4d17a0c29993"
    SOURCE_URL = f"https://github.com/freebayes/freebayes/tree/{GIT_COMMIT}"
    PACKAGE_CONSTRAINTS = ("freebayes==1.3.10",)
    PACKAGE_CONSTRAINT = "freebayes==1.3.10"
    EXIT_SEMANTICS = "Input validation or a non-zero FreeBayes result fails the node."
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_URLS = ["https://arxiv.org/abs/1207.3907"]
    CITATION_TEXT = "Haplotype-based variant detection from short-read sequencing."
    UPSTREAM_SOURCE = "src/Parameters.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted input BAM"}),
                "bam_index": (
                    "BAI",
                    {"description": "Exact <bam>.bai index for the input BAM"},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with a colocated FAI"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai index"},
                ),
            },
            "optional": {
                "pooled": (
                    "BOOLEAN",
                    {"default": False, "description": "Enable pooled-continuous calling"},
                ),
                "ploidy": ("INT", {"default": 2, "min": 1}),
                "min_mapping_quality": (
                    "INT",
                    {"default": 1, "min": 0, "advanced": True},
                ),
                "min_base_quality": (
                    "INT",
                    {"default": 0, "min": 0, "advanced": True},
                ),
                "haplotype_length": (
                    "INT",
                    {"default": 3, "min": 0, "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "freebayes",
            "-f",
            str(inputs["reference"]),
            "-v",
            str(output / cls.OUTPUT_FILENAMES[0]),
        ]
        if option_value(inputs, "pooled", False):
            command.append("-K")
        command.extend(
            [
                "-p",
                str(option_value(inputs, "ploidy", 2)),
                "-m",
                str(option_value(inputs, "min_mapping_quality", 1)),
                "-q",
                str(option_value(inputs, "min_base_quality", 0)),
                "--haplotype-length",
                str(option_value(inputs, "haplotype_length", 3)),
                str(inputs["bam"]),
            ]
        )
        return command

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("ploidy", 2, 1, None),
            ("min_mapping_quality", 1, 0, None),
            ("min_base_quality", 0, 0, None),
            ("haplotype_length", 3, 0, None),
        ):
            validation = validate_integer(
                inputs,
                key,
                default,
                minimum=minimum,
                maximum=maximum,
            )
            if validation is not True:
                return validation
        return True
