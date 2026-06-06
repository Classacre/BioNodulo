"""Pydantic models for all API request/response schemas in BioNodulo.

ValidationRequest, RunCreateRequest, AIChatRequest, workflow import/export,
manager operations, HPC configuration, and settings management.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Workflow requests
# ---------------------------------------------------------------------------

class ValidationRequest(BaseModel):
    """Request body for POST /workflow/validate."""

    workflow: dict[str, Any] = Field(..., description="Workflow JSON object")


class RunCreateRequest(BaseModel):
    """Request body for POST /runs."""

    workflow: dict[str, Any] = Field(..., description="Workflow JSON object to execute")
    workflow_id: str | None = Field(None, description="Collaborative workflow UUID, when applicable")
    name: str = Field("Untitled", description="Human-readable run name")
    environment: str | None = Field(None, description="Conda env or container to use")
    no_cache: bool = Field(False, description="Force re-execution by bypassing cache")
    dry_run: bool = Field(
        False,
        description="Resolve the workflow and return command/output/cache previews without submitting execution",
    )
    force_nodes: list[str] = Field(
        default_factory=list,
        description="Specific node IDs to force re-execution",
    )
    target_nodes: list[str] = Field(
        default_factory=list,
        description="Node IDs to execute, together with their upstream dependencies",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime workflow parameter overrides keyed by parameter name",
    )


class QueueReorderRequest(BaseModel):
    """Request body for POST /queue/reorder."""

    run_id: str = Field(..., description="Pending run ID to move")
    index: int | None = Field(None, ge=0, description="Zero-based destination index")
    before_run_id: str | None = Field(None, description="Move before this pending run ID")
    after_run_id: str | None = Field(None, description="Move after this pending run ID")


class PauseRequestResolveRequest(BaseModel):
    """Request body for POST /pause_requests/resolve."""

    action: Literal["approve", "reject"] = Field(..., description="Review decision to persist")
    node_id: str | None = Field(None, description="Node ID whose pause request should be resolved")
    pause_file: str | None = Field(None, description="Pause request JSON path relative to workspace")
    reviewer: str = Field("", description="Reviewer name or identifier")
    comment: str = Field("", description="Optional review comment")


class WorkflowTriggerEvaluateRequest(BaseModel):
    """Request body for POST /workflow_triggers/evaluate."""

    now: str | None = Field(
        None,
        description="Optional ISO timestamp used to evaluate due scheduled triggers",
    )


class WorkflowExportRequest(BaseModel):
    """Request body for POST /workflow/export."""

    workflow: dict[str, Any] = Field(..., description="Workflow JSON to export")
    format: Literal["snakemake", "nextflow", "cwl", "galaxy", "json"] = Field(
        ..., description="Target export format"
    )
    name: str = Field("workflow", description="Output filename base")


class WorkflowExtractRequest(BaseModel):
    """Request body for extracting sub-workflow."""

    workflow: dict[str, Any] = Field(..., description="Full workflow JSON")
    node_ids: list[str] = Field(..., description="Node IDs to extract")
    name: str = Field("extracted", description="Name for the extracted workflow")


class ImportWorkflowRequest(BaseModel):
    """Request body for POST /workflow/import."""

    source: str = Field(..., description="Source format (snakemake, nextflow, cwl, galaxy)")
    content: str | None = Field(None, description="File content as string")
    file_path: str | None = Field(None, description="Path to uploaded file")


# ---------------------------------------------------------------------------
# Manager requests
# ---------------------------------------------------------------------------

class ManagerGitRequest(BaseModel):
    """Request body for installing a custom node from a Git repository."""

    url: str = Field(..., description="Git repository URL")
    branch: str = Field("main", description="Git branch to checkout")
    commit: str | None = Field(None, description="Specific commit hash")
    directory: str | None = Field(None, description="Target directory name")


class ManagerPackageRequest(BaseModel):
    """Request body for manager update/remove operations on a package."""

    name: str = Field(..., description="Package or node name")
    version: str | None = Field(None, description="Target version")


# ---------------------------------------------------------------------------
# AI assistant requests
# ---------------------------------------------------------------------------

class AIChatFile(BaseModel):
    """An attached file sent with an AI chat message."""

    name: str = Field(..., description="Original file name")
    mime_type: str = Field(..., description="MIME type")
    content: str = Field(..., description="Base64-encoded file content")


class AIChatRequest(BaseModel):
    """Request body for POST /ai/chat."""

    message: str = Field(..., description="User message text")
    workflow: dict[str, Any] | None = Field(None, description="Current workflow context")
    workflow_id: str | None = Field(None, description="Stable ID of the active workflow")
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Previous conversation messages",
    )
    stream: bool = Field(False, description="Whether to stream the response")
    provider: str | None = Field(None, description="LLM provider override")
    model: str | None = Field(None, description="Model name override")
    files: list[AIChatFile] = Field(default_factory=list, description="Attached files")


class AIChatResponseStep(BaseModel):
    """A single step in the AI reasoning chain."""

    type: str = Field(..., description="thinking, tool_call, tool_result, propose_changes, reply")
    content: str = Field("", description="Text content for thinking/reply")
    name: str = Field("", description="Tool name for tool_call/tool_result")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    result: dict[str, Any] = Field(default_factory=dict, description="Tool execution result")
    workflow: dict[str, Any] | None = Field(None, description="Proposed workflow")
    description: str = Field("", description="Human-readable description of proposed changes")


# ---------------------------------------------------------------------------
# Settings requests
# ---------------------------------------------------------------------------

class SettingsSaveRequest(BaseModel):
    """Request body for POST /settings (bulk save)."""

    settings: dict[str, Any] = Field(..., description="Settings key-value pairs to save")


class SettingsSetRequest(BaseModel):
    """Request body for POST /settings/{id} (single setting)."""

    value: Any = Field(..., description="Setting value")


# ---------------------------------------------------------------------------
# Workspace requests
# ---------------------------------------------------------------------------

class WorkspaceRootRequest(BaseModel):
    """Request body for POST /workspace/root."""

    path: str = Field(..., description="New workspace root directory path")


class FileOperationRequest(BaseModel):
    """Request body for POST /workspace/file-operation."""

    operation: Literal["copy", "move"] = Field(..., description="File operation type")
    source: str = Field(..., description="Source file path")
    target: str = Field(..., description="Target file path")


class DeleteFilesRequest(BaseModel):
    """Request body for POST /workspace/delete."""

    paths: list[str] = Field(..., description="Paths to delete")


# ---------------------------------------------------------------------------
# HPC requests
# ---------------------------------------------------------------------------

class HPCConfigureRequest(BaseModel):
    """Request body for POST /hpc/configure."""

    backend: Literal["slurm", "pbs", "sge", "local"] = Field(
        ..., description="HPC scheduler backend"
    )
    host: str | None = Field(None, description="Remote host address")
    user: str | None = Field(None, description="SSH username")
    key_path: str | None = Field(None, description="Path to SSH private key")
    partition: str | None = Field(None, description="SLURM partition / PBS queue")
    account: str | None = Field(None, description="Project account for billing")
    default_cpus: int = Field(1, description="Default CPU count per job")
    default_memory: str = Field("4G", description="Default memory per job")
    default_walltime: str = Field("01:00:00", description="Default walltime limit")


class HPCSubmitRequest(BaseModel):
    """Request body for POST /hpc/submit."""

    workflow: dict[str, Any] = Field(..., description="Workflow to submit")
    workflow_id: str | None = Field(None, description="Collaborative workflow UUID, when applicable")
    name: str = Field(..., description="Job name")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime workflow parameter overrides keyed by parameter name",
    )
    cpus: int | None = Field(None, description="CPU override")
    memory: str | None = Field(None, description="Memory override")
    walltime: str | None = Field(None, description="Walltime override")
    dependency_jobs: list[str] = Field(
        default_factory=list,
        description="Job IDs this job depends on",
    )


class ManagerDiagnoseRequest(BaseModel):
    """Request body for POST /manager/diagnose."""

    workflow: dict[str, Any] = Field(..., description="Workflow to diagnose")


class ManagerResolveRequest(BaseModel):
    """Request body for POST /manager/resolve."""

    workflow: dict[str, Any] = Field(..., description="Workflow to resolve dependencies for")


# ---------------------------------------------------------------------------
# Environment requests
# ---------------------------------------------------------------------------

class EnvironmentCreateRequest(BaseModel):
    """Request body for POST /manager/environments."""

    name: str = Field(..., description="Environment name")
    packages: list[str] = Field(default_factory=list, description="Conda packages to install")
    channels: list[str] = Field(
        default_factory=lambda: ["bioconda", "conda-forge", "defaults"],
        description="Conda channels",
    )
    pip_packages: list[str] = Field(default_factory=list, description="Pip packages to install")


class EnvironmentInstallRequest(BaseModel):
    """Request body for installing packages into an existing environment."""

    packages: list[str] = Field(..., description="Conda packages to install")
    channels: list[str] = Field(
        default_factory=lambda: ["bioconda", "conda-forge", "defaults"],
        description="Conda channels",
    )


class WorkflowEnvironmentRequest(BaseModel):
    """Request body for setting a workflow's execution environment."""

    workflow: dict[str, Any] = Field(..., description="Workflow JSON")
    environment: dict[str, Any] = Field(..., description="Environment spec")


