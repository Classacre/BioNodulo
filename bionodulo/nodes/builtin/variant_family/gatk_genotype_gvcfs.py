"""GATK 4.6.2.0 GenotypeGVCFs node."""

from __future__ import annotations

from typing import Any

from .gatk_adapter import (
    GATKCommandNode,
    resolve_single_path_alias,
    validate_gatk_variant_index,
    validate_optional_variant_index,
    validate_reference_bundle,
)


class GatkGenotypeGVCFsNode(GATKCommandNode):
    """Genotype one single- or multi-sample GVCF input."""

    NODE_ID = "gatk_genotype_gvcfs"
    DISPLAY_NAME = "GATK GenotypeGVCFs"
    DESCRIPTION = "Joint-genotype one HaplotypeCaller or CombineGVCFs GVCF"
    SEARCH_ALIASES = ["gatk", "genotypegvcfs", "joint genotyping", "gvcf"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("vcf", "vcf_index")
    OUTPUT_FILENAMES = ("genotyped.vcf.gz", "genotyped.vcf.gz.tbi")
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360036899732-GenotypeGVCFs"
    UPSTREAM_SOURCE = "src/main/java/org/broadinstitute/hellbender/tools/walkers/GenotypeGVCFs.java"
    UPSTREAM_TRAVERSAL_SOURCE = "src/main/java/org/broadinstitute/hellbender/engine/VariantLocusWalker.java"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gvcf": (
                    ("VCF", "VCF_GZ"),
                    {"description": "One HaplotypeCaller or CombineGVCFs GVCF"},
                ),
                "gvcf_index": (
                    "VCF_INDEX",
                    {"description": "Exact TBI or Tribble IDX for the GVCF"},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with colocated FAI and sequence dictionary"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai sidecar"},
                ),
                "sequence_dictionary": (
                    "SEQUENCE_DICTIONARY",
                    {"description": "Exact extension-replaced <reference>.dict sidecar"},
                ),
            },
            "optional": {
                "gvcfs": (
                    ("VCF", "VCF_GZ"),
                    {
                        "default": None,
                        "multiple": True,
                        "description": "Legacy alias for gvcf; must resolve to exactly one path",
                        "advanced": True,
                    },
                ),
                "intervals": (
                    "STRING",
                    {"default": "", "description": "GATK interval string or file", "advanced": True},
                ),
                "dbsnp": (
                    ("VCF", "VCF_GZ"),
                    {"description": "Optional dbSNP annotation resource", "advanced": True},
                ),
                "dbsnp_index": (
                    "VCF_INDEX",
                    {"description": "Exact TBI or Tribble IDX for dbSNP", "advanced": True},
                ),
                "standard_min_confidence": (
                    "FLOAT",
                    {"default": 30.0, "min": 0.0, "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _resolved_gvcf(cls, inputs: dict[str, Any]) -> str | None:
        return resolve_single_path_alias(
            inputs,
            canonical_key="gvcf",
            alias_key="gvcfs",
            split_alias_commas=True,
        )

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            gvcf = cls._resolved_gvcf(inputs)
        except ValueError as exc:
            return str(exc)
        normalized = dict(inputs)
        if gvcf is not None:
            normalized["gvcf"] = gvcf

        validation = super().VALIDATE_INPUTS(normalized)
        if validation is not True:
            return validation
        validation = validate_reference_bundle(normalized)
        if validation is not True:
            return validation
        validation = validate_gatk_variant_index(
            normalized,
            variant_key="gvcf",
            index_key="gvcf_index",
        )
        if validation is not True:
            return validation
        validation = validate_optional_variant_index(
            normalized,
            variant_key="dbsnp",
            index_key="dbsnp_index",
        )
        if validation is not True:
            return validation
        return cls.validate_number(
            normalized.get("standard_min_confidence", 30.0),
            key="standard_min_confidence",
            minimum=0.0,
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "GenotypeGVCFs")
        gvcf = cls._resolved_gvcf(inputs)
        if gvcf is None:
            raise ValueError("Required input 'gvcf' is missing")
        command.extend(
            [
                "-R",
                str(inputs["reference"]),
                "-V",
                gvcf,
                "-O",
                str(cls.output_path(inputs)),
                "--create-output-variant-index",
                "true",
                "--standard-min-confidence-threshold-for-calling",
                str(inputs.get("standard_min_confidence", 30.0)),
            ]
        )
        if inputs.get("dbsnp"):
            command.extend(["--dbsnp", str(inputs["dbsnp"])])
        if inputs.get("intervals"):
            command.extend(["-L", str(inputs["intervals"])])
        return command
