from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UserSession(Base, TimestampMixin):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="INIT", index=True)
    lifecycle_state: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    pipeline_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    requirement_completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_requirement_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("requirement_sessions.id"),
        nullable=True,
    )
    current_blueprint_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("blueprint_versions.id"),
        nullable=True,
    )
    current_generation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_jobs.id"),
        nullable=True,
    )
    current_project_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("project_versions.id"),
        nullable=True,
    )
    current_deployment_id: Mapped[str | None] = mapped_column(
        ForeignKey("deployments.id"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (Index("ix_projects_owner_status", "owner_id", "status"),)


class ProjectMessage(Base, TimestampMixin):
    __tablename__ = "project_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    agent: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (Index("ix_project_messages_project_created", "project_id", "created_at"),)


class Prompt(Base, TimestampMixin):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(64), default="initial", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RequirementSession(Base, TimestampMixin):
    __tablename__ = "requirement_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(64), default="pending", index=True)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_module: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    normalized_requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    gathering_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ClarificationQuestion(Base, TimestampMixin):
    __tablename__ = "clarification_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    requirement_session_id: Mapped[str] = mapped_column(ForeignKey("requirement_sessions.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    module_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClarificationAnswer(Base, TimestampMixin):
    __tablename__ = "clarification_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    requirement_session_id: Mapped[str] = mapped_column(ForeignKey("requirement_sessions.id"), index=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("clarification_questions.id"), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    answered_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="user", index=True)


class BlueprintVersion(Base, TimestampMixin):
    __tablename__ = "blueprint_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    blueprint_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_requirements_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    __table_args__ = (Index("ix_blueprint_versions_project_version", "project_id", "version_number", unique=True),)


class GenerationJob(Base, TimestampMixin):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    blueprint_version_id: Mapped[str | None] = mapped_column(ForeignKey("blueprint_versions.id"), nullable=True, index=True)
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(64), default="full_generation", index=True)
    status: Mapped[str] = mapped_column(String(64), default="queued", index=True)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_spec_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GeneratedArtifact(Base, TimestampMixin):
    __tablename__ = "generated_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    generation_job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    file_path: Mapped[str] = mapped_column(String(512))
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ProjectVersion(Base, TimestampMixin):
    __tablename__ = "project_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    blueprint_version_id: Mapped[str | None] = mapped_column(ForeignKey("blueprint_versions.id"), nullable=True, index=True)
    generation_job_id: Mapped[str | None] = mapped_column(ForeignKey("generation_jobs.id"), nullable=True, index=True)
    version_label: Mapped[str] = mapped_column(String(128), index=True)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Deployment(Base, TimestampMixin):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    project_version_id: Mapped[str | None] = mapped_column(ForeignKey("project_versions.id"), nullable=True, index=True)
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), default="docker-compose", index=True)
    environment_name: Mapped[str] = mapped_column(String(128), default="development")
    status: Mapped[str] = mapped_column(String(64), default="pending", index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeploymentLog(Base, TimestampMixin):
    __tablename__ = "deployment_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info", index=True)
    message: Mapped[str] = mapped_column(Text)


class APIConfiguration(Base, TimestampMixin):
    __tablename__ = "api_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="active", index=True)


class AutomationWorkflow(Base, TimestampMixin):
    __tablename__ = "automation_workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    trigger_event: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    workflow_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="in_app", index=True)
    status: Mapped[str] = mapped_column(String(32), default="unread", index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

