from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from agents import (
    backend_generator,
    code_reviewer,
    erp_architect,
    frontend_generator,
    is_valid_markdown_blueprint,
    json_transformer,
    markdown_blueprint_generator,
    requirement_analyzer,
    requirement_gatherer,
)

from .db import SessionLocal
from .models import (
    APIConfiguration,
    AuditLog,
    AutomationWorkflow,
    BlueprintVersion,
    ClarificationAnswer,
    ClarificationQuestion,
    Deployment,
    DeploymentLog,
    GeneratedArtifact,
    GenerationJob,
    Notification,
    Project,
    ProjectMessage,
    ProjectVersion,
    Prompt,
    RequirementSession,
    User,
)
from .schemas import (
    APIConfigurationRead,
    APIConfigurationUpsertRequest,
    ArchitecturePayload,
    AutomationWorkflowCreateRequest,
    AutomationWorkflowRead,
    BlueprintVersionRead,
    ChatResponse,
    CodeReviewPayload,
    DeploymentCreateRequest,
    DeploymentLogRead,
    DeploymentRead,
    GatheringPayload,
    GeneratedBundlePayload,
    GenerationJobRead,
    MasterJsonPayload,
    MessageRead,
    NotificationRead,
    PipelineStageRead,
    ProjectCreateRequest,
    ProjectRead,
    ProjectVersionRead,
    PromptRead,
    RequirementAnalysisPayload,
    RequirementSessionRead,
    RequirementsDocumentPayload,
)


PIPELINE_STAGES = [
    "requirement_analysis",
    "requirement_gathering",
    "architecture",
    "json_transform",
    "frontend_generation",
    "backend_generation",
    "code_review",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat()


def default_pipeline_state() -> dict[str, dict[str, Any]]:
    return {
        stage: {"status": "pending", "output": None, "updated_at": None}
        for stage in PIPELINE_STAGES
    }


def ensure_pipeline_state(project: Project) -> dict[str, dict[str, Any]]:
    state = dict(project.pipeline_state or {})
    for stage in PIPELINE_STAGES:
        current = dict(state.get(stage) or {})
        current.setdefault("status", "pending")
        current.setdefault("output", None)
        current.setdefault("updated_at", None)
        state[stage] = current
    project.pipeline_state = state
    return state


def update_stage(project: Project, stage: str, status_value: str, output: Any | None = None) -> None:
    state = ensure_pipeline_state(project)
    stage_state = dict(state.get(stage) or {})
    stage_state["status"] = status_value
    stage_state["updated_at"] = now_iso()
    if output is not None:
        stage_state["output"] = output
    state[stage] = stage_state
    project.pipeline_state = state
    project.updated_at = utc_now()


def reset_generation_stages(project: Project) -> None:
    state = ensure_pipeline_state(project)
    for stage in PIPELINE_STAGES[2:]:
        state[stage] = {"status": "pending", "output": None, "updated_at": now_iso()}
    project.pipeline_state = state


def serialize_project(project: Project) -> ProjectRead:
    pipeline = {
        stage: PipelineStageRead.model_validate(data)
        for stage, data in ensure_pipeline_state(project).items()
    }
    return ProjectRead(
        id=project.id,
        owner_id=project.owner_id,
        name=project.name,
        description=project.description,
        prompt_text=project.prompt_text,
        status=project.status,
        lifecycle_state=project.lifecycle_state,
        requirement_completeness=project.requirement_completeness,
        pipeline=pipeline,
        current_requirement_session_id=project.current_requirement_session_id,
        current_blueprint_version_id=project.current_blueprint_version_id,
        current_generation_job_id=project.current_generation_job_id,
        current_project_version_id=project.current_project_version_id,
        current_deployment_id=project.current_deployment_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def add_project_message(db: Session, project_id: str, role: str, content: str, agent: str | None = None) -> ProjectMessage:
    message = ProjectMessage(project_id=project_id, role=role, content=content, agent=agent)
    db.add(message)
    db.flush()
    return message


def add_audit_log(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    *,
    user_id: str | None = None,
    project_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            project_id=project_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=details or {},
        )
    )


def add_notification(db: Session, user_id: str, title: str, body: str, project_id: str | None = None) -> None:
    db.add(
        Notification(
            user_id=user_id,
            project_id=project_id,
            title=title,
            body=body,
        )
    )


def get_project_or_404(db: Session, project_id: str, user: User) -> Project:
    query = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None))
    if not user.is_superuser:
        query = query.filter(Project.owner_id == user.id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def get_requirement_session(db: Session, project: Project) -> RequirementSession:
    session = (
        db.query(RequirementSession)
        .filter(RequirementSession.project_id == project.id, RequirementSession.deleted_at.is_(None))
        .first()
    )
    if session:
        return session

    session = RequirementSession(project_id=project.id, status="pending")
    db.add(session)
    db.flush()
    project.current_requirement_session_id = session.id
    return session


def build_conversation_history(db: Session, project_id: str) -> list[dict[str, str]]:
    messages = (
        db.query(ProjectMessage)
        .filter(ProjectMessage.project_id == project_id, ProjectMessage.deleted_at.is_(None))
        .order_by(ProjectMessage.created_at.asc())
        .all()
    )
    return [{"role": item.role, "content": item.content} for item in messages]


def build_chat_transcript(db: Session, project_id: str) -> str:
    history = build_conversation_history(db, project_id)
    if not history:
        return ""

    labels = {"user": "User", "assistant": "Assistant", "system": "System"}
    lines = []
    for item in history:
        role = labels.get(item.get("role", "").lower(), item.get("role", "Message").title() or "Message")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"### {role}\n{content}")
    return "\n\n".join(lines)


