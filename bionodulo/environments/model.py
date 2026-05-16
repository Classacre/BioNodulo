"""Environment specification dataclass for BioNodulo.

Defines the data model for tool execution environments including
Pixi, Docker, Apptainer/Singularity, and bare-metal configurations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EnvironmentSpec:
    """Specification for a tool execution environment.

    Used by nodes to declare their runtime requirements and by the
    environment manager to provision the correct execution context.
    """

    # Environment type discriminator
    type: str = "none"
    """Environment type: conda, docker, apptainer, singularity, or none."""

    # Conda-specific fields
    name: str = ""
    """Conda environment name."""

    file: str = ""
    """Path to environment.yml or environment.yaml."""

    channels: list[str] = field(default_factory=list)
    """Conda channels to use (e.g., bioconda, conda-forge)."""

    packages: list[str] = field(default_factory=list)
    """Conda packages to install."""

    pip: list[str] = field(default_factory=list)
    """Additional pip packages."""

    # Container-specific fields
    image: str = ""
    """Docker/Apptainer image name or URI."""

    dockerfile: str = ""
    """Path to Dockerfile for building custom images."""

    # Apptainer/Singularity specific
    sif: str = ""
    """Path to pre-built .sif image file."""

    # Mount points for containers
    mounts: list[str] = field(default_factory=list)
    """Volume mounts in format 'host:container[:ro]'."""

    # General metadata
    notes: str = ""
    """Human-readable notes about this environment."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.type,
            "name": self.name,
            "file": self.file,
            "image": self.image,
            "dockerfile": self.dockerfile,
            "sif": self.sif,
            "channels": self.channels,
            "packages": self.packages,
            "pip": self.pip,
            "mounts": self.mounts,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentSpec:
        """Deserialize from dictionary."""
        return cls(
            type=data.get("type", "none"),
            name=data.get("name", ""),
            file=data.get("file", ""),
            image=data.get("image", ""),
            dockerfile=data.get("dockerfile", ""),
            sif=data.get("sif", ""),
            channels=data.get("channels", []),
            packages=data.get("packages", []),
            pip=data.get("pip", []),
            mounts=data.get("mounts", []),
            notes=data.get("notes", ""),
        )

    def is_container(self) -> bool:
        """Check if this is a container-based environment."""
        return self.type in ("docker", "apptainer", "singularity")

    def is_pixi(self) -> bool:
        """Check if this is a pixi-based environment."""
        return self.type in ("pixi",)
