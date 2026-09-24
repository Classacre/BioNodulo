"""Runtime validator for artifact coordinate semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.artifact_semantics import (
    FORMAT_COORDINATES,
    validate_artifact_semantics,
    write_artifact_semantic_evidence,
)
from bionodulo.nodes.base import BaseNode


class ValidateSemanticArtifactNode(BaseNode):
    NODE_ID = "validate_semantic_artifact"
    DISPLAY_NAME = "Validate Artifact Semantics"
    CATEGORY = "validation"
    DESCRIPTION = (
        "Validate BED/GFF3/GTF coordinate semantics and emit immutable evidence "
        "without modifying the source artifact."
    )
    SEARCH_ALIASES = ["BED", "GFF3", "GTF", "coordinates", "semantic evidence"]
    RETURN_TYPES = ("FILE", "JSON", "FILE", "STRING")
    RETURN_NAMES = (
        "validated_artifact",
        "evidence_json",
        "evidence_sha256_file",
        "evidence_sha256",
    )
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "1.0.0"
    ENVIRONMENT = {"python_stdlib_only": True}
    DOCUMENTATION_URL = "https://samtools.github.io/hts-specs/BEDv1.pdf"
    CITATION_URLS = [
        "https://samtools.github.io/hts-specs/BEDv1.pdf",
        "https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md",
        "https://www.ensembl.org/info/website/upload/gff.html",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "FILE",
                    {
                        "label": "Artifact",
                        "description": "BED, GFF3, or GTF artifact to scan",
                    },
                ),
                "format": (
                    "STRING",
                    {
                        "default": "bed",
                        "options": list(FORMAT_COORDINATES),
                        "label": "Format",
                        "description": "Normative coordinate-bearing file format",
                    },
                ),
            },
            "optional": {
                "declared_coordinate_system": (
                    "STRING",
                    {
                        "default": "unknown",
                        "options": ["unknown", *sorted(set(FORMAT_COORDINATES.values()))],
                        "label": "Coordinates",
                        "description": "Optional declared convention; contradictions fail",
                    },
                ),
                "declared_assembly": (
                    "STRING",
                    {
                        "default": "",
                        "label": "Assembly",
                        "description": "Optional declaration; not reference-identity proof",
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        path = Path(str(inputs.get("input_file", ""))).expanduser()
        if not path.is_file():
            return f"Input artifact does not exist: {path}"
        format_name = str(inputs.get("format", ""))
        if format_name not in FORMAT_COORDINATES:
            return f"Input 'format' must be one of: {', '.join(FORMAT_COORDINATES)}"
        declared = str(inputs.get("declared_coordinate_system", "unknown"))
        allowed = {"unknown", *FORMAT_COORDINATES.values()}
        if declared not in allowed:
            return "Unsupported declared coordinate system"
        if declared != "unknown" and declared != FORMAT_COORDINATES[format_name]:
            return (
                f"Declared coordinate system {declared!r} contradicts the "
                f"{format_name} standard ({FORMAT_COORDINATES[format_name]})"
            )
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str, str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(validation)
        result = validate_artifact_semantics(
            kwargs["input_file"],
            artifact_format=str(kwargs["format"]),  # type: ignore[arg-type]
            declared_coordinate_system=str(
                kwargs.get("declared_coordinate_system", "unknown")
            ),
            declared_assembly=str(kwargs.get("declared_assembly", "")),
            max_records=None,
        )
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        output_dir = base / self.NODE_ID
        evidence_path, checksum_path, evidence_hash = write_artifact_semantic_evidence(
            result, output_dir
        )
        return (
            result.source_path,
            str(evidence_path),
            str(checksum_path),
            evidence_hash,
        )
