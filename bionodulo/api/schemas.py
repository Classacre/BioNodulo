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
    name: str = Field("Untitled", description="Human-readable run name")
    environment: str | None = Field(None, description="Conda env or container to use")
    no_cache: bool = Field(False, description="Force re-execution by bypassing cache")


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
    name: str = Field(..., description="Job name")
    cpus: int | None = Field(None, description="CPU override")
    memory: str | None = Field(None, description="Memory override")
    walltime: str | None = Field(None, description="Walltime override")
    dependency_jobs: list[str] = Field(
        default_factory=list,
        description="Job IDs this job depends on",
    )


# ---------------------------------------------------------------------------
# Manager install requests
# ---------------------------------------------------------------------------

class ManagerInstallPlanRequest(BaseModel):
    """Request body for POST /manager/install-plan."""

    nodes: list[str] = Field(..., description="Node names to plan install for")


class ManagerInstallRequest(BaseModel):
    """Request body for POST /manager/install."""

    plan: dict[str, Any] = Field(..., description="Install plan from install-plan response")
    confirm: bool = Field(False, description="Whether to actually execute the install")


class ManagerDiagnoseRequest(BaseModel):
    """Request body for POST /manager/diagnose."""

    workflow: dict[str, Any] = Field(..., description="Workflow to diagnose")


class ManagerResolveRequest(BaseModel):
    """Request body for POST /manager/resolve."""

    workflow: dict[str, Any] = Field(..., description="Workflow to resolve dependencies for")


class ManagerInstallDepsRequest(BaseModel):
    """Request body for POST /manager/install-deps."""

    report: dict[str, Any] = Field(..., description="Resolution report from /manager/resolve")
    env_strategy: str = Field("shared", description="Install strategy: 'shared' or 'isolated'")


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
