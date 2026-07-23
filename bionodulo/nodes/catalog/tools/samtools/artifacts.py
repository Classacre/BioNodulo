"""Samtools artifact types and compatibility registry.

The seed catalog in :mod:`bionodulo.nodes.catalog.artifacts` intentionally
remains a five-type compatibility fixture.  Samtools types are additive and
are exposed through ``SAMTOOLS_ARTIFACT_REGISTRY`` instead of changing that
fixture in place.
"""

from __future__ import annotations

from typing import Final

from bionodulo.nodes.catalog.artifacts import ARTIFACT_TYPES
from bionodulo.nodes.contract.artifacts import ArtifactContainer, ArtifactRegistry, ArtifactType


SAMTOOLS_ARTIFACT_TYPES: Final[tuple[ArtifactType, ...]] = (
    ArtifactType(
        type_id="alignment",
        container=ArtifactContainer.FILE,
        parents=("artifact.file",),
    ),
    ArtifactType(
        type_id="alignment.union",
        container=ArtifactContainer.FILE,
        parents=("alignment",),
        accepted_sources=("alignment.bam", "alignment.sam"),
    ),
    ArtifactType(
        type_id="alignment.sam",
        container=ArtifactContainer.FILE,
        parents=("alignment",),
        extensions=(".sam",),
    ),
    ArtifactType(
        type_id="alignment.bam",
        container=ArtifactContainer.FILE,
        parents=("alignment",),
        extensions=(".bam",),
    ),
    ArtifactType(
        type_id="alignment.bai",
        container=ArtifactContainer.FILE,
        parents=("artifact.file",),
        extensions=(".bai",),
    ),
    ArtifactType(
        type_id="statistics.text",
        container=ArtifactContainer.FILE,
        parents=("file.text",),
        extensions=(".txt",),
    ),
)

SAMTOOLS_ARTIFACT_REGISTRY: Final[ArtifactRegistry] = ArtifactRegistry(
    types=(*ARTIFACT_TYPES, *SAMTOOLS_ARTIFACT_TYPES),
)

__all__ = ["SAMTOOLS_ARTIFACT_REGISTRY", "SAMTOOLS_ARTIFACT_TYPES"]