class DependencyTreeRequest(BaseModel):
    """Request body for POST /manager/dependency-tree."""

    workflow: dict[str, Any] = Field(..., description="Workflow to analyze")


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class GenericMessageResponse(BaseModel):
    """Simple message response wrapper."""

    message: str = Field(..., description="Human-readable message")
    success: bool = Field(True, description="Operation success indicator")


# ---------------------------------------------------------------------------
# Getting Started requests
# ---------------------------------------------------------------------------

class ExampleDataDownloadRequest(BaseModel):
    """Request body for POST /getting-started/download."""

    url: str | None = Field(
        None,
        description="Optional URL override. Defaults to the configured example-data release asset.",
    )


class ErrorResponse(BaseModel):
    """Standardized error response."""

    detail: str = Field(..., description="Error description")
    error_code: str | None = Field(None, description="Machine-readable error code")


# ---------------------------------------------------------------------------
# Collaboration requests / responses
# ---------------------------------------------------------------------------

class ShareWorkflowRequest(BaseModel):
    """Request body for POST /api/collab/share."""

    workflow_id: str = Field(..., description="Workflow UUID to share")
    user_id: str = Field(..., description="User to invite")
    role: Literal["owner", "editor", "viewer", "commenter"] = Field(
        "viewer", description="Permission level"
    )