def _analysis_seed(project: Project, message: str) -> str:
    prompt = (project.prompt_text or "").strip()
    text = (message or "").strip()
    if not prompt:
        return text
    if not text or text == prompt:
        return prompt
    return f"{prompt}\n\nAdditional context:\n{text}"


def _next_blueprint_version_number(db: Session, project_id: str) -> int:
    current = db.query(func.max(BlueprintVersion.version_number)).filter(BlueprintVersion.project_id == project_id).scalar()
    return int(current or 0) + 1


def _next_project_version_label(db: Session, project_id: str) -> str:
    count = db.query(func.count(ProjectVersion.id)).filter(ProjectVersion.project_id == project_id).scalar() or 0
    return f"v{int(count) + 1}"


def _validate_analysis(payload: Any) -> dict[str, Any]:
    return RequirementAnalysisPayload.model_validate(payload).model_dump()


def _validate_gathering(payload: Any) -> GatheringPayload:
    return GatheringPayload.model_validate(payload)


def _validate_requirements(payload: Any) -> dict[str, Any]:
    return RequirementsDocumentPayload.model_validate(payload).model_dump()


def _validate_architecture(payload: Any) -> dict[str, Any]:
    return ArchitecturePayload.model_validate(payload).model_dump()


def _validate_master_json(payload: Any) -> dict[str, Any]:
    return MasterJsonPayload.model_validate(payload).model_dump()


def _validate_bundle(payload: Any) -> dict[str, Any]:
    return GeneratedBundlePayload.model_validate(payload).model_dump()


def _validate_review(payload: Any) -> dict[str, Any]:
    return CodeReviewPayload.model_validate(payload).model_dump()


def create_project(db: Session, owner: User, payload: ProjectCreateRequest) -> Project:
    project = Project(
        owner_id=owner.id,
        name=payload.name,
        description=payload.description,
        prompt_text=payload.prompt,
        status="INIT",
        lifecycle_state="draft",
        pipeline_state=default_pipeline_state(),
    )
    db.add(project)
    db.flush()

    db.add(
        Prompt(
            project_id=project.id,
            created_by_id=owner.id,
            content=payload.prompt,
            kind="initial",
        )
    )

    requirement_session = RequirementSession(
        project_id=project.id,
        status="pending",
        completeness_score=0.0,
    )
    db.add(requirement_session)
    db.flush()

    project.current_requirement_session_id = requirement_session.id
    add_audit_log(db, "project.created", "project", project.id, user_id=owner.id, project_id=project.id)
    db.commit()
    db.refresh(project)
    return project


