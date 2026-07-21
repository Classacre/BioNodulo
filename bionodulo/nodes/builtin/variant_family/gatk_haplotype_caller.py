"""GATK 4.6.2.0 HaplotypeCaller node."""

from __future__ import annotations

from typing import Any

from .gatk_adapter import (
    GATKCommandNode,
    validate_gatk_bam_index,
    validate_optional_variant_index,
    validate_reference_bundle,
)


class GatkHaplotypeCallerNode(GATKCommandNode):
    """Call germline SNPs and indels from one indexed BAM."""

    NODE_ID = "gatk_haplotype_caller"
    DISPLAY_NAME = "GATK HaplotypeCaller"
    DESCRIPTION = "Call germline SNPs and indels with GATK HaplotypeCaller"
    SEARCH_ALIASES = ["gatk", "haplotypecaller", "variant", "snp", "indel"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("vcf", "vcf_index")
    OUTPUT_FILENAMES = ("calls.vcf.gz", "calls.vcf.gz.tbi")
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller"
    UPSTREAM_SOURCE = "src/main/java/org/broadinstitute/hellbender/tools/walkers/haplotypecaller/HaplotypeCaller.java"
    UPSTREAM_ARGUMENT_SOURCE = (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/"
        "haplotypecaller/AssemblyBasedCallerArgumentCollection.java"
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Coordinate-sorted BAM with read groups"}),
                "bam_index": (
                    "BAI",
                    {"description": "Exact colocated <stem>.bai or <bam>.bai index"},
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
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "optional": {
                "emit_ref_confidence": (
                    "STRING",
                    {
                        "default": "NONE",
                        "options": ["NONE", "GVCF", "BP_RESOLUTION"],
                        "advanced": True,
                    },
                ),
                "dbsnp": (
                    ("VCF", "VCF_GZ"),
                    {"description": "Optional dbSNP annotation resource", "advanced": True},
                ),
                "dbsnp_index": (
                    "VCF_INDEX",
                    {"description": "Exact TBI or Tribble IDX for dbSNP", "advanced": True},
                ),
                "stand_call_conf": (
                    "FLOAT",
                    {"default": 30.0, "min": 0.0, "advanced": True},
                ),
                "min_base_quality": (
                    "INT",
                    {"default": 10, "min": 0, "max": 127, "advanced": True},
                ),
                "sample_ploidy": (
                    "INT",
                    {"default": 2, "min": 1, "advanced": True},
                ),
                "intervals": (
                    "STRING",
                    {"default": "", "description": "GATK interval string or file", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_gatk_bam_index(inputs)
        if validation is not True:
            return validation
        validation = validate_reference_bundle(inputs)
        if validation is not True:
            return validation
        validation = validate_optional_variant_index(
            inputs,
            variant_key="dbsnp",
            index_key="dbsnp_index",
        )
        if validation is not True:
            return validation
        validation = cls.validate_int(inputs.get("threads", 4), key="threads", minimum=1)
        if validation is not True:
            return validation
        validation = cls.validate_choice(
            inputs.get("emit_ref_confidence", "NONE"),
            key="emit_ref_confidence",
            choices=("NONE", "GVCF", "BP_RESOLUTION"),
        )
        if validation is not True:
            return validation
        validation = cls.validate_number(
            inputs.get("stand_call_conf", 30.0),
            key="stand_call_conf",
            minimum=0.0,
        )
        if validation is not True:
            return validation
        validation = cls.validate_int(
            inputs.get("min_base_quality", 10),
            key="min_base_quality",
            minimum=0,
            maximum=127,
        )
        if validation is not True:
            return validation
        return cls.validate_int(
            inputs.get("sample_ploidy", 2),
            key="sample_ploidy",
            minimum=1,
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "HaplotypeCaller")
        command.extend(
            [
                "-R",
                str(inputs["reference"]),
                "-I",
                str(inputs["bam"]),
                "-O",
                str(cls.output_path(inputs)),
                "--create-output-variant-index",
                "true",
                "--native-pair-hmm-threads",
                str(inputs.get("threads", 4)),
                "--emit-ref-confidence",
                str(inputs.get("emit_ref_confidence", "NONE")),
                "--standard-min-confidence-threshold-for-calling",
                str(inputs.get("stand_call_conf", 30.0)),
                "--min-base-quality-score",
                str(inputs.get("min_base_quality", 10)),
                "--sample-ploidy",
                str(inputs.get("sample_ploidy", 2)),
            ]
        )
        if inputs.get("dbsnp"):
            command.extend(["--dbsnp", str(inputs["dbsnp"])])
        if inputs.get("intervals"):
            command.extend(["-L", str(inputs["intervals"])])
        return command
