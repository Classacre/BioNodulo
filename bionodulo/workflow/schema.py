from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from bionodulo.environments.model import EnvironmentSpec


class Position(BaseModel):
    x: float = 0
    y: float = 0


class WorkflowNode(BaseModel):
    id: str
    type: str
    position: Position = Field(default_factory=Position)
    params: dict[str, Any] = Field(default_factory=dict)


class Endpoint(BaseModel):
    node: str
    output: str | None = None
    input: str | None = None


class WorkflowEdge(BaseModel):
    id: str
    from_: Endpoint = Field(alias="from")
    to: Endpoint

    model_config = {"populate_by_name": True}


class Workflow(BaseModel):
    version: str = "0.1.0"
    app: str = "bionodulo"
    name: str = "Untitled workflow"
    description: str = ""
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    environment: EnvironmentSpec = Field(default_factory=EnvironmentSpec)


class ValidationIssue(BaseModel):
    node_id: str | None = None
    edge_id: str | None = None
    level: str = "error"
    code: str
    message: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)