async def _queue_generation(
    db: Session,
    project: Project,
    user: User,
    background_tasks: BackgroundTasks,
    *,
    change_request: str | None = None,
) -> ChatResponse:
    requirement_session = get_requirement_session(db, project)
    if not requirement_session.normalized_requirements:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirements are not complete yet")

    reset_generation_stages(project)
    job = GenerationJob(
        project_id=project.id,
        requested_by_id=user.id,
        blueprint_version_id=project.current_blueprint_version_id,
        job_type="partial_regeneration" if change_request else "full_generation",
        status="queued",
        current_stage="architecture",
        change_request=change_request,
        job_spec_json={"change_request": change_request},
    )
    db.add(job)
    db.flush()

    project.current_generation_job_id = job.id
    project.status = "ARCHITECTING"
    project.lifecycle_state = "generation_queued"

    msg = (
        "Processing your modification request. Regenerating the affected ERP blueprint and artifacts..."
        if change_request
        else "Requirements gathered successfully! Now generating your ERP blueprint and code artifacts."
    )
    add_project_message(db, project.id, "assistant", msg, agent="orchestrator")
    add_audit_log(
        db,
        "generation.queued",
        "generation_job",
        job.id,
        user_id=user.id,
        project_id=project.id,
        details={"change_request": change_request},
    )
    add_notification(db, user.id, "Generation queued", msg, project.id)
    db.commit()

    background_tasks.add_task(run_generation_pipeline, project.id, job.id, change_request)
    return ChatResponse(
        response=msg,
        status=project.status,
        auto_advance=True,
        requirements=requirement_session.normalized_requirements,
    )


