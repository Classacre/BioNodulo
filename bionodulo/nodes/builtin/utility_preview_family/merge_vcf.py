"""BCFtools 1.24 unindexed VCF merge compatibility contract."""

from __future__ import annotations

from typing import Any

from bionodulo.nodes.builtin.bcftools_family.adapter import (
    FixedVcfOutputNode,
    add_fixed_vcf_output,
    as_list,
    require_paths,
    validate_choice,
)


MERGE_MODES = ("snps", "indels", "both", "snp-ins-del", "all", "exact", "none", "id", "*", "**")


class MergeVCFNode(FixedVcfOutputNode):
    """Merge at least two compressed VCFs without implicit sidecar discovery."""

    NODE_ID = "merge_vcf"
    DISPLAY_NAME = "Merge VCF"
    CATEGORY = "utils"
    DESCRIPTION = "Merge multiple VCF/BCF sample sets with source-pinned BCFtools"
    SEARCH_ALIASES = ["merge", "vcf", "combine", "bcftools merge"]
    RETURN_NAMES = ("merged_vcf",)
    OUTPUT_FILENAME = "merged.vcf.gz"
    CONDA_PACKAGE_CONSTRAINTS = {"bcftools": "1.24"}
    DOCUMENTATION_URL = "https://www.htslib.org/doc/bcftools.html#merge"
    UPSTREAM_SOURCE = "vcfmerge.c; doc/bcftools.txt"
    EXIT_SEMANTICS = "BCFtools exit code 0 plus merged.vcf.gz is success; any failure or missing output fails the node."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcfs": ("VCF_GZ", {"multiple": True, "description": "Two or more compressed VCFs"}),
            },
            "optional": {
                "force_samples": ("BOOLEAN", {"default": True}),
                "merge": ("STRING", {"default": "both", "options": list(MERGE_MODES)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_paths(inputs, "vcfs", minimum=2)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("merge", "both"), "merge", MERGE_MODES)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "merge", "--no-index"]
        if inputs.get("force_samples", True):
            command.append("--force-samples")
        command.extend(["--merge", str(inputs.get("merge", "both"))])
        add_fixed_vcf_output(command, cls, inputs)
        command.extend(as_list(inputs.get("vcfs")))
        return command
