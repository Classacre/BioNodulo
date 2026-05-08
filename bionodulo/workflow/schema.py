from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from bionodulo.environments.model import EnvironmentSpec


class Position(BaseModel):
    x: float = 0
    y: float = 0


class NodeUiState(BaseModel):
    pinned: bool = False
    muted: bool = False
    bypassed: bool = False
    group_id: str | None = None
    color: str | None = None
    bgcolor: str | None = None


class WorkflowNode(BaseModel):
    id: str
    type: str
    position: Position = Field(default_factory=Position)
    params: dict[str, Any] = Field(default_factory=dict)
    node_info: dict[str, Any] = Field(default_factory=dict)
    ui: NodeUiState = Field(default_factory=NodeUiState)


class WorkflowGroup(BaseModel):
    id: str
    name: str = "Group"
    position: Position = Field(default_factory=Position)
    width: float = 360
    height: float = 240
    color: str = "#38bdf8"
    collapsed: bool = False


class Endpoint(BaseModel):
    node: str
    output: str | None = None
    input: str | None = None


class WorkflowEdge(BaseModel):
    id: str
    from_: Endpoint = Field(alias="from")
    to: Endpoint

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class Workflow(BaseModel):
    version: str = "0.1.0"
    app: str = "bionodulo"
    name: str = "Untitled workflow"
    description: str = ""
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    groups: list[WorkflowGroup] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    environment: EnvironmentSpec = Field(default_factory=EnvironmentSpec)
    dependencies: dict[str, Any] = Field(default_factory=dict)


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
