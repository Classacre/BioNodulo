"""VCF filtering node backed by bcftools."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class FilterVCFNode(CommandNode):
    """Filter VCF/BCF variants using bcftools."""

    NODE_ID = "filter_vcf"
    DISPLAY_NAME = "Filter VCF"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Filter VCF/BCF variant files using bcftools. Supports QUAL, DP, AF "
        "thresholds, region filtering, biallelic/SNP/indel selection, PASS-only "
        "filtering, and custom bcftools filter expressions."
    )
    SEARCH_ALIASES = [
        "vcf filter",
        "bcf filter",
        "variant filter",
        "bcftools filter",
        "quality filter",
        "depth filter",
        "region filter",
        "snp filter",
        "indel filter",
        "pass filter",
        "allele frequency",
    ]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("filtered_vcf",)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ["bcftools"]
    VERSION = "1.0.0"
    SHELL = True
    _OUTPUT_EXTENSIONS = {"VCF": ".vcf", "VCF_GZ": ".vcf.gz", "BCF": ".bcf"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF,VCF_GZ,BCF", {"description": "Input VCF, bgzipped VCF, or BCF file"}),
            },
            "optional": {
                "regions": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma-separated regions: chr1:1000-2000,chr2:500-1000",
                    },
                ),
                "targets": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Comma-separated target regions (streamed, indexed input required)",
                    },
                ),
                "min_qual": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 999999.0, "tooltip": "Minimum QUAL score"},
                ),
                "min_dp": (
                    "INT",
                    {"default": 0, "min": 0, "max": 999999, "tooltip": "Minimum INFO/DP depth"},
                ),
                "max_dp": (
                    "INT",
                    {"default": 0, "min": 0, "max": 999999, "tooltip": "Maximum INFO/DP depth (0 = no limit)"},
                ),
                "min_af": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 1.0, "tooltip": "Minimum allele frequency"},
                ),
                "max_af": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 1.0, "tooltip": "Maximum allele frequency (0 = no limit)"},
                ),
                "pass_only": ("BOOLEAN", {"default": False, "tooltip": "Keep only PASS variants"}),
                "biallelic_only": ("BOOLEAN", {"default": False, "tooltip": "Keep only biallelic sites"}),
                "snp_only": ("BOOLEAN", {"default": False, "tooltip": "Keep only SNPs"}),
                "indel_only": ("BOOLEAN", {"default": False, "tooltip": "Keep only indels"}),
                "custom_filter": (
                    "STRING",
                    {
                        "default": "",
                        "tooltip": "Custom bcftools filter expression, e.g. INFO/ANN ~ 'missense_variant'",
                    },
                ),
                "samples": (
                    "STRING",
                    {"default": "", "tooltip": "Comma-separated sample names to retain (empty = all)"},
                ),
                "output_type": (["VCF", "VCF_GZ", "BCF"], {"default": "VCF_GZ"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {
                "output_dir": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if bool(inputs.get("snp_only", False)) and bool(inputs.get("indel_only", False)):
            return "snp_only and indel_only cannot both be enabled"

        min_dp = int(inputs.get("min_dp") or 0)
        max_dp = int(inputs.get("max_dp") or 0)
        if max_dp > 0 and min_dp > max_dp:
            return "min_dp cannot be greater than max_dp"

        min_af = float(inputs.get("min_af") or 0.0)
        max_af = float(inputs.get("max_af") or 0.0)
        if max_af > 0 and min_af > max_af:
            return "min_af cannot be greater than max_af"

        output_type = str(inputs.get("output_type") or "VCF_GZ")
        if output_type not in {"VCF", "VCF_GZ", "BCF"}:
            return "output_type must be one of VCF, VCF_GZ, or BCF"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_type = str(inputs.get("output_type") or "VCF_GZ")
        extension = cls._OUTPUT_EXTENSIONS.get(output_type, ".vcf.gz")
        return [Path(output_dir) / cls.NODE_ID / f"filtered_vcf{extension}"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        filters = cls._filter_expressions(inputs)
        view_cmd = cls._view_command(inputs)
        output_cmd = cls._output_command(inputs)

        if filters:
            return [
                *view_cmd,
                "|",
                "bcftools",
                "filter",
                "--include",
                " && ".join(filters),
                "|",
                *output_cmd,
            ]
        return [*view_cmd, "|", *output_cmd]

    @classmethod
    def _filter_expressions(cls, inputs: dict[str, Any]) -> list[str]:
        filters: list[str] = []

        min_qual = float(inputs.get("min_qual") or 0.0)
        if min_qual > 0:
            filters.append(f"QUAL >= {min_qual}")

        min_dp = int(inputs.get("min_dp") or 0)
        if min_dp > 0:
            filters.append(f"INFO/DP >= {min_dp}")

        max_dp = int(inputs.get("max_dp") or 0)
        if max_dp > 0:
            filters.append(f"INFO/DP <= {max_dp}")

        min_af = float(inputs.get("min_af") or 0.0)
        if min_af > 0:
            filters.append(f"INFO/AF >= {min_af}")

        max_af = float(inputs.get("max_af") or 0.0)
        if max_af > 0:
            filters.append(f"INFO/AF <= {max_af}")

        if bool(inputs.get("pass_only", False)):
            filters.append('FILTER == "PASS"')

        custom_filter = str(inputs.get("custom_filter") or "").strip()
        if custom_filter:
            filters.append(custom_filter)

        return filters

    @classmethod
    def _view_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bcftools", "view"]

        regions = str(inputs.get("regions") or "").strip()
        if regions:
            cmd.extend(["--regions", regions])

        targets = str(inputs.get("targets") or "").strip()
        if targets:
            cmd.extend(["--targets", targets])

        samples = str(inputs.get("samples") or "").strip()
        if samples:
            cmd.extend(["--samples", samples])

        if bool(inputs.get("biallelic_only", False)):
            cmd.extend(["--min-alleles", "2", "--max-alleles", "2"])

        if bool(inputs.get("snp_only", False)):
            cmd.extend(["--types", "snps"])
        elif bool(inputs.get("indel_only", False)):
            cmd.extend(["--types", "indels"])

        cmd.append(str(inputs.get("vcf", "")))
        return cmd

    @classmethod
    def _output_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_type = str(inputs.get("output_type") or "VCF_GZ")
        out_flag = {"VCF": "-Ov", "VCF_GZ": "-Oz", "BCF": "-Ob"}[output_type]
        threads = max(1, int(inputs.get("threads") or 1))
        output_base = inputs.get("output") or inputs.get("output_dir") or "."
        output_path = Path(str(output_base)) / f"filtered_vcf{cls._OUTPUT_EXTENSIONS[output_type]}"
        return ["bcftools", "view", "--threads", str(threads), out_flag, "-o", str(output_path)]
