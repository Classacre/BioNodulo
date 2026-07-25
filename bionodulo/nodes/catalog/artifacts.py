from typing import Final

from bionodulo.nodes.contract.artifacts import (
    ArtifactContainer,
    ArtifactRegistry,
    ArtifactType,
)


ARTIFACT_TYPES: Final[tuple[ArtifactType, ...]] = (
    ArtifactType(
        type_id="artifact.file",
        container=ArtifactContainer.FILE,
    ),
    ArtifactType(
        type_id="artifact.directory",
        container=ArtifactContainer.DIRECTORY,
    ),
    ArtifactType(
        type_id="file.text",
        container=ArtifactContainer.FILE,
        parents=("artifact.file",),
        extensions=(".txt",),
    ),
    ArtifactType(
        type_id="report.html",
        container=ArtifactContainer.FILE,
        parents=("file.text",),
        extensions=(".html",),
    ),
    ArtifactType(
        type_id="value.string",
        container=None,
    ),
)

ARTIFACT_REGISTRY: Final[ArtifactRegistry] = ArtifactRegistry(types=ARTIFACT_TYPES)