class ShareWorkflowResponse(BaseModel):
    """Response for a successful share operation."""

    share_id: str = Field(..., description="Unique share record ID")
    workflow_id: str = Field(..., description="Workflow UUID")
    user_id: str = Field(..., description="Invited user")
    role: str = Field(..., description="Granted role")
    invited_by: str = Field("", description="User who sent the invite")
    invited_at: str = Field(..., description="ISO timestamp of invitation")


class CreateCollabRoomRequest(BaseModel):
    """Request body for POST /api/collab/rooms."""

    workflow_id: str = Field(..., min_length=1, max_length=160, description="Workflow room ID")
    role: Literal["editor", "viewer", "commenter"] = Field(
        "editor",
        description="Role granted to visitors who open the generated link",
    )


class CreateCollabRoomResponse(BaseModel):
    """Temporary invite link metadata for a collaboration room."""

    workflow_id: str = Field(..., description="Workflow room ID")
    invite_token: str = Field(..., description="Temporary invite token")
    role: str = Field(..., description="Role granted by the invite")
    created_by: str = Field(..., description="User who created the room")
    created_at: str = Field(..., description="ISO timestamp of room creation")
    public_url: str | None = Field(
        None,
        description="Public app base URL to use for invite links when the server is already tunneled",
    )


class CollabTunnelResponse(BaseModel):
    """Current public collaboration URL status."""

    public_url: str | None = Field(None, description="Public app base URL when available")
    provider: str | None = Field(None, description="Tunnel provider, if one is active")
    status: Literal["public", "local", "unavailable"] = Field(..., description="Public-link availability")
    message: str = Field(..., description="Human-readable status detail")


