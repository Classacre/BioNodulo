from __future__ import annotations

from pydantic import BaseModel, Field

from bionodulo.workflow.schema import Workflow


class RunCreateRequest(BaseModel):
    workflow: Workflow
    mock_tools: bool | None = None
    force: bool = False
    force_nodes: list[str] = Field(default_factory=list)
    options: dict = Field(default_factory=dict)


class PromptCompatibilityRequest(BaseModel):
    prompt: Workflow | dict
    mock_tools: bool | None = None
    force: bool = False
    options: dict = Field(default_factory=dict)


class WorkflowExtractRequest(BaseModel):
    path: str | None = None
    content: str | None = None
    content_encoding: str | None = None
    filename: str = "workflow-output"


class WorkflowExportRequest(BaseModel):
    workflow: Workflow
    format: str = "snakemake"


class ManagerGitRequest(BaseModel):
    url: str
    name: str | None = None


class ManagerPackageRequest(BaseModel):
    package: str


class ValidationRequest(BaseModel):
    workflow: Workflow
    mock_tools: bool = True


class AIProviderSettings(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.2


class AIChatMessage(BaseModel):
    role: str
    content: str


class AIChatRequest(BaseModel):
    workflow: Workflow
    messages: list[AIChatMessage] = Field(default_factory=list)
    settings: AIProviderSettings = Field(default_factory=AIProviderSettings)
