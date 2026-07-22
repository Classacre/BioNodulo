"""Source-pinned VCF filtering with one BCFtools 1.24 view command."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.annotation_family.staging import stage_file
from bionodulo.nodes.command_node import CommandNode


def _path_value(value: Any) -> str | None:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def _number(
    value: Any,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> bool | str:
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected):
        return f"{name} must be {'an integer' if integer else 'a number'}"
    number = float(value)
    if minimum is not None and number < minimum:
        return f"{name} must be at least {minimum:g}"
    if maximum is not None and number > maximum:
        return f"{name} must be at most {maximum:g}"
    return True


def _expected_indexes(data_path: str) -> tuple[Path, ...]:
    data = Path(os.path.abspath(os.path.normpath(data_path)))
    if data.suffix.lower() == ".bcf":
        return (Path(f"{data}.csi"),)
    return (Path(f"{data}.csi"), Path(f"{data}.tbi"))


class FilterVCFNode(CommandNode):
    """Filter VCF/BCF records and always emit an indexed BGZF VCF."""

    NODE_ID = "filter_vcf"
    DISPLAY_NAME = "Filter VCF"
    CATEGORY = "data_transform"
    DESCRIPTION = "Filter VCF/BCF records with one BCFtools view invocation and emit a VCF.gz/CSI pair."
    SEARCH_ALIASES = [
        "vcf filter",
        "bcf filter",
        "variant filter",
        "bcftools view",
        "quality filter",
        "depth filter",
        "region filter",
        "snp filter",
        "indel filter",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("filtered_vcf", "filtered_vcf_index")
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ["bcftools"]
    PACKAGE_CONSTRAINTS = ("bcftools==1.24",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "1.24"
    GIT_URL = "https://github.com/samtools/bcftools.git"
    GIT_COMMIT = "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"
    DOCUMENTATION_URL = "https://www.htslib.org/doc/1.24/bcftools.html"
    SOURCE_URL = f"https://github.com/samtools/bcftools/blob/{GIT_COMMIT}/vcfview.c"
    DOCUMENTATION_SOURCE_URL = f"https://github.com/samtools/bcftools/blob/{GIT_COMMIT}/doc/bcftools.txt"
    DOCUMENTATION_SOURCE_SHA256 = "378bcf1f2faa5cef1f776c8cdcfdf096ad4b977a9e9d811a9c74d4d5830af0f7"
    UPSTREAM_SOURCE_SHA256 = "0834e06b0a6338e36b21f105b1a49c5f337c8f4dc358abe68cf6b59026f16412"
    CITATION_DOIS = ["10.1093/gigascience/giab008"]
    CITATION_URLS = ["https://doi.org/10.1093/gigascience/giab008"]
    CITATION_TEXT = "Twelve years of SAMtools and BCFtools."
    UPSTREAM_DOC = "doc/bcftools.txt"
    UPSTREAM_SOURCE = "vcfview.c"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    OUTPUT_FILENAME = "filtered_vcf.vcf.gz"
    OUTPUT_INDEX_FILENAME = "filtered_vcf.vcf.gz.csi"
    EXIT_SEMANTICS = (
        "BCFtools view exits non-zero for unreadable inputs, invalid filters, missing random-access indexes, "
        "and output/index failures; every non-zero exit is fatal. BioNodulo also requires both the BGZF VCF "
        "and requested CSI output after a zero exit."
    )
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF,VCF_GZ,BCF", {"description": "Input VCF, BGZF VCF, or BCF"}),
            },
            "optional": {
                "vcf_index": (
                    "VCF_INDEX",
                    {"default": "", "description": "Explicit colocated CSI/TBI required by --regions"},
                ),
                "regions": ("STRING", {"default": "", "description": "Comma-separated random-access regions"}),
                "targets": ("STRING", {"default": "", "description": "Comma-separated streaming targets"}),
                "min_qual": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "min_dp": ("INT", {"default": 0, "min": 0}),
                "max_dp": ("INT", {"default": None, "min": 0}),
                "min_af": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "max_af": ("FLOAT", {"default": None, "min": 0.0, "max": 1.0}),
                "pass_only": ("BOOLEAN", {"default": False}),
                "biallelic_only": ("BOOLEAN", {"default": False}),
                "snp_only": ("BOOLEAN", {"default": False}),
                "indel_only": ("BOOLEAN", {"default": False}),
                "custom_filter": ("STRING", {"default": "", "description": "BCFtools include expression"}),
                "samples": ("STRING", {"default": "", "description": "Comma-separated samples to retain"}),
                "threads": ("INT", {"default": 0, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _filter_expression(cls, inputs: dict[str, Any]) -> str:
        expressions: list[str] = []
        min_qual = float(inputs.get("min_qual") or 0.0)
        if min_qual > 0:
            expressions.append(f"QUAL >= {min_qual}")
        min_dp = int(inputs.get("min_dp") or 0)
        if min_dp > 0:
            expressions.append(f"INFO/DP >= {min_dp}")
        max_dp = inputs.get("max_dp")
        if max_dp not in (None, ""):
            expressions.append(f"INFO/DP <= {int(max_dp)}")
        min_af = float(inputs.get("min_af") or 0.0)
        if min_af > 0:
            expressions.append(f"INFO/AF >= {min_af}")
        max_af = inputs.get("max_af")
        if max_af not in (None, ""):
            expressions.append(f"INFO/AF <= {float(max_af)}")
        if inputs.get("pass_only", False):
            expressions.append('FILTER == "PASS"')
        custom = str(inputs.get("custom_filter") or "").strip()
        if custom:
            expressions.append(f"({custom})")
        return " && ".join(expressions)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        vcf = _path_value(inputs.get("vcf"))
        if vcf is None:
            return "vcf must be a non-empty path"
        if inputs.get("snp_only", False) and inputs.get("indel_only", False):
            return "snp_only and indel_only cannot both be enabled"
        for name, default, minimum, maximum, integer in (
            ("min_qual", 0.0, 0.0, None, False),
            ("min_dp", 0, 0.0, None, True),
            ("max_dp", None, 0.0, None, True),
            ("min_af", 0.0, 0.0, 1.0, False),
            ("max_af", None, 0.0, 1.0, False),
            ("threads", 0, 0.0, None, True),
        ):
            value = inputs.get(name, default)
            if default is None and value in (None, ""):
                continue
            validation = _number(
                value,
                name,
                minimum=minimum,
                maximum=maximum,
                integer=integer,
            )
            if validation is not True:
                return validation
        min_dp = int(inputs.get("min_dp") or 0)
        max_dp_value = inputs.get("max_dp")
        if max_dp_value not in (None, ""):
            max_dp = int(max_dp_value)
            if min_dp > max_dp:
                return "min_dp cannot be greater than max_dp"
        min_af = float(inputs.get("min_af") or 0.0)
        max_af_value = inputs.get("max_af")
        if max_af_value not in (None, ""):
            max_af = float(max_af_value)
            if min_af > max_af:
                return "min_af cannot be greater than max_af"
        if str(inputs.get("regions") or "").strip():
            if Path(vcf).suffix.lower() != ".bcf" and not vcf.lower().endswith((".vcf.gz", ".vcf.bgz")):
                return "regions require an indexed BGZF VCF or BCF input"
            index = _path_value(inputs.get("vcf_index"))
            expected = _expected_indexes(vcf)
            if index is None:
                rendered = ", ".join(str(path) for path in expected)
                return f"vcf_index is required for regions; expected one of: {rendered}"
            absolute_index = Path(os.path.abspath(os.path.normpath(index)))
            if absolute_index not in expected:
                rendered = ", ".join(str(path) for path in expected)
                return f"vcf_index must be colocated with vcf; expected one of: {rendered}"
        if "output_type" in inputs:
            return "output_type is stale; Filter VCF always emits an indexed BGZF VCF"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        index = _path_value(inputs.get("vcf_index"))
        if index is None:
            return
        source = Path(str(inputs["vcf"]))
        if source.suffix.lower() == ".bcf":
            staged_data = outputs[0].parent / "input" / "input.bcf"
        elif str(source).lower().endswith((".vcf.gz", ".vcf.bgz")):
            staged_data = outputs[0].parent / "input" / "input.vcf.gz"
        else:
            staged_data = outputs[0].parent / "input" / "input.vcf"
        staged_index = Path(f"{staged_data}{Path(index).suffix.lower()}")
        inputs["vcf"] = str(stage_file(source, staged_data))
        inputs["vcf_index"] = str(stage_file(index, staged_index))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["bcftools", "view", "--threads", str(inputs.get("threads", 0))]
        regions = str(inputs.get("regions") or "").strip()
        if regions:
            command.extend(["--regions", regions])
        targets = str(inputs.get("targets") or "").strip()
        if targets:
            command.extend(["--targets", targets])
        samples = str(inputs.get("samples") or "").strip()
        if samples:
            command.extend(["--samples", samples])
        if inputs.get("biallelic_only", False):
            command.extend(["--min-alleles", "2", "--max-alleles", "2"])
        if inputs.get("snp_only", False):
            command.extend(["--types", "snps"])
        elif inputs.get("indel_only", False):
            command.extend(["--types", "indels"])
        expression = cls._filter_expression(inputs)
        if expression:
            command.extend(["--include", expression])
        command.extend(
            [
                "-Oz",
                "--write-index=csi",
                "-o",
                str(output_dir / cls.OUTPUT_FILENAME),
                str(inputs.get("vcf", "")),
            ]
        )
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / cls.OUTPUT_FILENAME, node_out / cls.OUTPUT_INDEX_FILENAME]
