"""CNVkit 0.9.12 absolute copy-number calling to native CNS output."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.cnvkit_family.adapter import (
    CNVKIT_COMMIT,
    CNVkitCommandNode,
    optional_path,
    validate_optional_number,
)


CALL_METHODS = ("threshold", "clonal", "none")
CALL_FILTERS = ("ampdel", "cn", "ci", "sem")
CENTER_METHODS = ("", "mean", "median", "mode", "biweight")
DEFAULT_THRESHOLDS = "-1.1,-0.25,0.2,0.7"


def _selected(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    result: list[str] = []
    for item in values:
        result.extend(part.strip() for part in str(item).split(",") if part.strip())
    return result


class CNVkitCallNode(CNVkitCommandNode):
    """Call absolute copy number from CNVkit copy-ratio or segment tables."""

    NODE_ID = "cnvkit_call"
    DISPLAY_NAME = "CNVkit Call"
    DESCRIPTION = "Convert CNVkit log2 ratios or segments into a called .cns table."
    SEARCH_ALIASES = ["cnvkit", "cnv call", "copy number", "segment", "call"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("called_segments",)
    OUTPUT_FILENAMES = ("called_segments.call.cns",)
    SOURCE_REF = CNVKIT_COMMIT
    DOCUMENTATION_URL = (
        f"https://github.com/etal/cnvkit/blob/{CNVKIT_COMMIT}/doc/calling.rst"
    )
    UPSTREAM_CALL_SOURCE = "cnvlib/call.py"
    SOURCE_PATHS = ("cnvlib/commands.py", "cnvlib/call.py", "doc/calling.rst")
    SOURCE_OUTPUTS = "CNVkit tabular copy-ratio output conventionally named *.call.cns"
    EXIT_SEMANTICS = (
        "BioNodulo prevalidates exposed values; a non-zero CNVkit result or missing "
        "called_segments.call.cns fails the node. Real CNVkit execution was not performed."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cns_file": ("FILE", {"description": "CNVkit .cnr or .cns copy-ratio table"}),
            },
            "optional": {
                "center": ("STRING", {"default": "", "options": list(CENTER_METHODS)}),
                "center_at": ("FLOAT", {"default": None, "description": "Manual log2 recentering constant"}),
                "filters": (
                    "STRING_LIST",
                    {"default": [], "options": list(CALL_FILTERS), "description": "Repeatable segment filters"},
                ),
                "method": ("STRING", {"default": "threshold", "options": list(CALL_METHODS)}),
                "thresholds": (
                    "STRING",
                    {"default": DEFAULT_THRESHOLDS, "description": "Comma-separated absolute copy-number thresholds"},
                ),
                "ploidy": ("INT", {"default": 2, "min": 1}),
                "purity": ("FLOAT", {"default": None, "min": 0.0, "max": 1.0}),
                "drop_low_coverage": ("BOOLEAN", {"default": False}),
                "sample_sex": ("STRING", {"default": "", "options": ["", "male", "female"]}),
                "male_reference": ("BOOLEAN", {"default": False}),
                "vcf": (
                    ("VCF", "VCF_GZ"),
                    {"description": "Optional SNV VCF used to calculate B-allele frequencies"},
                ),
                "sample_id": ("STRING", {"default": "", "description": "Sample ID selected from the VCF"}),
                "normal_id": ("STRING", {"default": "", "description": "Matched normal sample ID in the VCF"}),
                "min_variant_depth": ("INT", {"default": 20, "min": 1}),
                "zygosity_freq": ("FLOAT", {"default": None, "min": 0.0, "max": 1.0}),
                "diploid_parx_genome": (
                    "STRING",
                    {"default": "", "description": "Genome label whose chromosome-X PAR is diploid"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["cnvkit.py", "call", str(inputs["cns_file"])]

        center = str(inputs.get("center", "") or "")
        if center:
            command.extend(["--center", center])
        if inputs.get("center_at") is not None:
            command.extend(["--center-at", str(inputs["center_at"])])
        for filter_name in _selected(inputs.get("filters")):
            command.extend(["--filter", filter_name])
        command.extend(["--method", str(inputs.get("method", "threshold"))])
        command.append(f"--thresholds={inputs.get('thresholds', DEFAULT_THRESHOLDS)}")
        command.extend(["--ploidy", str(inputs.get("ploidy", 2))])
        if inputs.get("purity") is not None:
            command.extend(["--purity", str(inputs["purity"])])
        if inputs.get("drop_low_coverage", False):
            command.append("--drop-low-coverage")
        if inputs.get("sample_sex"):
            command.extend(["--sample-sex", str(inputs["sample_sex"])])
        if inputs.get("male_reference", False):
            command.append("--male-reference")
        command.extend(["--output", str(output / cls.OUTPUT_FILENAMES[0])])

        if inputs.get("vcf"):
            command.extend(["--vcf", str(inputs["vcf"])])
            if inputs.get("sample_id"):
                command.extend(["--sample-id", str(inputs["sample_id"])])
            if inputs.get("normal_id"):
                command.extend(["--normal-id", str(inputs["normal_id"])])
            command.extend(["--min-variant-depth", str(inputs.get("min_variant_depth", 20))])
            if inputs.get("zygosity_freq") is not None:
                command.extend(["--zygosity-freq", str(inputs["zygosity_freq"])])
        if inputs.get("diploid_parx_genome"):
            command.extend(["--diploid-parx-genome", str(inputs["diploid_parx_genome"])])
        return command

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if optional_path(inputs.get("cns_file")) in (None, ""):
            return "cns_file must be a non-empty path-like value"
        if optional_path(inputs.get("vcf")) is None:
            return "vcf must be a single non-empty path when supplied"

        method = str(inputs.get("method", "threshold"))
        if method not in CALL_METHODS:
            return f"method must be one of: {', '.join(CALL_METHODS)}"
        center = str(inputs.get("center", "") or "")
        if center not in CENTER_METHODS:
            return "center must be one of: mean, median, mode, biweight"
        if center and inputs.get("center_at") is not None:
            return "center and center_at are mutually exclusive"
        validation = validate_optional_number(inputs.get("center_at"), key="center_at")
        if validation is not True:
            return validation

        filters = _selected(inputs.get("filters"))
        invalid_filters = sorted(set(filters) - set(CALL_FILTERS))
        if invalid_filters:
            return f"unsupported CNVkit call filters: {', '.join(invalid_filters)}"
        try:
            thresholds = [
                float(value)
                for value in str(inputs.get("thresholds", DEFAULT_THRESHOLDS)).split(",")
            ]
        except ValueError:
            return "thresholds must be comma-separated numbers"
        if not thresholds or not all(math.isfinite(value) for value in thresholds):
            return "thresholds must be comma-separated finite numbers"

        ploidy = inputs.get("ploidy", 2)
        if isinstance(ploidy, bool) or not isinstance(ploidy, int) or ploidy < 1:
            return "ploidy must be a positive integer"
        validation = validate_optional_number(
            inputs.get("purity"),
            key="purity",
            minimum=0.0,
            maximum=1.0,
            exclusive_minimum=True,
        )
        if validation is not True:
            return validation
        if str(inputs.get("sample_sex", "")) not in {"", "male", "female"}:
            return "sample_sex must be empty, male, or female"

        vcf = optional_path(inputs.get("vcf"))
        dependent = ("sample_id", "normal_id", "zygosity_freq")
        if not vcf and any(inputs.get(key) not in (None, "") for key in dependent):
            return "sample_id, normal_id, and zygosity_freq require a VCF input"
        min_depth = inputs.get("min_variant_depth", 20)
        if isinstance(min_depth, bool) or not isinstance(min_depth, int) or min_depth < 1:
            return "min_variant_depth must be a positive integer"
        return validate_optional_number(
            inputs.get("zygosity_freq"),
            key="zygosity_freq",
            minimum=0.0,
            maximum=1.0,
        )


__all__ = ["CNVkitCallNode"]