async def handle_project_chat(
    db: Session,
    project: Project,
    user: User,
    message: str,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    add_project_message(db, project.id, "user", message)

    requirement_session = get_requirement_session(db, project)
    conversation_history = build_conversation_history(db, project.id)

    if project.status == "INIT":
        seed = _analysis_seed(project, message)
        update_stage(project, "requirement_analysis", "running")
        project.status = "ANALYZING"
        db.commit()

        analysis = _validate_analysis(await requirement_analyzer(seed))
        requirement_session.analysis_json = analysis
        requirement_session.summary = analysis.get("summary", "")
        requirement_session.completeness_score = 0.25
        project.requirement_completeness = 0.25
        update_stage(project, "requirement_analysis", "complete", analysis)
        update_stage(project, "requirement_gathering", "running")

        gathered = _validate_gathering(await requirement_gatherer(analysis, conversation_history))
        if gathered.complete and gathered.requirements:
            normalized = _validate_requirements(gathered.requirements.model_dump())
            requirement_session.normalized_requirements = normalized
            requirement_session.status = "completed"
            requirement_session.completeness_score = 1.0
            project.requirement_completeness = 1.0
            update_stage(project, "requirement_gathering", "complete", normalized)
            db.commit()
            return await _queue_generation(db, project, user, background_tasks)

        question = gathered.question or "What module or workflow should the ERP prioritize first?"
        summary_message = (
            f"I've analyzed your request and identified the following:\n\n"
            f"**Business Type:** {analysis.get('business_type', 'N/A')}\n"
            f"**Industry:** {analysis.get('industry', 'N/A')}\n"
            f"**Scale:** {analysis.get('scale', 'N/A')}\n"
            f"**Suggested Modules:** {', '.join(analysis.get('suggested_modules', []))}\n\n"
            f"Let me ask a few questions to refine the requirements.\n\n"
            f"{question}"
        )
        db.add(
            ClarificationQuestion(
                requirement_session_id=requirement_session.id,
                project_id=project.id,
                question_text=question,
                module_name=gathered.current_module,
                status="pending",
            )
        )
        requirement_session.status = "collecting"
        requirement_session.current_module = gathered.current_module
        requirement_session.summary = gathered.progress_summary or summary_message
        requirement_session.completeness_score = 0.5
        project.requirement_completeness = 0.5
        project.status = "GATHERING"
        add_project_message(db, project.id, "assistant", summary_message, agent="requirement_gatherer")
        db.commit()
        return ChatResponse(
            response=summary_message,
            status=project.status,
            analysis=analysis,
            current_module=gathered.current_module,
            progress=gathered.progress_summary,
        )

    if project.status == "GATHERING":
        latest_question = (
            db.query(ClarificationQuestion)
            .filter(
                ClarificationQuestion.project_id == project.id,
                ClarificationQuestion.status == "pending",
                ClarificationQuestion.deleted_at.is_(None),
            )
            .order_by(ClarificationQuestion.created_at.desc())
            .first()
        )
        if latest_question:
            latest_question.status = "answered"
            latest_question.answered_at = utc_now()

        db.add(
            ClarificationAnswer(
                requirement_session_id=requirement_session.id,
                question_id=latest_question.id if latest_question else None,
                project_id=project.id,
                answered_by_id=user.id,
                answer_text=message,
                source="user",
            )
        )

        gathered = _validate_gathering(await requirement_gatherer(requirement_session.analysis_json, conversation_history))
        if gathered.complete and gathered.requirements:
            normalized = _validate_requirements(gathered.requirements.model_dump())
            requirement_session.normalized_requirements = normalized
            requirement_session.status = "completed"
            requirement_session.completeness_score = 1.0
            project.requirement_completeness = 1.0
            update_stage(project, "requirement_gathering", "complete", normalized)
            db.commit()
            return await _queue_generation(db, project, user, background_tasks)

        question = gathered.question or "What else should the system support operationally?"
        db.add(
            ClarificationQuestion(
                requirement_session_id=requirement_session.id,
                project_id=project.id,
                question_text=question,
                module_name=gathered.current_module,
                status="pending",
            )
        )
        requirement_session.current_module = gathered.current_module
        requirement_session.summary = gathered.progress_summary or question
        requirement_session.completeness_score = min(requirement_session.completeness_score + 0.15, 0.9)
        project.requirement_completeness = requirement_session.completeness_score
        add_project_message(db, project.id, "assistant", question, agent="requirement_gatherer")
        db.commit()
        return ChatResponse(
            response=question,
            status=project.status,
            current_module=gathered.current_module,
            progress=gathered.progress_summary,
        )

    if project.status in {"ARCHITECTING", "TRANSFORMING", "GENERATING_FRONTEND", "GENERATING_BACKEND", "REVIEWING"}:
        db.commit()
        return ChatResponse(
            response="The project is still processing. Please wait for the current job to finish.",
            status=project.status,
        )

    db.commit()
    return await _queue_generation(db, project, user, background_tasks, change_request=message)


async def run_generation_pipeline(project_id: str, job_id: str, change_request: str | None = None) -> None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not project or not job:
            return

        requirement_session = get_requirement_session(db, project)
        requirements = _validate_requirements(requirement_session.normalized_requirements)

        job.status = "running"
        job.started_at = utc_now()
        project.status = "ARCHITECTING"
        project.lifecycle_state = "generation_running"
        update_stage(project, "architecture", "running")
        db.commit()

        architecture = _validate_architecture(await erp_architect(requirements, change_request))
        update_stage(project, "architecture", "complete", architecture)
        blueprint = BlueprintVersion(
            project_id=project.id,
            version_number=_next_blueprint_version_number(db, project.id),
            status="active",
            summary=architecture.get("description"),
            blueprint_json=architecture,
            source_requirements_json=requirements,
            created_by_id=job.requested_by_id,
        )
        db.add(blueprint)
        db.flush()
        project.current_blueprint_version_id = blueprint.id
        job.blueprint_version_id = blueprint.id
        add_project_message(db, project.id, "assistant", "ERP architecture generated successfully.", agent="erp_architect")
        db.commit()

        project.status = "TRANSFORMING"
        job.current_stage = "json_transform"
        update_stage(project, "json_transform", "running")
        db.commit()

        master_json = _validate_master_json(await json_transformer(architecture))
        markdown_spec = await markdown_blueprint_generator(
            project.name,
            build_chat_transcript(db, project.id),
            requirements,
            architecture,
            master_json,
        )
        documentation = dict(master_json.get("documentation") or {})
        documentation["erp_build_markdown"] = markdown_spec
        documentation["source_summary"] = requirement_session.summary or architecture.get("description", "")
        documentation["chat_transcript_markdown"] = build_chat_transcript(db, project.id)
        master_json["documentation"] = documentation
        update_stage(project, "json_transform", "complete", master_json)
        add_project_message(db, project.id, "assistant", "Blueprint normalized into the master ERP JSON contract.", agent="json_transformer")
        db.commit()

        project.status = "GENERATING_FRONTEND"
        job.current_stage = "frontend_generation"
        update_stage(project, "frontend_generation", "running")
        db.commit()

        frontend_bundle = _validate_bundle(await frontend_generator(master_json, markdown_spec))
        update_stage(project, "frontend_generation", "complete", frontend_bundle)
        db.add(
            GeneratedArtifact(
                generation_job_id=job.id,
                project_id=project.id,
                artifact_type="spec",
                file_path="spec/erp-build-guide.md",
                language="markdown",
                content_text=markdown_spec,
                metadata_json={"source": "markdown_blueprint_generator"},
            )
        )
        db.add(
            GeneratedArtifact(
                generation_job_id=job.id,
                project_id=project.id,
                artifact_type="spec",
                file_path="spec/erp-blueprint.json",
                language="json",
                content_text=json.dumps(master_json, indent=2),
                metadata_json={"source": "json_transformer"},
            )
        )
        for generated_file in frontend_bundle.get("files", []):
            db.add(
                GeneratedArtifact(
                    generation_job_id=job.id,
                    project_id=project.id,
                    artifact_type="frontend",
                    file_path=generated_file["path"],
                    language=generated_file.get("language"),
                    content_text=generated_file["content"],
                    metadata_json={"dependencies": frontend_bundle.get("dependencies", {})},
                )
            )
        add_project_message(db, project.id, "assistant", "Frontend artifacts generated.", agent="frontend_generator")
        db.commit()

        project.status = "GENERATING_BACKEND"
        job.current_stage = "backend_generation"
        update_stage(project, "backend_generation", "running")
        db.commit()

        backend_bundle = _validate_bundle(await backend_generator(master_json, markdown_spec))
        update_stage(project, "backend_generation", "complete", backend_bundle)
        for generated_file in backend_bundle.get("files", []):
            db.add(
                GeneratedArtifact(
                    generation_job_id=job.id,
                    project_id=project.id,
                    artifact_type="backend",
                    file_path=generated_file["path"],
                    language=generated_file.get("language"),
                    content_text=generated_file["content"],
                    metadata_json={"dependencies": backend_bundle.get("dependencies", {})},
                )
            )
        add_project_message(db, project.id, "assistant", "Backend artifacts generated.", agent="backend_generator")
        db.commit()

        project.status = "REVIEWING"
        job.current_stage = "code_review"
        update_stage(project, "code_review", "running")
        db.commit()

        review = _validate_review(await code_reviewer(frontend_bundle, backend_bundle))
        update_stage(project, "code_review", "complete", review)

        project_version = ProjectVersion(
            project_id=project.id,
            blueprint_version_id=blueprint.id,
            generation_job_id=job.id,
            version_label=_next_project_version_label(db, project.id),
            changelog=change_request or "Initial generated version",
            snapshot_json={
                "architecture": architecture,
                "master_json": master_json,
                "build_markdown": markdown_spec,
                "review": review,
            },
        )
        db.add(project_version)
        db.flush()

        project.current_project_version_id = project_version.id
        project.status = "COMPLETE"
        project.lifecycle_state = "generated"
        job.status = "complete"
        job.current_stage = "complete"
        job.completed_at = utc_now()
        job.result_summary_json = {
            "blueprint_version_id": blueprint.id,
            "project_version_id": project_version.id,
            "markdown_spec_available": bool(markdown_spec),
            "frontend_file_count": len(frontend_bundle.get("files", [])),
            "backend_file_count": len(backend_bundle.get("files", [])),
            "review_score": review.get("overall_score"),
        }
        add_project_message(
            db,
            project.id,
            "assistant",
            (
                f"Your ERP system is ready. Blueprint version {blueprint.version_number} and project version "
                f"{project_version.version_label} were generated successfully."
            ),
            agent="orchestrator",
        )
        add_notification(
            db,
            job.requested_by_id or project.owner_id,
            "Generation completed",
            f"Project {project.name} finished code generation successfully.",
            project.id,
        )
        add_audit_log(
            db,
            "generation.completed",
            "generation_job",
            job.id,
            user_id=job.requested_by_id,
            project_id=project.id,
            details=job.result_summary_json,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        project = db.query(Project).filter(Project.id == project_id).first()
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if project and job:
            project.status = "ERROR"
            project.lifecycle_state = "error"
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = utc_now()
            update_stage(project, job.current_stage or "architecture", "failed", {"error": str(exc)})
            add_project_message(
                db,
                project.id,
                "assistant",
                "Generation failed. Please review the job logs and retry with a refined change request.",
                agent="system",
            )
            add_notification(
                db,
                job.requested_by_id or project.owner_id,
                "Generation failed",
                f"Project {project.name} encountered an error during generation.",
                project.id,
            )
            add_audit_log(
                db,
                "generation.failed",
                "generation_job",
                job.id,
                user_id=job.requested_by_id,
                project_id=project.id,
                details={"error": str(exc)},
            )
            db.commit()
    finally:
        db.close()


def list_project_messages(db: Session, project: Project) -> list[MessageRead]:
    messages = (
        db.query(ProjectMessage)
        .filter(ProjectMessage.project_id == project.id, ProjectMessage.deleted_at.is_(None))
        .order_by(ProjectMessage.created_at.asc())
        .all()
    )
    return [MessageRead.model_validate(message) for message in messages]


def list_project_prompts(db: Session, project: Project) -> list[PromptRead]:
    prompts = (
        db.query(Prompt)
        .filter(Prompt.project_id == project.id, Prompt.deleted_at.is_(None))
        .order_by(Prompt.created_at.asc())
        .all()
    )
    return [PromptRead.model_validate(prompt) for prompt in prompts]


def get_project_requirement_session(db: Session, project: Project) -> RequirementSessionRead:
    session = get_requirement_session(db, project)
    return RequirementSessionRead.model_validate(session)


def list_project_generation_jobs(db: Session, project: Project) -> list[GenerationJobRead]:
    jobs = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project.id, GenerationJob.deleted_at.is_(None))
        .order_by(GenerationJob.created_at.desc())
        .all()
    )
    return [GenerationJobRead.model_validate(job) for job in jobs]


