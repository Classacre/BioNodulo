"""Pydantic models for workflow definition in BioNodulo.

WorkflowNode, WorkflowEdge, WorkflowGroup, and Workflow container
with full validation support.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkflowNodeInput(BaseModel):
    """Input slot definition for a workflow node."""

    name: str = Field(..., description="Input name")
    type: str = Field("*", description="Accepted data type")
    required: bool = Field(True, description="Whether this input is required")
    multiple: bool = Field(False, description="Whether multiple connections are allowed")
    default: Any = Field(None, description="Default value if not connected")


class WorkflowNodeOutput(BaseModel):
    """Output slot definition for a workflow node."""

    name: str = Field(..., description="Output name")
    type: str = Field("*", description="Output data type")
    is_list: bool = Field(False, description="Whether output is a list")


class WorkflowNode(BaseModel):
    """A node instance in a workflow graph.

    Represents a configured tool or operation with specific parameters.
    """

    id: str = Field(..., description="Unique node instance ID")
    type: str = Field(..., description="Node type (registered node class name)")
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0},
        description="Canvas position",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific parameter values",
    )
    node_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Cached node metadata (inputs, outputs, category)",
    )
    ui: dict[str, Any] = Field(
        default_factory=dict,
        description="UI-specific state (color, collapsed, etc.)",
    )


class WorkflowEdge(BaseModel):
    """A directed edge connecting two workflow nodes.

    Represents data flow from an output slot to an input slot.
    """

    id: str = Field(..., description="Unique edge ID")
    source_node: str = Field(..., alias="from_node", description="Source node ID")
    source_output: str = Field(..., alias="from_output", description="Source output name")
    target_node: str = Field(..., alias="to_node", description="Target node ID")
    target_input: str = Field(..., alias="to_input", description="Target input name")

    model_config = {"populate_by_name": True}


class WorkflowGroup(BaseModel):
    """A visual group containing workflow nodes.

    Groups help organize complex workflows visually.
    """

    id: str = Field(..., description="Unique group ID")
    name: str = Field("Group", description="Display name")
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0},
        description="Canvas position",
    )
    width: float = Field(300.0, description="Group width in pixels")
    height: float = Field(200.0, description="Group height in pixels")
    color: str = Field("#3f789e", description="Group color (hex)")
    collapsed: bool = Field(False, description="Whether group is collapsed")
    node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of nodes in this group",
    )


class WorkflowOutput(BaseModel):
    """Workflow output specification.

    Defines named outputs that the workflow produces.
    """

    name: str = Field(..., description="Output name")
    node_id: str = Field(..., description="Source node ID")
    output_name: str = Field(..., description="Source output slot name")


class WorkflowEnvironment(BaseModel):
    """Execution environment specification for a workflow."""

    conda_env: str | None = Field(None, description="Conda environment name")
    container: str | None = Field(None, description="Container image URI")
    variables: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables",
    )


class WorkflowDependency(BaseModel):
    """External dependency required by the workflow."""

    name: str = Field(..., description="Package/tool name")
    version: str | None = Field(None, description="Required version")
    source: str = Field("conda", description="Installation source (conda, pip, container)")


class WorkflowParameter(BaseModel):
    """Reusable workflow-level parameter definition.

    Workflows can declare shared values and reference them in node inputs or
    params with ``{{name}}`` placeholders. Execution resolves stored values,
    defaults, and per-run overrides before node inputs are evaluated.
    """

    name: str = Field(..., description="Unique parameter name")
    type: str = Field("STRING", description="Parameter value type")
    required: bool = Field(False, description="Whether the parameter must be supplied")
    default: Any = Field(None, description="Default parameter value")
    value: Any = Field(None, description="Current parameter value")
    description: str = Field("", description="Human-readable parameter description")


class Workflow(BaseModel):
    """Complete workflow definition.

    The top-level container for a BioNodulo workflow with nodes,
    edges, groups, and metadata.
    """

    version: str = Field("1.0", description="Workflow format version")
    app: str = Field("bionodulo", description="Application identifier")
    name: str = Field("Untitled", description="Workflow display name")
    description: str = Field("", description="Workflow description")
    nodes: list[WorkflowNode] = Field(default_factory=list, description="Workflow nodes")
    edges: list[WorkflowEdge] = Field(default_factory=list, description="Node connections")
    groups: list[WorkflowGroup] = Field(default_factory=list, description="Visual groups")
    outputs: list[WorkflowOutput] = Field(default_factory=list, description="Named outputs")
    environment: WorkflowEnvironment = Field(
        default_factory=lambda: WorkflowEnvironment(),  # type: ignore[call-arg]
        description="Execution environment",
    )
    dependencies: list[WorkflowDependency] = Field(
        default_factory=list,
        description="External dependencies",
    )
    parameters: list[WorkflowParameter] = Field(
        default_factory=list,
        description="Workflow-level parameter definitions",
    )

    def get_node(self, node_id: str) -> WorkflowNode | None:
        """Look up a node by its ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_node_inputs(self, node_id: str) -> list[WorkflowEdge]:
        """Get all edges targeting a specific node."""
        return [e for e in self.edges if e.target_node == node_id]

    def get_node_outputs(self, node_id: str) -> list[WorkflowEdge]:
        """Get all edges originating from a specific node."""
        return [e for e in self.edges if e.source_node == node_id]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dictionary."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workflow:
        """Deserialize from a plain dictionary."""
        return cls.model_validate(data)
