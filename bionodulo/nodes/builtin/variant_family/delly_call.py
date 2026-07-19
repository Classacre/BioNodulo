"""Stable DELLY alias that converts native BCF to an indexed VCF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .delly import DellyNode


class DellyCallNode(DellyNode):
    """Call with DELLY, then explicitly convert and tabix-index the VCF."""

    NODE_ID = "delly_call"
    DISPLAY_NAME = "DELLY Call"
    DESCRIPTION = "Call structural variants with DELLY and convert BCF to indexed VCF"
    SEARCH_ALIASES = [
        "delly_call",
        "delly",
        "structural variant",
        "sv caller",
        "somatic sv",
        "long-read sv",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("sv_vcf", "sv_vcf_index")
    OUTPUT_FILENAMES = ("sv_vcf.vcf.gz", "sv_vcf.vcf.gz.tbi")
    REQUIRED_EXECUTABLES = ["delly", "bcftools", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["delly", "bcftools", "htslib"]
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        native_bcf = output / "sv_calls.bcf"
        converted_vcf = output / cls.OUTPUT_FILENAMES[0]
        return [
            *cls._render_delly_command(inputs, native_bcf),
            "&&",
            "bcftools",
            "view",
            "-Oz",
            "-o",
            str(converted_vcf),
            str(native_bcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(converted_vcf),
        ]