class JoinCollabRoomRequest(BaseModel):
    """Request body for POST /api/collab/rooms/join."""

    workflow_id: str = Field(..., min_length=1, max_length=160, description="Workflow room ID")
    invite_token: str | None = Field(None, description="Temporary invite token from a share link")


class JoinCollabRoomResponse(BaseModel):
    """Response for joining a collaboration room."""

    workflow_id: str = Field(..., description="Workflow room ID")
    user_id: str = Field(..., description="Joined user ID")
    role: str = Field(..., description="Granted or existing role")
    joined_at: str = Field(..., description="ISO timestamp of the join")


class RoomStatusResponse(BaseModel):
    """Response for GET /api/collab/room/{workflow_id}."""

    workflow_id: str = Field(..., description="Workflow UUID")
    active: bool = Field(..., description="Whether the room is currently open")
    users: list[dict[str, Any]] = Field(default_factory=list, description="Active users")
    created_at: str | None = Field(None, description="Room creation ISO timestamp")
    client_count: int = Field(0, description="Number of connected WebSocket clients")


# ---------------------------------------------------------------------------
# Authentication requests / responses
# ---------------------------------------------------------------------------

class AuthTokenRequest(BaseModel):
    """Request body for POST /api/auth/token."""

    name: str = Field(..., description="Human-readable display name")


class AuthTokenResponse(BaseModel):
    """Response for POST /api/auth/token."""

    token: str = Field(..., description="Signed JWT string")
    user_id: str = Field(..., description="Opaque user identifier")
    name: str = Field(..., description="Display name from request")


class AuthMeResponse(BaseModel):
    """Response for GET /api/auth/me."""

    user_id: str = Field(..., description="User identifier from token sub claim")
    name: str = Field(..., description="Display name from token")
    role: str = Field(..., description="Role from token (owner/editor/viewer/commenter)")


# ---------------------------------------------------------------------------
# Phase 3 collaboration request models
# ---------------------------------------------------------------------------


class CreateCommentRequest(BaseModel):
    """Request body for POST /api/collab/workflows/{id}/comments."""

    node_id: str | None = Field(None, description="Optional node ID to attach the comment to")
    content: str = Field(..., min_length=1, max_length=5000, description="Comment text")
    parent_id: str | None = Field(None, description="Parent comment ID for replies")


class UpdateCommentRequest(BaseModel):
    """Request body for PATCH /api/collab/comments/{id}."""

    content: str = Field(..., min_length=1, max_length=5000, description="Updated comment text")


class CreateVersionRequest(BaseModel):
    """Request body for POST /api/collab/workflows/{id}/versions."""

    name: str | None = Field(None, description="Version name; None for auto-generated")


class CreateTemplateRequest(BaseModel):
    """Request body for POST /api/collab/templates."""

    workflow_id: str = Field(..., description="Source workflow UUID")
    title: str = Field(..., min_length=1, max_length=200, description="Template title")
    description: str = Field(default="", max_length=2000, description="Template description")
    tags: str = Field(default="", max_length=500, description="Comma-separated tags")
    is_public: bool = Field(default=False, description="Make template publicly visible")
