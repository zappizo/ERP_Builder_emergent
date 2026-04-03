from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(ORMModel):
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class PipelineStageRead(BaseModel):
    status: str = "pending"
    output: Any | None = None
    updated_at: str | None = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    prompt: str = Field(min_length=10)
    description: str | None = None
    template_id: str | None = None


class PromptRead(ORMModel):
    id: str
    project_id: str
    created_by_id: str
    content: str
    kind: str
    created_at: datetime


class MessageRead(ORMModel):
    id: str
    project_id: str
    role: str
    content: str
    agent: str | None = None
    created_at: datetime


class RequirementSessionRead(ORMModel):
    id: str
    project_id: str
    status: str
    completeness_score: float
    current_module: str | None = None
    summary: str | None = None
    analysis_json: dict[str, Any]
    normalized_requirements: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectRead(ORMModel):
    id: str
    owner_id: str
    name: str
    description: str | None = None
    prompt: str = Field(validation_alias="prompt_text")
    selected_template_id: str | None = None
    selected_template_name: str | None = None
    selected_template_reference: str | None = None
    status: str
    lifecycle_state: str
    requirement_completeness: float
    pipeline: dict[str, PipelineStageRead]
    current_requirement_session_id: str | None = None
    current_blueprint_version_id: str | None = None
    current_generation_job_id: str | None = None
    current_project_version_id: str | None = None
    current_deployment_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    response: str
    status: str
    auto_advance: bool = False
    analysis: dict[str, Any] | None = None
    requirements: dict[str, Any] | None = None
    current_module: str | None = None
    progress: str | None = None
    completeness_score: float | None = None
    missing_topics: list[str] = Field(default_factory=list)
    captured_topics: list[str] = Field(default_factory=list)
    question_rationale: str | None = None
    analysis_model: str | None = None


class GenerationTriggerRequest(BaseModel):
    change_request: str | None = None


class GenerationJobRead(ORMModel):
    id: str
    project_id: str
    blueprint_version_id: str | None = None
    job_type: str
    status: str
    current_stage: str | None = None
    change_request: str | None = None
    result_summary_json: dict[str, Any]
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LocalRunRead(BaseModel):
    project_id: str
    status: str
    message: str
    workspace_path: str
    frontend_url: str
    backend_url: str
    frontend_port: int
    backend_port: int


class BlueprintVersionRead(ORMModel):
    id: str
    project_id: str
    version_number: int
    status: str
    summary: str | None = None
    blueprint_json: dict[str, Any]
    source_requirements_json: dict[str, Any]
    created_at: datetime


class ProjectVersionRead(ORMModel):
    id: str
    project_id: str
    blueprint_version_id: str | None = None
    generation_job_id: str | None = None
    version_label: str
    changelog: str | None = None
    snapshot_json: dict[str, Any]
    created_at: datetime


class DeploymentCreateRequest(BaseModel):
    project_id: str
    provider: str = "docker-compose"
    environment_name: str = "development"
    config: dict[str, Any] = Field(default_factory=dict)


class DeploymentRead(ORMModel):
    id: str
    project_id: str
    project_version_id: str | None = None
    provider: str
    environment_name: str
    status: str
    config_json: dict[str, Any]
    status_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DeploymentLogRead(ORMModel):
    id: str
    deployment_id: str
    level: str
    message: str
    created_at: datetime


class TemplateSourceFileRead(BaseModel):
    relative_path: str
    language: str = "text"
    role: str | None = None


class ErpTemplateRead(BaseModel):
    id: str
    name: str
    display_name: str
    reference_project: str
    summary: str = ""
    relative_directory: str
    status: str = "ready"
    source_files: list[TemplateSourceFileRead] = Field(default_factory=list)


class APIConfigurationUpsertRequest(BaseModel):
    provider: str
    display_name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class APIConfigurationRead(ORMModel):
    id: str
    user_id: str
    provider: str
    display_name: str | None = None
    config_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class AutomationWorkflowCreateRequest(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=255)
    trigger_event: str = Field(min_length=2, max_length=128)
    workflow_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"


class AutomationWorkflowRead(ORMModel):
    id: str
    project_id: str
    name: str
    trigger_event: str
    status: str
    workflow_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class NotificationRead(ORMModel):
    id: str
    user_id: str
    project_id: str | None = None
    channel: str
    status: str
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime


class StatusResponse(BaseModel):
    status: str
    message: str


class RequirementAnalysisPayload(BaseModel):
    business_type: str = ""
    industry: str = ""
    scale: str = "small"
    suggested_modules: list[str] = Field(default_factory=list)
    complexity: str = "standard"
    key_requirements: list[str] = Field(default_factory=list)
    summary: str = ""

    model_config = ConfigDict(extra="allow")


class RequirementModulePayload(BaseModel):
    name: str
    description: str = ""
    features: list[str] = Field(default_factory=list)
    entities: list[Any] = Field(default_factory=list)
    workflows: list[Any] = Field(default_factory=list)
    user_roles: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class RequirementsDocumentPayload(BaseModel):
    business_type: str = ""
    industry: str = ""
    scale: str = "small"
    modules: list[RequirementModulePayload] = Field(default_factory=list)
    general_requirements: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class GatheringPayload(BaseModel):
    complete: bool = False
    assistant_response: str | None = None
    question: str | None = None
    current_module: str | None = None
    progress_summary: str | None = None
    completeness_score: float | None = None
    missing_topics: list[str] = Field(default_factory=list)
    captured_topics: list[str] = Field(default_factory=list)
    question_rationale: str | None = None
    requirements: RequirementsDocumentPayload | None = None

    model_config = ConfigDict(extra="allow")


class ArchitecturePayload(BaseModel):
    system_name: str = "AI ERP Builder"
    description: str = ""
    modules: list[dict[str, Any]] = Field(default_factory=list)
    database_schema: dict[str, Any] = Field(default_factory=dict)
    user_roles: list[dict[str, Any]] = Field(default_factory=list)
    tech_stack: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class MasterJsonPayload(BaseModel):
    version: str = "1.0.0"
    system: dict[str, Any] = Field(default_factory=dict)
    modules: list[dict[str, Any]] = Field(default_factory=list)
    database: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class GeneratedFilePayload(BaseModel):
    path: str
    language: str = "text"
    content: str

    model_config = ConfigDict(extra="allow")


class GeneratedBundlePayload(BaseModel):
    files: list[GeneratedFilePayload] = Field(default_factory=list)
    dependencies: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class CodeReviewPayload(BaseModel):
    overall_score: float = 0.0
    summary: str = ""
    frontend_review: dict[str, Any] = Field(default_factory=dict)
    backend_review: dict[str, Any] = Field(default_factory=dict)
    security_checks: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")
