"""Workflow-compatible Manta alias exposing the selected primary VCF and TBI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .manta import MantaNode


class MantaCallNode(MantaNode):
    """Run Manta and return the mode-specific primary native VCF."""

    NODE_ID = "manta_call"
    DISPLAY_NAME = "Manta Call"
    DESCRIPTION = "Call structural variants with Manta for multi-caller workflows"
    SEARCH_ALIASES = [
        "manta_call",
        "manta",
        "structural variant",
        "sv caller",
        "illumina sv",
        "germline sv",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = ("sv_vcf", "sv_vcf_index")

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        variants_dir = Path(output_dir) / cls.NODE_ID / "results" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        primary = variants_dir / cls._primary_vcf_name(inputs)
        return [primary, Path(f"{primary}.tbi")]
