from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ensure_active_user
from ..models import User
from ..schemas import (
    BlueprintVersionRead,
    ChatRequest,
    ChatResponse,
    GenerationJobRead,
    MessageRead,
    PipelineStageRead,
    ProjectCreateRequest,
    ProjectVersionRead,
    PromptRead,
    RequirementSessionRead,
)
from ..services import (
    create_project,
    ensure_markdown_documentation,
    get_pipeline_stage,
    get_project_or_404,
    get_project_requirement_session,
    handle_project_chat,
    list_project_blueprints,
    list_project_generation_jobs,
    list_project_messages,
    list_project_prompts,
    list_project_versions,
    list_projects,
    serialize_project,
    soft_delete_project,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _project_payload(project, *, list_view: bool = False) -> dict[str, Any]:
    data = serialize_project(project).model_dump(mode="json")
    data["pipeline"] = dict(data.get("pipeline") or {})

    hidden_stages = {"frontend_generation", "backend_generation", "json_transform", "code_review"}
    if list_view:
        hidden_stages = set(data["pipeline"].keys())

    for stage in hidden_stages:
        if stage in data["pipeline"]:
            data["pipeline"][stage]["output"] = None
    return data


@router.post("")
def create_project_endpoint(
    payload: ProjectCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> dict[str, Any]:
    project = create_project(db, user, payload)
    return _project_payload(project)


@router.get("")
def list_projects_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[dict[str, Any]]:
    projects = list_projects(db, user)
    return [_project_payload(project, list_view=True) for project in projects]


@router.get("/{project_id}")
def get_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> dict[str, Any]:
    project = get_project_or_404(db, project_id, user)
    return _project_payload(project)


@router.delete("/{project_id}")
def delete_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> dict[str, str]:
    project = get_project_or_404(db, project_id, user)
    soft_delete_project(db, project, user)
    return {"status": "deleted"}


@router.get("/{project_id}/messages", response_model=list[MessageRead])
def get_project_messages_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[MessageRead]:
    project = get_project_or_404(db, project_id, user)
    return list_project_messages(db, project)


@router.post("/{project_id}/chat", response_model=ChatResponse)
async def chat_endpoint(
    project_id: str,
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> ChatResponse:
    project = get_project_or_404(db, project_id, user)
    return await handle_project_chat(db, project, user, payload.message, background_tasks)


@router.get("/{project_id}/pipeline/{stage}", response_model=PipelineStageRead)
async def get_pipeline_stage_endpoint(
    project_id: str,
    stage: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> PipelineStageRead:
    project = get_project_or_404(db, project_id, user)
    if stage == "json_transform":
        await ensure_markdown_documentation(db, project)
        db.refresh(project)
    return get_pipeline_stage(project, stage)


@router.get("/{project_id}/prompts", response_model=list[PromptRead])
def get_project_prompts_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[PromptRead]:
    project = get_project_or_404(db, project_id, user)
    return list_project_prompts(db, project)


@router.get("/{project_id}/requirement-session", response_model=RequirementSessionRead)
def get_requirement_session_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> RequirementSessionRead:
    project = get_project_or_404(db, project_id, user)
    return get_project_requirement_session(db, project)


@router.get("/{project_id}/jobs", response_model=list[GenerationJobRead])
def list_generation_jobs_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[GenerationJobRead]:
    project = get_project_or_404(db, project_id, user)
    return list_project_generation_jobs(db, project)


@router.get("/{project_id}/blueprints", response_model=list[BlueprintVersionRead])
def list_blueprints_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[BlueprintVersionRead]:
    project = get_project_or_404(db, project_id, user)
    return list_project_blueprints(db, project)


@router.get("/{project_id}/versions", response_model=list[ProjectVersionRead])
def list_versions_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[ProjectVersionRead]:
    project = get_project_or_404(db, project_id, user)
    return list_project_versions(db, project)
