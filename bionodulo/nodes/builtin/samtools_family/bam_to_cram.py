"""Focused Samtools 1.23.1 owner: Convert BAM or SAM alignments to CRAM using a reference genome."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _add_if_value,
    _additional_threads,
    TOOLS_IUC_GIT_COMMIT,
    validate_index_pairs,
)


class SamtoolsBamToCramNode(SamtoolsCommandNode):
    """Convert BAM or SAM alignments to CRAM using a reference genome."""

    NODE_ID = "samtools_bam_to_cram"
    DISPLAY_NAME = "Samtools BAM to CRAM"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Convert BAM alignments to CRAM format with reference-based compression."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "samtools",
        "BAM to CRAM",
        "SAM to CRAM",
        "CRAM compression",
        "reference based compression",
    ]
    RETURN_TYPES = ("CRAM",)
    RETURN_NAMES = ("cram",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-view.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("output.cram",)
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"
    WRAPPER_SOURCE = "tool_collections/samtools/bam_to_cram/samtools_bam_to_cram.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reference = str(inputs.get("reference", ""))

        cmd = ["samtools", "view"]
        if inputs.get("target_region") == "regions_bed_file":
            _add_if_value(cmd, "-L", inputs.get("regions_bed_file"))
        cmd.extend(
            [
                "-@",
                str(_additional_threads(inputs)),
                "-C",
                "-h",
                "-o",
                str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
                "-T",
                reference,
            ]
        )
        input_path = str(inputs.get("input", ""))
        if inputs.get("target_region") == "region":
            cmd.extend(
                [
                    "-X",
                    input_path,
                    str(inputs.get("bam_index", "")),
                    str(inputs.get("region_string", "")),
                ]
            )
        else:
            cmd.append(input_path)
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        validation = validate_colocated_reference_index(inputs)
        if validation is not True:
            return validation
        target_region = str(inputs.get("target_region", "entire_input_file"))
        if target_region == "region" and not str(inputs.get("region_string", "") or "").strip():
            return "region_string is required when target_region is region"
        if target_region == "regions_bed_file" and not str(inputs.get("regions_bed_file", "") or "").strip():
            return "regions_bed_file is required when target_region is regions_bed_file"
        if target_region != "region" and str(inputs.get("region_string", "") or "").strip():
            return "region_string is only valid when target_region is region"
        if target_region != "regions_bed_file" and inputs.get("regions_bed_file"):
            return "regions_bed_file is only valid when target_region is regions_bed_file"
        if target_region == "region":
            return validate_index_pairs(
                inputs,
                data_key="input",
                index_key="bam_index",
                required=True,
            )
        if inputs.get("bam_index"):
            return "bam_index is only consumed when target_region is region"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for CRAM compression"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated <reference>.fai index"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "bam_index": (
                    "BAI",
                    {"description": "Explicit BAI passed with -X for a region query", "advanced": True},
                ),
                "target_region": (
                    "STRING",
                    {
                        "default": "entire_input_file",
                        "options": ["entire_input_file", "region", "regions_bed_file"],
                        "description": "Convert the entire input or restrict to specific genomic regions",
                    },
                ),
                "region_string": (
                    "STRING",
                    {"default": "", "description": "Region such as chrX or chr:start-end"},
                ),
                "regions_bed_file": (
                    "BED",
                    {"description": "Only include reads overlapping regions in this BED file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