def list_project_blueprints(db: Session, project: Project) -> list[BlueprintVersionRead]:
    blueprints = (
        db.query(BlueprintVersion)
        .filter(BlueprintVersion.project_id == project.id, BlueprintVersion.deleted_at.is_(None))
        .order_by(BlueprintVersion.version_number.desc())
        .all()
    )
    return [BlueprintVersionRead.model_validate(item) for item in blueprints]


def list_project_versions(db: Session, project: Project) -> list[ProjectVersionRead]:
    versions = (
        db.query(ProjectVersion)
        .filter(ProjectVersion.project_id == project.id, ProjectVersion.deleted_at.is_(None))
        .order_by(ProjectVersion.created_at.desc())
        .all()
    )
    return [ProjectVersionRead.model_validate(item) for item in versions]


def list_projects(db: Session, user: User) -> list[Project]:
    query = db.query(Project).filter(Project.deleted_at.is_(None)).order_by(Project.created_at.desc())
    if not user.is_superuser:
        query = query.filter(Project.owner_id == user.id)
    return query.all()


def get_pipeline_stage(project: Project, stage: str) -> PipelineStageRead:
    if stage not in PIPELINE_STAGES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid stage")
    state = ensure_pipeline_state(project)
    return PipelineStageRead.model_validate(state.get(stage, {}))


