from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EnvironmentSpec(BaseModel):
    type: Literal["conda", "docker", "apptainer"] = "conda"
    name: str = "bionodulo-workflow"
    file: str | None = None
    image: str | None = None
    channels: list[str] = Field(default_factory=lambda: ["conda-forge", "bioconda"])
    packages: list[str] = Field(default_factory=list)
    pip: list[str] = Field(default_factory=list)
    mounts: list[str] = Field(default_factory=list)
    notes: str = ""
