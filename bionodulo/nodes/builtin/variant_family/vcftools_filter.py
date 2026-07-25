"""VCFtools 0.1.17 filtering with native recoded-VCF output."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .adapter import VariantCommandNode


VCFTOOLS_COMMIT = "1c53c3c73be141103069965403e655536dda9c87"


def _validate_optional_number(
    inputs: dict[str, Any],
    key: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> bool | str:
    value = inputs.get(key)
    if value is None:
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{key} must be a number"
    numeric = float(value)
    if not math.isfinite(numeric):
        return f"{key} must be finite"
    if numeric < minimum:
        return f"{key} must be at least {minimum:g}"
    if maximum is not None and numeric > maximum:
        return f"{key} must be at most {maximum:g}"
    return True


class VcfToolsFilterNode(VariantCommandNode):
    """Apply selected VCFtools site filters and recode to VCF."""

    NODE_ID = "vcftools_filter"
    DISPLAY_NAME = "VCFtools Filter"
    DESCRIPTION = "Apply selected VCFtools site filters and write a recoded VCF"
    SEARCH_ALIASES = ["vcftools", "filter", "vcf", "recode"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("filtered_vcf",)
    OUTPUT_FILENAMES = ("filtered.recode.vcf",)
    REQUIRED_EXECUTABLES = ["vcftools"]
    REQUIRED_CONDA_PACKAGES = ["vcftools"]
    VERSION = "0.1.17"
    GIT_URL = "https://github.com/vcftools/vcftools.git"
    GIT_COMMIT = VCFTOOLS_COMMIT
    SOURCE_REF = "v0.1.17"
    SOURCE_URL = "https://github.com/vcftools/vcftools/tree/v0.1.17"
    PINNED_SOURCE_URL = f"https://github.com/vcftools/vcftools/tree/{VCFTOOLS_COMMIT}"
    DOCUMENTATION_URL = (
        f"https://github.com/vcftools/vcftools/blob/{VCFTOOLS_COMMIT}/src/cpp/vcftools.1"
    )
    PACKAGE_CONSTRAINTS = ("vcftools==0.1.17",)
    PACKAGE_CONSTRAINT = "vcftools==0.1.17"
    EXIT_SEMANTICS = (
        "Exposed values are validated before execution; non-zero results and a missing "
        "filtered.recode.vcf fail the node. VCFtools 0.1.17 itself reports some parser "
        "errors with exit 0, missing arguments with exit 76, output-open failures with "
        "exit 3, and many input-file failures with exit 1."
    )
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = ["10.1093/bioinformatics/btr330"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btr330"]
    CITATION_TEXT = "The Variant Call Format and VCFtools."
    UPSTREAM_MANPAGE = "src/cpp/vcftools.1"
    UPSTREAM_PARSER_SOURCE = "src/cpp/parameters.cpp"
    UPSTREAM_FILTER_SOURCE = "src/cpp/entry_filters.cpp"
    UPSTREAM_OUTPUT_SOURCE = "src/cpp/vcf_file.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (
                    ("VCF", "VCF_GZ"),
                    {"description": "Uncompressed or gzip-compressed input VCF"},
                ),
            },
            "optional": {
                "maf": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "description": "Optional minimum minor allele frequency",
                        "advanced": True,
                    },
                ),
                "min_qual": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "description": "Optional minimum site QUAL",
                        "advanced": True,
                    },
                ),
                "min_mean_depth": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "description": "Optional minimum mean site depth from FORMAT/DP",
                        "advanced": True,
                    },
                ),
                "max_missing": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "description": "Optional minimum call rate (VCFtools --max-missing)",
                        "advanced": True,
                    },
                ),
                "recode_info_all": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Retain all original INFO fields while recoding",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        vcf = str(inputs["vcf"])
        input_flag = "--gzvcf" if vcf.lower().endswith(".gz") else "--vcf"
        command = ["vcftools", input_flag, vcf]

        for key, flag in (
            ("maf", "--maf"),
            ("min_qual", "--minQ"),
            ("min_mean_depth", "--min-meanDP"),
            ("max_missing", "--max-missing"),
        ):
            value = inputs.get(key)
            if value is not None:
                command.extend([flag, str(value)])

        if inputs.get("recode_info_all", False):
            command.append("--recode-INFO-all")

        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command.extend(["--recode", "--out", str(output / "filtered")])
        return command

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("vcf", "")).strip():
            return "vcf must be a non-empty path"

        for key, minimum, maximum in (
            ("maf", 0.0, 1.0),
            ("min_qual", 0.0, None),
            ("min_mean_depth", 0.0, None),
            ("max_missing", 0.0, 1.0),
        ):
            validation = _validate_optional_number(
                inputs,
                key,
                minimum=minimum,
                maximum=maximum,
            )
            if validation is not True:
                return validation
        return True