async def ensure_markdown_documentation(db: Session, project: Project) -> dict[str, Any] | None:
    state = ensure_pipeline_state(project)
    json_stage = dict(state.get("json_transform") or {})
    if json_stage.get("status") != "complete":
        return json_stage.get("output")

    output = dict(json_stage.get("output") or {})
    if not output:
        return output

    documentation = dict(output.get("documentation") or {})
    existing_markdown = documentation.get("erp_build_markdown")
    if existing_markdown and is_valid_markdown_blueprint(existing_markdown):
        return output

    requirement_session = get_requirement_session(db, project)
    architecture_output = dict((state.get("architecture") or {}).get("output") or {})
    conversation_transcript = build_chat_transcript(db, project.id)
    markdown_spec = await markdown_blueprint_generator(
        project.name,
        conversation_transcript,
        requirement_session.normalized_requirements or {},
        architecture_output,
        output,
    )

    documentation["erp_build_markdown"] = markdown_spec
    documentation["source_summary"] = requirement_session.summary or architecture_output.get("description", "")
    documentation["chat_transcript_markdown"] = conversation_transcript
    output["documentation"] = documentation

    json_stage["output"] = output
    json_stage["updated_at"] = now_iso()
    state["json_transform"] = json_stage
    project.pipeline_state = state
    project.updated_at = utc_now()

    if project.current_project_version_id:
        project_version = db.query(ProjectVersion).filter(ProjectVersion.id == project.current_project_version_id).first()
        if project_version:
            snapshot = dict(project_version.snapshot_json or {})
            snapshot["master_json"] = output
            snapshot["build_markdown"] = markdown_spec
            project_version.snapshot_json = snapshot

    db.commit()
    db.refresh(project)
    return output


