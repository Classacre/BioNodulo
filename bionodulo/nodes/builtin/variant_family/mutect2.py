"""GATK 4.6.2.0 Mutect2 node."""

from __future__ import annotations

from typing import Any

from .gatk_adapter import (
    GATKCommandNode,
    path_values,
    validate_gatk_bam_index,
    validate_optional_bam_index,
    validate_optional_variant_index,
    validate_reference_bundle,
)


class Mutect2Node(GATKCommandNode):
    """Call somatic variants in tumor-only or explicit tumor-normal mode."""

    NODE_ID = "mutect2"
    DISPLAY_NAME = "Mutect2"
    DESCRIPTION = "Call somatic SNVs and indels from indexed tumor or tumor-normal BAMs"
    SEARCH_ALIASES = ["mutect2", "gatk", "somatic variant", "tumor normal", "cancer variant"]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX", "STATS_FILE")
    RETURN_NAMES = ("vcf", "vcf_index", "stats")
    OUTPUT_FILENAMES = (
        "unfiltered.vcf.gz",
        "unfiltered.vcf.gz.tbi",
        "unfiltered.vcf.gz.stats",
    )
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037593851-Mutect2"
    UPSTREAM_SOURCE = "src/main/java/org/broadinstitute/hellbender/tools/walkers/mutect/Mutect2.java"
    UPSTREAM_ARGUMENT_SOURCE = (
        "src/main/java/org/broadinstitute/hellbender/tools/walkers/mutect/M2ArgumentCollection.java"
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tumor_bam": (
                    "BAM",
                    {"description": "Coordinate-sorted tumor BAM with read groups"},
                ),
                "tumor_bam_index": (
                    "BAI",
                    {"description": "Exact colocated <stem>.bai or <bam>.bai tumor index"},
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
                "normal_bam": (
                    "BAM",
                    {"description": "Coordinate-sorted matched-normal BAM", "advanced": True},
                ),
                "normal_bam_index": (
                    "BAI",
                    {"description": "Exact colocated matched-normal BAI", "advanced": True},
                ),
                "tumor_sample": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Deprecated GATK tumor sample override",
                        "advanced": True,
                    },
                ),
                "normal_sample": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Normal sample name; required with normal_bam",
                        "advanced": True,
                    },
                ),
                "germline_resource": (
                    ("VCF", "VCF_GZ"),
                    {"description": "Population germline allele-frequency resource", "advanced": True},
                ),
                "germline_resource_index": (
                    "VCF_INDEX",
                    {"description": "Exact TBI or Tribble IDX for germline_resource", "advanced": True},
                ),
                "panel_of_normals": (
                    ("VCF", "VCF_GZ"),
                    {"description": "Panel-of-normals VCF", "advanced": True},
                ),
                "panel_of_normals_index": (
                    "VCF_INDEX",
                    {"description": "Exact TBI or Tribble IDX for panel_of_normals", "advanced": True},
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
        validation = validate_gatk_bam_index(
            inputs,
            bam_key="tumor_bam",
            index_key="tumor_bam_index",
        )
        if validation is not True:
            return validation
        validation = validate_reference_bundle(inputs)
        if validation is not True:
            return validation
        validation = validate_optional_bam_index(
            inputs,
            bam_key="normal_bam",
            index_key="normal_bam_index",
        )
        if validation is not True:
            return validation

        normal_bams = path_values(inputs.get("normal_bam"), key="normal_bam")
        if isinstance(normal_bams, str):
            return normal_bams
        normal_sample = inputs.get("normal_sample", "")
        if normal_bams:
            if not isinstance(normal_sample, str) or not normal_sample.strip():
                return "Input 'normal_bam' requires a non-empty 'normal_sample'"
        elif normal_sample not in (None, ""):
            return "Input 'normal_sample' requires input 'normal_bam'"

        tumor_sample = inputs.get("tumor_sample", "")
        if tumor_sample not in (None, "") and (
            not isinstance(tumor_sample, str) or not tumor_sample.strip()
        ):
            return "Input 'tumor_sample' must be a non-empty string when provided"

        for variant_key, index_key in (
            ("germline_resource", "germline_resource_index"),
            ("panel_of_normals", "panel_of_normals_index"),
        ):
            validation = validate_optional_variant_index(
                inputs,
                variant_key=variant_key,
                index_key=index_key,
            )
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "Mutect2")
        command.extend(
            [
                "-R",
                str(inputs["reference"]),
                "-I",
                str(inputs["tumor_bam"]),
            ]
        )
        if inputs.get("normal_bam"):
            command.extend(["-I", str(inputs["normal_bam"])])
        if inputs.get("tumor_sample"):
            command.extend(["--tumor-sample", str(inputs["tumor_sample"])])
        if inputs.get("normal_sample"):
            command.extend(["--normal-sample", str(inputs["normal_sample"])])
        if inputs.get("germline_resource"):
            command.extend(["--germline-resource", str(inputs["germline_resource"])])
        if inputs.get("panel_of_normals"):
            command.extend(["--panel-of-normals", str(inputs["panel_of_normals"])])
        if inputs.get("intervals"):
            command.extend(["-L", str(inputs["intervals"])])
        command.extend(
            [
                "-O",
                str(cls.output_path(inputs)),
                "--create-output-variant-index",
                "true",
            ]
        )
        return command