def soft_delete_project(db: Session, project: Project, user: User) -> None:
    deleted_at = utc_now()
    project.deleted_at = deleted_at
    project.lifecycle_state = "deleted"
    project.status = "DELETED"

    dependent_models = [
        ProjectMessage,
        Prompt,
        RequirementSession,
        ClarificationQuestion,
        ClarificationAnswer,
        BlueprintVersion,
        GenerationJob,
        GeneratedArtifact,
        ProjectVersion,
        Deployment,
        AutomationWorkflow,
    ]

    for model in dependent_models:
        project_column = getattr(model, "project_id", None)
        if project_column is None:
            continue
        (
            db.query(model)
            .filter(project_column == project.id, model.deleted_at.is_(None))
            .update({"deleted_at": deleted_at}, synchronize_session=False)
        )

    add_audit_log(db, "project.deleted", "project", project.id, user_id=user.id, project_id=project.id)
    db.commit()


def create_deployment(db: Session, user: User, payload: DeploymentCreateRequest) -> DeploymentRead:
    project = get_project_or_404(db, payload.project_id, user)
    deployment = Deployment(
        project_id=project.id,
        project_version_id=project.current_project_version_id,
        requested_by_id=user.id,
        provider=payload.provider,
        environment_name=payload.environment_name,
        status="queued",
        config_json=payload.config,
        status_message="Deployment request queued for execution.",
        started_at=utc_now(),
    )
    db.add(deployment)
    db.flush()

    project.current_deployment_id = deployment.id
    project.lifecycle_state = "deployment_queued"
    db.add(
        DeploymentLog(
            deployment_id=deployment.id,
            level="info",
            message=f"Deployment queued for {payload.environment_name} via {payload.provider}.",
        )
    )
    add_audit_log(
        db,
        "deployment.created",
        "deployment",
        deployment.id,
        user_id=user.id,
        project_id=project.id,
        details={"provider": payload.provider, "environment_name": payload.environment_name},
    )
    add_notification(
        db,
        user.id,
        "Deployment queued",
        f"Deployment for project {project.name} has been queued.",
        project.id,
    )
    db.commit()
    db.refresh(deployment)
    return DeploymentRead.model_validate(deployment)


def list_deployments(db: Session, user: User, project_id: str | None = None) -> list[DeploymentRead]:
    query = db.query(Deployment).filter(Deployment.deleted_at.is_(None)).order_by(Deployment.created_at.desc())

    if project_id:
        project = get_project_or_404(db, project_id, user)
        query = query.filter(Deployment.project_id == project.id)
    elif not user.is_superuser:
        owned_project_ids = db.query(Project.id).filter(Project.owner_id == user.id, Project.deleted_at.is_(None))
        query = query.filter(Deployment.project_id.in_(owned_project_ids))

    return [DeploymentRead.model_validate(item) for item in query.all()]


def list_deployment_logs(db: Session, user: User, deployment_id: str) -> list[DeploymentLogRead]:
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id, Deployment.deleted_at.is_(None)).first()
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    if not user.is_superuser:
        project = get_project_or_404(db, deployment.project_id, user)
        if project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    logs = (
        db.query(DeploymentLog)
        .filter(DeploymentLog.deployment_id == deployment.id, DeploymentLog.deleted_at.is_(None))
        .order_by(DeploymentLog.created_at.asc())
        .all()
    )
    return [DeploymentLogRead.model_validate(item) for item in logs]


def upsert_api_configuration(
    db: Session,
    user: User,
    payload: APIConfigurationUpsertRequest,
) -> APIConfigurationRead:
    config = (
        db.query(APIConfiguration)
        .filter(
            APIConfiguration.user_id == user.id,
            APIConfiguration.provider == payload.provider,
            APIConfiguration.deleted_at.is_(None),
        )
        .first()
    )
    if config is None:
        config = APIConfiguration(
            user_id=user.id,
            provider=payload.provider,
            display_name=payload.display_name,
            config_json=payload.config,
            status=payload.status,
        )
        db.add(config)
    else:
        config.display_name = payload.display_name
        config.config_json = payload.config
        config.status = payload.status

    add_audit_log(
        db,
        "api_configuration.upserted",
        "api_configuration",
        config.id if config.id else None,
        user_id=user.id,
        details={"provider": payload.provider},
    )
    db.commit()
    db.refresh(config)
    return APIConfigurationRead.model_validate(config)


def list_api_configurations(db: Session, user: User) -> list[APIConfigurationRead]:
    configs = (
        db.query(APIConfiguration)
        .filter(APIConfiguration.user_id == user.id, APIConfiguration.deleted_at.is_(None))
        .order_by(APIConfiguration.updated_at.desc())
        .all()
    )
    return [APIConfigurationRead.model_validate(item) for item in configs]


def create_automation_workflow(
    db: Session,
    user: User,
    payload: AutomationWorkflowCreateRequest,
) -> AutomationWorkflowRead:
    project = get_project_or_404(db, payload.project_id, user)
    workflow = AutomationWorkflow(
        project_id=project.id,
        name=payload.name,
        trigger_event=payload.trigger_event,
        workflow_json=payload.workflow_json,
        status=payload.status,
    )
    db.add(workflow)
    db.flush()
    add_audit_log(
        db,
        "automation.created",
        "automation_workflow",
        workflow.id,
        user_id=user.id,
        project_id=project.id,
        details={"trigger_event": payload.trigger_event},
    )
    add_notification(
        db,
        user.id,
        "Automation saved",
        f"Workflow {payload.name} was saved for project {project.name}.",
        project.id,
    )
    db.commit()
    db.refresh(workflow)
    return AutomationWorkflowRead.model_validate(workflow)


def list_automation_workflows(
    db: Session,
    user: User,
    project_id: str | None = None,
) -> list[AutomationWorkflowRead]:
    query = (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.deleted_at.is_(None))
        .order_by(AutomationWorkflow.updated_at.desc())
    )

    if project_id:
        project = get_project_or_404(db, project_id, user)
        query = query.filter(AutomationWorkflow.project_id == project.id)
    elif not user.is_superuser:
        owned_project_ids = db.query(Project.id).filter(Project.owner_id == user.id, Project.deleted_at.is_(None))
        query = query.filter(AutomationWorkflow.project_id.in_(owned_project_ids))

    return [AutomationWorkflowRead.model_validate(item) for item in query.all()]


def list_notifications(db: Session, user: User) -> list[NotificationRead]:
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.deleted_at.is_(None))
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [NotificationRead.model_validate(item) for item in notifications]


def mark_notification_read(db: Session, user: User, notification_id: str) -> NotificationRead:
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.deleted_at.is_(None),
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.status = "read"
    notification.read_at = utc_now()
    db.commit()
    db.refresh(notification)
    return NotificationRead.model_validate(notification)
