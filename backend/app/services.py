from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from inspect import signature
from inspect import isawaitable
from typing import Any

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from agents import (
    analysis_model_label,
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
from .local_runner import start_project_locally
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
from .template_loader import (
    attach_erp_ui_template_metadata,
    list_erp_ui_templates,
    load_erp_ui_template,
    resolve_erp_ui_template_id,
)
from .template_frontend_bundle import build_template_driven_frontend_bundle


logger = logging.getLogger(__name__)

PIPELINE_STAGES = [
    "requirement_analysis",
    "requirement_gathering",
    "architecture",
    "json_transform",
    "frontend_generation",
    "backend_generation",
    "code_review",
]


class InProcessBackgroundTasks:
    def __init__(self) -> None:
        self.tasks: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    def add_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self.tasks.append((func, args, kwargs))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat()


def default_pipeline_state() -> dict[str, dict[str, Any]]:
    return {
        stage: {"status": "pending", "output": None, "updated_at": None}
        for stage in PIPELINE_STAGES
    }


def get_project_template_id(project: Project | None) -> str:
    metadata = dict((getattr(project, "metadata_json", {}) if project else {}) or {})
    return resolve_erp_ui_template_id(metadata.get("selected_template_id"))


def get_project_template_reference(project: Project | None, *, include_source_contents: bool = True) -> dict[str, Any]:
    template_id = get_project_template_id(project)
    if include_source_contents:
        return load_erp_ui_template(template_id)
    for template in list_erp_ui_templates():
        if template.get("id") == template_id:
            return template
    templates = list_erp_ui_templates()
    return templates[0] if templates else {}


def list_available_project_templates() -> list[dict[str, Any]]:
    templates = []
    for template in list_erp_ui_templates():
        templates.append(
            {
                "id": template.get("id"),
                "name": template.get("name"),
                "display_name": template.get("display_name"),
                "reference_project": template.get("reference_project"),
                "summary": template.get("summary") or "",
                "relative_directory": template.get("relative_directory"),
                "status": template.get("status", "unknown"),
                "source_files": [
                    {
                        "relative_path": item.get("relative_path"),
                        "language": item.get("language", "text"),
                        "role": item.get("role"),
                    }
                    for item in (template.get("source_files") or [])
                ],
            }
        )
    return templates


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


def reset_generation_stages(project: Project, *, preserve_existing_outputs: bool = False) -> None:
    state = ensure_pipeline_state(project)
    for stage in PIPELINE_STAGES[2:]:
        current = dict(state.get(stage) or {})
        if preserve_existing_outputs and current.get("output") is not None:
            state[stage] = {
                "status": "complete",
                "output": current.get("output"),
                "updated_at": now_iso(),
            }
        else:
            state[stage] = {"status": "pending", "output": None, "updated_at": now_iso()}
    project.pipeline_state = state


def mark_stage_failure(project: Project, stage: str, error_message: str) -> None:
    error_payload = {"error": error_message}
    update_stage(project, stage, "failed", error_payload)
    if stage not in {"frontend_generation", "backend_generation"}:
        return

    paired_stage = "backend_generation" if stage == "frontend_generation" else "frontend_generation"
    paired_state = dict(ensure_pipeline_state(project).get(paired_stage) or {})
    if paired_state.get("status") == "running":
        update_stage(project, paired_stage, "failed", error_payload)


def _should_preserve_last_working_build(project: Project, change_request: str | None) -> bool:
    return bool(change_request and project.current_project_version_id)


def _apply_generation_failure_state(
    project: Project,
    job: GenerationJob,
    error_message: str,
    *,
    change_request: str | None = None,
) -> dict[str, Any]:
    preserved_last_build = _should_preserve_last_working_build(project, change_request)
    if preserved_last_build:
        project.status = "COMPLETE"
        project.lifecycle_state = "generated"
    else:
        project.status = "ERROR"
        project.lifecycle_state = "error"

    job.status = "failed"
    job.error_message = error_message
    job.completed_at = utc_now()
    mark_stage_failure(project, job.current_stage or "architecture", error_message)

    return {
        "preserved_last_build": preserved_last_build,
        "message": (
            "The requested changes could not be applied cleanly. The last working ERP version is still available; "
            "review the job logs and retry with a refined change request."
            if preserved_last_build
            else "Generation failed. Please review the job logs and retry with a refined change request."
        ),
        "notification_title": "Revision failed, previous build preserved" if preserved_last_build else "Generation failed",
        "notification_body": (
            f"Project {project.name} kept the last working ERP version after a failed revision attempt."
            if preserved_last_build
            else f"Project {project.name} encountered an error during generation."
        ),
        "audit_details": {
            "error": error_message,
            "preserved_last_build": preserved_last_build,
        },
    }


def recover_interrupted_generation_jobs(db: Session) -> int:
    interrupted_jobs = (
        db.query(GenerationJob)
        .filter(
            GenerationJob.deleted_at.is_(None),
            GenerationJob.status.in_(["queued", "running"]),
        )
        .order_by(GenerationJob.created_at.asc())
        .all()
    )

    recovered_count = 0
    for job in interrupted_jobs:
        project = (
            db.query(Project)
            .filter(Project.id == job.project_id, Project.deleted_at.is_(None))
            .first()
        )
        if not project:
            continue

        failure_state = _apply_generation_failure_state(
            project,
            job,
            "Generation was interrupted when the builder backend restarted.",
            change_request=job.change_request,
        )
        add_project_message(
            db,
            project.id,
            "assistant",
            (
                "The previous generation run was interrupted when the builder backend restarted. "
                "The last working ERP version is still available."
                if failure_state["preserved_last_build"]
                else "The previous generation run was interrupted when the builder backend restarted. Please retry it."
            ),
            agent="system",
        )
        add_audit_log(
            db,
            "generation.recovered_after_restart",
            "generation_job",
            job.id,
            user_id=job.requested_by_id,
            project_id=project.id,
            details={
                **failure_state["audit_details"],
                "reason": "builder_restart",
            },
        )
        recovered_count += 1

    if recovered_count:
        db.commit()
    return recovered_count


def serialize_project(project: Project) -> ProjectRead:
    pipeline = {
        stage: PipelineStageRead.model_validate(data)
        for stage, data in ensure_pipeline_state(project).items()
    }
    template_reference = get_project_template_reference(project, include_source_contents=False)
    return ProjectRead(
        id=project.id,
        owner_id=project.owner_id,
        name=project.name,
        description=project.description,
        prompt_text=project.prompt_text,
        selected_template_id=template_reference.get("id"),
        selected_template_name=template_reference.get("display_name") or template_reference.get("name"),
        selected_template_reference=template_reference.get("reference_project"),
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


async def _run_in_process_background_tasks(background_tasks: InProcessBackgroundTasks) -> None:
    for func, args, kwargs in background_tasks.tasks:
        result = func(*args, **kwargs)
        if isawaitable(result):
            await result


_UI_THEME_FAMILIES: dict[str, dict[str, str]] = {
    "green": {
        "primary_color": "#16A34A",
        "accent_color": "#22C55E",
        "accent_cyan": "#14B8A6",
        "success_color": "#22C55E",
    },
    "teal": {
        "primary_color": "#0F766E",
        "accent_color": "#14B8A6",
        "accent_cyan": "#22D3EE",
        "success_color": "#14B8A6",
    },
    "blue": {
        "primary_color": "#2563EB",
        "accent_color": "#3B82F6",
        "accent_cyan": "#06B6D4",
        "success_color": "#22C55E",
    },
    "indigo": {
        "primary_color": "#4338CA",
        "accent_color": "#6366F1",
        "accent_cyan": "#38BDF8",
        "success_color": "#22C55E",
    },
    "purple": {
        "primary_color": "#7C3AED",
        "accent_color": "#A855F7",
        "accent_cyan": "#22D3EE",
        "success_color": "#22C55E",
    },
    "orange": {
        "primary_color": "#EA580C",
        "accent_color": "#F97316",
        "accent_cyan": "#F59E0B",
        "success_color": "#22C55E",
    },
    "red": {
        "primary_color": "#DC2626",
        "accent_color": "#EF4444",
        "accent_cyan": "#FB7185",
        "success_color": "#22C55E",
    },
    "slate": {
        "primary_color": "#334155",
        "accent_color": "#475569",
        "accent_cyan": "#64748B",
        "success_color": "#22C55E",
    },
}

_UI_THEME_KEYWORDS = [
    ("emerald", "green"),
    ("lime", "green"),
    ("forest", "green"),
    ("green", "green"),
    ("teal", "teal"),
    ("cyan", "teal"),
    ("turquoise", "teal"),
    ("navy", "blue"),
    ("blue", "blue"),
    ("indigo", "indigo"),
    ("violet", "purple"),
    ("purple", "purple"),
    ("orange", "orange"),
    ("amber", "orange"),
    ("yellow", "orange"),
    ("red", "red"),
    ("rose", "red"),
    ("crimson", "red"),
    ("slate", "slate"),
    ("gray", "slate"),
    ("grey", "slate"),
    ("charcoal", "slate"),
]

_UI_THEME_INTENT_KEYWORDS = [
    "theme",
    "color",
    "colors",
    "colour",
    "colours",
    "palette",
    "scheme",
    "branding",
    "brand",
    "ui",
    "ux",
    "style",
    "look",
    "frontend",
    "layout",
    "navigation",
    "nav",
    "sidebar",
    "side bar",
    "topbar",
    "top bar",
    "header bar",
    "dashboard",
    "screen",
    "button",
    "card",
]

_MONOCHROME_THEME_HINTS = [
    "single color",
    "single colours",
    "single colour",
    "single colors",
    "one color",
    "one colour",
    "one colours",
    "one colors",
    "monochrome",
    "no other color",
    "no other colours",
    "no other colour",
    "no other colors",
]

_UI_ONLY_REVISION_BLOCKERS = [
    "backend",
    "api",
    "database",
    "db ",
    "schema",
    "model",
    "route",
    "endpoint",
    "auth",
    "login",
    "rbac",
    "permission",
    "workflow",
    "approval",
    "button",
    "buttons",
    "click",
    "submit",
    "save",
    "create ",
    "update ",
    "delete ",
    "integration",
    "webhook",
    "automation",
    "n8n",
    "localhost",
    "run locally",
    "server",
]


def _mentions_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _hex_to_rgba(hex_color: str, alpha: float) -> str | None:
    candidate = str(hex_color or "").strip().lstrip("#")
    if len(candidate) == 3:
        candidate = "".join(character * 2 for character in candidate)
    if len(candidate) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", candidate):
        return None

    red = int(candidate[0:2], 16)
    green = int(candidate[2:4], 16)
    blue = int(candidate[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.2f})"


def _merge_nested_dicts(existing: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in updates.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_nested_dicts(current, value)
        else:
            merged[key] = value
    return merged


def _detect_ui_theme_family(change_request: str) -> str | None:
    for keyword, family in _UI_THEME_KEYWORDS:
        if keyword in change_request:
            return family
    return None


def _is_ui_theme_request(change_request: str, theme_family: str | None) -> bool:
    if _mentions_any(change_request, _UI_THEME_INTENT_KEYWORDS):
        return True
    if not theme_family:
        return False
    if re.search(
        r"\b(?:make|turn|change|switch|set|use|apply)\b[^\n\r]{0,24}\b(?:it|ui|ux|erp|frontend|dashboard|app|software|shell|theme)\b",
        change_request,
    ):
        return True
    return bool(re.search(r"\b(?:full|fully|completely|entirely|totally)\b", change_request))


def _is_monochrome_theme_request(change_request: str) -> bool:
    if _mentions_any(change_request, _MONOCHROME_THEME_HINTS):
        return True
    return bool(
        re.search(r"\b(?:full|fully|completely|entirely|totally)\b", change_request)
        and _detect_ui_theme_family(change_request)
    )


def _extract_ui_revision_directives(change_request: str | None) -> dict[str, Any]:
    normalized_request = str(change_request or "").strip()
    if not normalized_request:
        return {}

    lowered = normalized_request.lower()
    theme_family = _detect_ui_theme_family(lowered)
    ui_intent = _is_ui_theme_request(lowered, theme_family)
    if not ui_intent:
        return {}

    directives: dict[str, Any] = {}

    if theme_family:
        palette = dict(_UI_THEME_FAMILIES.get(theme_family) or {})
        if _is_monochrome_theme_request(lowered):
            primary_color = str(palette.get("primary_color") or "")
            accent_color = str(palette.get("accent_color") or primary_color)
            palette["accent_color"] = accent_color
            palette["accent_cyan"] = accent_color
            palette["success_color"] = accent_color
            palette["danger_color"] = primary_color or accent_color
        border_color = _hex_to_rgba(palette.get("primary_color", ""), 0.22)
        if border_color:
            palette.setdefault("border_color", border_color)
        directives["theme"] = palette

    if _mentions_any(lowered, ["dark mode", "dark theme", "dark ui", "dark layout", "dark dashboard"]):
        theme_directives = dict(directives.get("theme") or {})
        theme_directives.update(
            {
                "background_color": "#06110B",
                "surface_color": "#0D1B13",
                "text_color": "#F0FDF4",
                "muted_color": "#9FB7A7",
            }
        )
        if "border_color" not in theme_directives and theme_family:
            border_color = _hex_to_rgba(theme_directives.get("primary_color", ""), 0.24)
            if border_color:
                theme_directives["border_color"] = border_color
        directives["theme"] = theme_directives

    if _mentions_any(lowered, ["light mode", "light theme", "light ui", "light layout", "light dashboard"]):
        theme_directives = dict(directives.get("theme") or {})
        theme_directives.update(
            {
                "background_color": "#F6FCF8",
                "surface_color": "#FFFFFF",
                "text_color": "#052E16",
                "muted_color": "#527067",
            }
        )
        if "border_color" not in theme_directives and theme_family:
            border_color = _hex_to_rgba(theme_directives.get("primary_color", ""), 0.18)
            if border_color:
                theme_directives["border_color"] = border_color
        directives["theme"] = theme_directives

    if _mentions_any(lowered, ["topbar", "top bar", "top navigation", "header nav", "horizontal nav", "top menu"]):
        directives["layout_mode"] = "topbar"
    elif _mentions_any(lowered, ["sidebar", "side bar", "side navigation", "left nav", "left menu"]):
        directives["layout_mode"] = "sidebar"

    if _mentions_any(lowered, ["compact", "dense", "condensed", "tighter", "tight layout"]):
        directives["density"] = "compact"
    elif _mentions_any(lowered, ["comfortable", "spacious", "airy", "relaxed layout"]):
        directives["density"] = "comfortable"

    sidebar_match = re.search(r"(?:sidebar|side\s*bar)[^\d]{0,24}(\d{2,4})\s*px", lowered)
    if not sidebar_match:
        sidebar_match = re.search(r"(\d{2,4})\s*px[^\n\r]{0,24}(?:sidebar|side\s*bar)", lowered)
    if sidebar_match:
        directives["sidebar_width"] = f"{sidebar_match.group(1)}px"

    radius_match = re.search(r"(\d{1,3})\s*px[^\n\r]{0,16}(?:radius|rounded)", lowered)
    if radius_match:
        directives["border_radius"] = f"{radius_match.group(1)}px"

    if directives:
        directives["requested_change"] = normalized_request
    return directives


def _apply_ui_revision_directives(master_json: dict[str, Any], change_request: str | None) -> dict[str, Any]:
    directives = _extract_ui_revision_directives(change_request)
    if not directives:
        return master_json

    documentation = dict(master_json.get("documentation") or {})
    existing_directives = documentation.get("ui_revision_directives")
    if not isinstance(existing_directives, dict):
        existing_directives = {}
    documentation["ui_revision_directives"] = _merge_nested_dicts(existing_directives, directives)
    master_json["documentation"] = documentation
    return master_json


def _has_ui_revision_directives(master_json: dict[str, Any]) -> bool:
    documentation = master_json.get("documentation") or {}
    directives = documentation.get("ui_revision_directives") if isinstance(documentation, dict) else {}
    return isinstance(directives, dict) and bool(directives)


def _is_ui_only_revision_request(change_request: str | None, master_json: dict[str, Any]) -> bool:
    lowered = str(change_request or "").strip().lower()
    if not lowered or not _has_ui_revision_directives(master_json):
        return False
    return not _mentions_any(lowered, _UI_ONLY_REVISION_BLOCKERS)


def _build_frontend_revision_fallback_bundle(
    master_json: dict[str, Any],
    template_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _validate_bundle(build_template_driven_frontend_bundle(master_json, template_reference=template_reference))


def _clone_json_payload(payload: Any) -> Any:
    return json.loads(json.dumps(payload))


def _can_attempt_direct_code_revision(revision_context: dict[str, Any]) -> bool:
    return bool(
        revision_context.get("project_version_id")
        and revision_context.get("architecture")
        and revision_context.get("master_json")
        and revision_context.get("build_markdown")
        and revision_context.get("frontend_bundle")
        and revision_context.get("backend_bundle")
    )


def _persist_spec_artifacts(
    db: Session,
    project: Project,
    job: GenerationJob,
    *,
    markdown_spec: str,
    master_json: dict[str, Any],
) -> None:
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


def _persist_bundle_artifacts(
    db: Session,
    project: Project,
    job: GenerationJob,
    *,
    artifact_type: str,
    bundle: dict[str, Any],
) -> None:
    for generated_file in bundle.get("files", []):
        db.add(
            GeneratedArtifact(
                generation_job_id=job.id,
                project_id=project.id,
                artifact_type=artifact_type,
                file_path=generated_file["path"],
                language=generated_file.get("language"),
                content_text=generated_file["content"],
                metadata_json={"dependencies": bundle.get("dependencies", {})},
            )
        )


async def _finalize_generation_success(
    db: Session,
    project: Project,
    job: GenerationJob,
    *,
    blueprint_id: str | None,
    blueprint_reference: str | int | None = None,
    architecture: dict[str, Any],
    master_json: dict[str, Any],
    markdown_spec: str,
    frontend_bundle: dict[str, Any],
    backend_bundle: dict[str, Any],
    revision_context: dict[str, Any],
    change_request: str | None,
    code_only_revision: bool = False,
) -> None:
    update_stage(project, "frontend_generation", "complete", frontend_bundle)
    update_stage(project, "backend_generation", "complete", backend_bundle)
    _persist_spec_artifacts(db, project, job, markdown_spec=markdown_spec, master_json=master_json)
    _persist_bundle_artifacts(db, project, job, artifact_type="frontend", bundle=frontend_bundle)
    add_project_message(db, project.id, "assistant", "Frontend artifacts generated.", agent="frontend_generator")
    _persist_bundle_artifacts(db, project, job, artifact_type="backend", bundle=backend_bundle)
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
        blueprint_version_id=blueprint_id,
        generation_job_id=job.id,
        version_label=_next_project_version_label(db, project.id),
        changelog=change_request or "Initial generated version",
        snapshot_json={
            "architecture": architecture,
            "master_json": master_json,
            "build_markdown": markdown_spec,
            "review": review,
            "base_project_version_id": revision_context.get("project_version_id"),
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
        "blueprint_version_id": blueprint_id,
        "project_version_id": project_version.id,
        "base_project_version_id": revision_context.get("project_version_id"),
        "markdown_spec_available": bool(markdown_spec),
        "frontend_file_count": len(frontend_bundle.get("files", [])),
        "backend_file_count": len(backend_bundle.get("files", [])),
        "review_score": review.get("overall_score"),
        "code_only_revision": code_only_revision,
    }
    add_project_message(
        db,
        project.id,
        "assistant",
        (
            f"Your changes were applied directly on top of {revision_context.get('version_label', 'the previous version')}. "
            f"Project version {project_version.version_label} is ready."
            if change_request and code_only_revision
            else (
                f"Your changes have been applied on top of {revision_context.get('version_label', 'the previous version')}. "
                f"Blueprint version {blueprint_reference or job.result_summary_json.get('blueprint_version_id')} and project version {project_version.version_label} are ready."
                if change_request
                else (
                    f"Your ERP system is ready. Blueprint version {blueprint_reference or job.result_summary_json.get('blueprint_version_id')} and project version "
                    f"{project_version.version_label} were generated successfully."
                )
            )
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


async def _attempt_direct_code_revision(
    db: Session,
    project: Project,
    job: GenerationJob,
    *,
    revision_context: dict[str, Any],
    template_reference: dict[str, Any],
    change_request: str,
) -> bool:
    if not _can_attempt_direct_code_revision(revision_context):
        return False

    architecture = _validate_architecture(_clone_json_payload(revision_context.get("architecture") or {}))
    master_json = _validate_master_json(_clone_json_payload(revision_context.get("master_json") or {}))
    master_json = attach_erp_ui_template_metadata(master_json, template_reference)
    master_json = _apply_ui_revision_directives(master_json, change_request)
    markdown_spec = str(revision_context.get("build_markdown") or "").strip()
    if not markdown_spec:
        raise RuntimeError("Existing ERP build markdown is unavailable for direct revision.")

    documentation = dict(master_json.get("documentation") or {})
    documentation["erp_build_markdown"] = markdown_spec
    master_json["documentation"] = documentation

    update_stage(project, "architecture", "complete", architecture)
    update_stage(project, "json_transform", "complete", master_json)
    project.status = "GENERATING_FRONTEND"
    job.current_stage = "frontend_generation"
    update_stage(project, "frontend_generation", "running")
    update_stage(project, "backend_generation", "running")
    db.commit()

    frontend_bundle, backend_bundle = await generate_code_bundles(
        master_json,
        markdown_spec,
        existing_frontend_bundle=revision_context.get("frontend_bundle"),
        existing_backend_bundle=revision_context.get("backend_bundle"),
        change_request=change_request,
        template_reference=template_reference,
    )

    await _finalize_generation_success(
        db,
        project,
        job,
        blueprint_id=project.current_blueprint_version_id,
        blueprint_reference=revision_context.get("version_label"),
        architecture=architecture,
        master_json=master_json,
        markdown_spec=markdown_spec,
        frontend_bundle=frontend_bundle,
        backend_bundle=backend_bundle,
        revision_context=revision_context,
        change_request=change_request,
        code_only_revision=True,
    )
    return True


async def generate_code_bundles(
    master_json: dict[str, Any],
    markdown_spec: str,
    *,
    existing_frontend_bundle: dict[str, Any] | None = None,
    existing_backend_bundle: dict[str, Any] | None = None,
    change_request: str | None = None,
    template_reference: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        change_request
        and existing_frontend_bundle is not None
        and existing_backend_bundle is not None
        and _is_ui_only_revision_request(change_request, master_json)
    ):
        frontend_bundle = _build_frontend_revision_fallback_bundle(master_json, template_reference)
        frontend_bundle = _merge_generated_bundle(existing_frontend_bundle, frontend_bundle)
        backend_bundle = _validate_bundle(_clone_json_payload(existing_backend_bundle))
        return frontend_bundle, backend_bundle

    frontend_revision_fallback_allowed = (
        bool(change_request) and existing_frontend_bundle is not None and _has_ui_revision_directives(master_json)
    )
    frontend_result, backend_result = await asyncio.gather(
        _generate_candidate_code_bundle(
            frontend_generator,
            "frontend",
            master_json,
            markdown_spec,
            existing_bundle=existing_frontend_bundle,
            change_request=change_request,
            template_reference=template_reference,
        ),
        _generate_candidate_code_bundle(
            backend_generator,
            "backend",
            master_json,
            markdown_spec,
            existing_bundle=existing_backend_bundle,
            change_request=change_request,
            template_reference=template_reference,
        ),
        return_exceptions=True,
    )

    errors: list[str] = []
    frontend_bundle: dict[str, Any] | None = None
    backend_bundle: dict[str, Any] | None = None
    frontend_changed = False
    backend_changed = False

    if isinstance(frontend_result, Exception):
        if frontend_revision_fallback_allowed:
            try:
                fallback_bundle = _build_frontend_revision_fallback_bundle(master_json, template_reference)
                frontend_changed = _bundle_candidate_changes_existing(existing_frontend_bundle, fallback_bundle)
                frontend_bundle = fallback_bundle
            except Exception as exc:
                errors.append(f"Frontend generation failed: {frontend_result}; fallback generation failed: {exc}")
        else:
            errors.append(f"Frontend generation failed: {frontend_result}")
    else:
        try:
            frontend_bundle, frontend_changed = frontend_result
            if frontend_revision_fallback_allowed and not frontend_changed:
                fallback_bundle = _build_frontend_revision_fallback_bundle(master_json, template_reference)
                fallback_changed = _bundle_candidate_changes_existing(existing_frontend_bundle, fallback_bundle)
                if fallback_changed:
                    frontend_bundle = fallback_bundle
                    frontend_changed = True
            if existing_frontend_bundle:
                frontend_bundle = _merge_generated_bundle(existing_frontend_bundle, frontend_bundle)
        except Exception as exc:
            errors.append(f"Frontend generation validation failed: {exc}")

    if isinstance(backend_result, Exception):
        errors.append(f"Backend generation failed: {backend_result}")
    else:
        try:
            backend_bundle, backend_changed = backend_result
            if existing_backend_bundle:
                backend_bundle = _merge_generated_bundle(existing_backend_bundle, backend_bundle)
        except Exception as exc:
            errors.append(f"Backend generation validation failed: {exc}")

    if errors:
        raise RuntimeError("; ".join(errors))

    if (
        change_request
        and existing_frontend_bundle is not None
        and existing_backend_bundle is not None
        and not frontend_changed
        and not backend_changed
        and not _is_rebuild_retry_request(change_request)
    ):
        raise RuntimeError("Revision request completed without changing either the frontend or backend generated code.")

    return frontend_bundle or {"files": [], "dependencies": {}}, backend_bundle or {"files": [], "dependencies": {}}


def get_project_or_404(db: Session, project_id: str, user: User) -> Project:
    query = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None))
    if not user.is_superuser:
        query = query.filter(Project.owner_id == user.id)
    project = query.first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def run_project_locally(db: Session, project: Project) -> dict[str, Any]:
    return start_project_locally(db, project)


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


def _coerce_completeness_score(value: Any, default: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = float(default)
    return min(max(score, 0.0), 1.0)


def _gathering_stage_output(gathered: GatheringPayload, *, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    output = {
        "complete": gathered.complete,
        "assistant_response": gathered.assistant_response,
        "question": gathered.question,
        "current_module": gathered.current_module,
        "progress_summary": gathered.progress_summary,
        "completeness_score": gathered.completeness_score,
        "missing_topics": list(gathered.missing_topics or []),
        "captured_topics": list(gathered.captured_topics or []),
        "question_rationale": gathered.question_rationale,
        "analysis_model": analysis_model_label(),
    }
    if analysis:
        output["analysis_summary"] = analysis.get("summary")
        output["business_type"] = analysis.get("business_type")
        output["industry"] = analysis.get("industry")
        output["suggested_modules"] = list(analysis.get("suggested_modules") or [])
    if gathered.complete and gathered.requirements:
        output["requirements"] = gathered.requirements.model_dump()
    return output


def _gathering_response_message(gathered: GatheringPayload, fallback: str) -> str:
    return (gathered.assistant_response or gathered.question or fallback).strip()


def _artifact_bundle_from_rows(artifacts: list[GeneratedArtifact]) -> dict[str, Any]:
    dependencies: dict[str, Any] = {}
    files = []
    for artifact in artifacts:
        files.append(
            {
                "path": artifact.file_path,
                "language": artifact.language or "text",
                "content": artifact.content_text,
            }
        )
        metadata_dependencies = dict(artifact.metadata_json.get("dependencies") or {})
        dependencies.update(metadata_dependencies)
    return {"files": files, "dependencies": dependencies}


def hydrate_pipeline_outputs_from_current_version(db: Session, project: Project) -> dict[str, dict[str, Any]]:
    state = ensure_pipeline_state(project)
    if not project.current_project_version_id:
        return state

    project_version = (
        db.query(ProjectVersion)
        .filter(ProjectVersion.id == project.current_project_version_id, ProjectVersion.deleted_at.is_(None))
        .first()
    )
    if not project_version:
        return state

    snapshot = dict(project_version.snapshot_json or {})
    master_json_output = dict(snapshot.get("master_json") or {})
    if master_json_output:
        master_json_output = attach_erp_ui_template_metadata(
            master_json_output,
            get_project_template_reference(project, include_source_contents=False),
        )
        documentation = dict(master_json_output.get("documentation") or {})
        if snapshot.get("build_markdown") and not documentation.get("erp_build_markdown"):
            documentation["erp_build_markdown"] = snapshot.get("build_markdown")
        if documentation:
            master_json_output["documentation"] = documentation

    grouped_artifacts: dict[str, list[GeneratedArtifact]] = {}
    if project_version.generation_job_id:
        artifacts = (
            db.query(GeneratedArtifact)
            .filter(
                GeneratedArtifact.generation_job_id == project_version.generation_job_id,
                GeneratedArtifact.project_id == project.id,
                GeneratedArtifact.deleted_at.is_(None),
            )
            .order_by(GeneratedArtifact.file_path.asc())
            .all()
        )
        for artifact in artifacts:
            grouped_artifacts.setdefault(artifact.artifact_type, []).append(artifact)

    stage_outputs: dict[str, Any] = {
        "architecture": snapshot.get("architecture"),
        "json_transform": master_json_output or None,
        "frontend_generation": _artifact_bundle_from_rows(grouped_artifacts.get("frontend", [])),
        "backend_generation": _artifact_bundle_from_rows(grouped_artifacts.get("backend", [])),
        "code_review": snapshot.get("review"),
    }

    mutated = False
    for stage, output in stage_outputs.items():
        if not output:
            continue
        stage_state = dict(state.get(stage) or {})
        if stage_state.get("output") is None:
            stage_state["output"] = output
            if stage_state.get("status") == "pending" and project.status == "COMPLETE":
                stage_state["status"] = "complete"
            stage_state["updated_at"] = stage_state.get("updated_at") or now_iso()
            state[stage] = stage_state
            mutated = True

    if mutated:
        project.pipeline_state = state

    return state


def _load_revision_context(db: Session, project: Project) -> dict[str, Any]:
    hydrate_pipeline_outputs_from_current_version(db, project)
    if not project.current_project_version_id:
        return {}

    project_version = (
        db.query(ProjectVersion)
        .filter(ProjectVersion.id == project.current_project_version_id, ProjectVersion.deleted_at.is_(None))
        .first()
    )
    if not project_version:
        return {}

    snapshot = dict(project_version.snapshot_json or {})
    context: dict[str, Any] = {
        "project_version_id": project_version.id,
        "version_label": project_version.version_label,
        "changelog": project_version.changelog,
        "architecture": snapshot.get("architecture") or {},
        "master_json": attach_erp_ui_template_metadata(
            snapshot.get("master_json") or {},
            get_project_template_reference(project, include_source_contents=False),
        ),
        "build_markdown": snapshot.get("build_markdown") or "",
        "review": snapshot.get("review") or {},
    }

    if project_version.generation_job_id:
        artifacts = (
            db.query(GeneratedArtifact)
            .filter(
                GeneratedArtifact.generation_job_id == project_version.generation_job_id,
                GeneratedArtifact.project_id == project.id,
                GeneratedArtifact.deleted_at.is_(None),
            )
            .order_by(GeneratedArtifact.file_path.asc())
            .all()
        )
        grouped: dict[str, list[GeneratedArtifact]] = {}
        for artifact in artifacts:
            grouped.setdefault(artifact.artifact_type, []).append(artifact)
        context["frontend_bundle"] = _artifact_bundle_from_rows(grouped.get("frontend", []))
        context["backend_bundle"] = _artifact_bundle_from_rows(grouped.get("backend", []))

    return context


def _merge_generated_bundle(previous_bundle: dict[str, Any] | None, new_bundle: dict[str, Any] | None) -> dict[str, Any]:
    previous_bundle = dict(previous_bundle or {})
    new_bundle = dict(new_bundle or {})

    merged_dependencies = dict(previous_bundle.get("dependencies") or {})
    merged_dependencies.update(dict(new_bundle.get("dependencies") or {}))

    file_map: dict[str, dict[str, Any]] = {}
    file_order: list[str] = []
    for bundle in [previous_bundle, new_bundle]:
        for item in bundle.get("files") or []:
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            if path not in file_map:
                file_order.append(path)
            file_map[path] = {
                "path": path,
                "language": item.get("language") or "text",
                "content": item.get("content") or "",
            }

    return {
        "files": [file_map[path] for path in file_order],
        "dependencies": merged_dependencies,
    }


def _strengthen_revision_request(change_request: str | None, target: str) -> str:
    base_request = (change_request or "").strip() or "Apply the requested revision."
    return (
        f"{base_request}\n\n"
        f"IMPORTANT: The previous {target} revision attempt did not produce meaningful code changes. "
        f"You must directly modify the existing {target} code to implement this request. "
        "Return updated file contents for the files that need to change and do not send an unchanged bundle."
    )


def _is_rebuild_retry_request(change_request: str | None) -> bool:
    lowered = str(change_request or "").strip().lower()
    if not lowered:
        return False

    direct_phrases = [
        "rebuild",
        "rebuilt",
        "re-build",
        "build again",
        "rebuild it",
        "rebuilt it",
        "regenerate",
        "generate again",
        "rerun",
        "re-run",
        "run again",
        "retry",
        "try again",
        "reubit",
        "rebuit",
        "rebuid",
        "rebuild the app",
        "rebuild the erp",
        "rerun the build",
    ]
    if any(phrase in lowered for phrase in direct_phrases):
        return True

    normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    retry_only_messages = {
        "again",
        "retry",
        "rerun",
        "regenerate",
        "rebuild",
        "rebuilt",
        "rebuild it",
        "rebuilt it",
        "reubit it",
        "rebuit it",
        "rebuid it",
        "run again",
        "try again",
    }
    return normalized in retry_only_messages


def _bundle_candidate_changes_existing(
    existing_bundle: dict[str, Any] | None,
    candidate_bundle: dict[str, Any],
) -> bool:
    candidate_files = candidate_bundle.get("files") or []
    candidate_dependencies = dict(candidate_bundle.get("dependencies") or {})
    if existing_bundle is None:
        return bool(candidate_files or candidate_dependencies)

    existing_files = {
        str(item.get("path") or "").strip(): {
            "content": item.get("content") or "",
            "language": item.get("language") or "text",
        }
        for item in (existing_bundle.get("files") or [])
        if str(item.get("path") or "").strip()
    }
    existing_dependencies = dict(existing_bundle.get("dependencies") or {})

    for item in candidate_files:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        existing_item = existing_files.get(path)
        if not existing_item:
            return True
        if existing_item["content"] != (item.get("content") or ""):
            return True
        if existing_item["language"] != (item.get("language") or "text"):
            return True

    for name, version in candidate_dependencies.items():
        if existing_dependencies.get(name) != version:
            return True

    return False


async def _invoke_code_generator(
    generator: Any,
    master_json: dict[str, Any],
    markdown_spec: str,
    *,
    existing_bundle: dict[str, Any] | None = None,
    change_request: str | None = None,
    template_reference: dict[str, Any] | None = None,
) -> Any:
    generator_signature = signature(generator)
    kwargs: dict[str, Any] = {}
    if "existing_bundle" in generator_signature.parameters:
        kwargs["existing_bundle"] = existing_bundle
    if "change_request" in generator_signature.parameters:
        kwargs["change_request"] = change_request
    if "template_reference" in generator_signature.parameters:
        kwargs["template_reference"] = template_reference
    return await generator(master_json, markdown_spec, **kwargs)


async def _generate_candidate_code_bundle(
    generator: Any,
    target: str,
    master_json: dict[str, Any],
    markdown_spec: str,
    *,
    existing_bundle: dict[str, Any] | None = None,
    change_request: str | None = None,
    template_reference: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    candidate_bundle = _validate_bundle(
        await _invoke_code_generator(
            generator,
            master_json,
            markdown_spec,
            existing_bundle=existing_bundle,
            change_request=change_request,
            template_reference=template_reference,
        )
    )
    changed = _bundle_candidate_changes_existing(existing_bundle, candidate_bundle)

    if change_request and existing_bundle is not None and not changed:
        candidate_bundle = _validate_bundle(
            await _invoke_code_generator(
                generator,
                master_json,
                markdown_spec,
                existing_bundle=existing_bundle,
                change_request=_strengthen_revision_request(change_request, target),
                template_reference=template_reference,
            )
        )
        changed = _bundle_candidate_changes_existing(existing_bundle, candidate_bundle)

    return candidate_bundle, changed


async def _invoke_markdown_blueprint_generator(
    generator: Any,
    project_name: str,
    conversation_transcript: str,
    requirements: dict[str, Any],
    architecture: dict[str, Any],
    master_json: dict[str, Any],
    *,
    existing_markdown: str | None = None,
    change_request: str | None = None,
    template_reference: dict[str, Any] | None = None,
) -> str:
    generator_signature = signature(generator)
    kwargs: dict[str, Any] = {}
    if "existing_markdown" in generator_signature.parameters:
        kwargs["existing_markdown"] = existing_markdown
    if "change_request" in generator_signature.parameters:
        kwargs["change_request"] = change_request
    if "template_reference" in generator_signature.parameters:
        kwargs["template_reference"] = template_reference
    return await generator(
        project_name,
        conversation_transcript,
        requirements,
        architecture,
        master_json,
        **kwargs,
    )


def create_project(db: Session, owner: User, payload: ProjectCreateRequest) -> Project:
    selected_template_id = resolve_erp_ui_template_id(payload.template_id)
    project = Project(
        owner_id=owner.id,
        name=payload.name,
        description=payload.description,
        prompt_text=payload.prompt,
        status="INIT",
        lifecycle_state="draft",
        pipeline_state=default_pipeline_state(),
        metadata_json={"selected_template_id": selected_template_id},
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


async def auto_start_project_from_prompt(project_id: str, user_id: str, prompt: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
        user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        if not project or not user or project.status != "INIT":
            return

        background_tasks = InProcessBackgroundTasks()
        await handle_project_chat(db, project, user, prompt, background_tasks)
        await _run_in_process_background_tasks(background_tasks)
    except Exception:
        logger.exception("Failed to auto-start project %s from initial prompt", project_id)
    finally:
        db.close()


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

    hydrate_pipeline_outputs_from_current_version(db, project)
    reset_generation_stages(
        project,
        preserve_existing_outputs=bool(change_request and project.current_project_version_id and project.status == "COMPLETE"),
    )
    job = GenerationJob(
        project_id=project.id,
        requested_by_id=user.id,
        blueprint_version_id=project.current_blueprint_version_id,
        job_type="partial_regeneration" if change_request else "full_generation",
        status="queued",
        current_stage="architecture",
        change_request=change_request,
        job_spec_json={"change_request": change_request, "base_project_version_id": project.current_project_version_id},
    )
    db.add(job)
    db.flush()

    if change_request:
        db.add(
            Prompt(
                project_id=project.id,
                created_by_id=user.id,
                content=change_request,
                kind="revision",
                metadata_json={"base_project_version_id": project.current_project_version_id},
            )
        )

    project.current_generation_job_id = job.id
    project.status = "ARCHITECTING"
    project.lifecycle_state = "revision_queued" if change_request else "generation_queued"

    msg = (
        "Applying your changes on top of the current ERP build. Regenerating the affected blueprint and code artifacts..."
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
        completeness_score=project.requirement_completeness,
        analysis_model=analysis_model_label(),
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
            requirement_session.current_module = gathered.current_module
            requirement_session.summary = gathered.progress_summary or analysis.get("summary", "")
            project.requirement_completeness = 1.0
            update_stage(project, "requirement_gathering", "complete", _gathering_stage_output(gathered, analysis=analysis))
            db.commit()
            return await _queue_generation(db, project, user, background_tasks)

        assistant_message = _gathering_response_message(gathered, "What module or workflow should the ERP prioritize first?")
        db.add(
            ClarificationQuestion(
                requirement_session_id=requirement_session.id,
                project_id=project.id,
                question_text=gathered.question or assistant_message,
                module_name=gathered.current_module,
                status="pending",
            )
        )
        requirement_session.status = "collecting"
        requirement_session.current_module = gathered.current_module
        requirement_session.summary = gathered.progress_summary or analysis.get("summary", "")
        requirement_session.completeness_score = max(0.3, _coerce_completeness_score(gathered.completeness_score, 0.5))
        project.requirement_completeness = requirement_session.completeness_score
        project.status = "GATHERING"
        update_stage(project, "requirement_gathering", "running", _gathering_stage_output(gathered, analysis=analysis))
        add_project_message(db, project.id, "assistant", assistant_message, agent="requirement_gatherer")
        db.commit()
        return ChatResponse(
            response=assistant_message,
            status=project.status,
            analysis=analysis,
            current_module=gathered.current_module,
            progress=gathered.progress_summary,
            completeness_score=project.requirement_completeness,
            missing_topics=list(gathered.missing_topics or []),
            captured_topics=list(gathered.captured_topics or []),
            question_rationale=gathered.question_rationale,
            analysis_model=analysis_model_label(),
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
            requirement_session.current_module = gathered.current_module
            requirement_session.summary = gathered.progress_summary or requirement_session.summary
            project.requirement_completeness = 1.0
            update_stage(project, "requirement_gathering", "complete", _gathering_stage_output(gathered, analysis=requirement_session.analysis_json))
            db.commit()
            return await _queue_generation(db, project, user, background_tasks)

        assistant_message = _gathering_response_message(gathered, "What else should the system support operationally?")
        db.add(
            ClarificationQuestion(
                requirement_session_id=requirement_session.id,
                project_id=project.id,
                question_text=gathered.question or assistant_message,
                module_name=gathered.current_module,
                status="pending",
            )
        )
        requirement_session.current_module = gathered.current_module
        requirement_session.summary = gathered.progress_summary or requirement_session.summary
        requirement_session.completeness_score = min(
            max(
                requirement_session.completeness_score,
                _coerce_completeness_score(gathered.completeness_score, requirement_session.completeness_score or 0.5),
            ),
            0.95,
        )
        project.requirement_completeness = requirement_session.completeness_score
        update_stage(project, "requirement_gathering", "running", _gathering_stage_output(gathered, analysis=requirement_session.analysis_json))
        add_project_message(db, project.id, "assistant", assistant_message, agent="requirement_gatherer")
        db.commit()
        return ChatResponse(
            response=assistant_message,
            status=project.status,
            current_module=gathered.current_module,
            progress=gathered.progress_summary,
            completeness_score=project.requirement_completeness,
            missing_topics=list(gathered.missing_topics or []),
            captured_topics=list(gathered.captured_topics or []),
            question_rationale=gathered.question_rationale,
            analysis_model=analysis_model_label(),
        )

    if project.status in {"ARCHITECTING", "TRANSFORMING", "GENERATING_FRONTEND", "GENERATING_BACKEND", "REVIEWING"}:
        db.commit()
        return ChatResponse(
            response="The project is still processing. Please wait for the current job to finish.",
            status=project.status,
            analysis_model=analysis_model_label(),
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
        revision_context = _load_revision_context(db, project) if change_request else {}
        template_reference = get_project_template_reference(project)

        job.status = "running"
        job.started_at = utc_now()
        project.lifecycle_state = "revision_running" if change_request else "generation_running"
        db.commit()

        if change_request and _can_attempt_direct_code_revision(revision_context):
            try:
                direct_revision_applied = await _attempt_direct_code_revision(
                    db,
                    project,
                    job,
                    revision_context=revision_context,
                    template_reference=template_reference,
                    change_request=change_request,
                )
                if direct_revision_applied:
                    return
            except Exception as exc:
                logger.warning(
                    "Direct code revision fast path failed for project %s job %s: %s",
                    project.id,
                    job.id,
                    exc,
                )
                db.rollback()
                project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
                job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
                if not project or not job:
                    return
                revision_context = _load_revision_context(db, project) if change_request else {}
                template_reference = get_project_template_reference(project)
                reset_generation_stages(
                    project,
                    preserve_existing_outputs=bool(change_request and project.current_project_version_id),
                )
                db.commit()

        project.status = "ARCHITECTING"
        update_stage(project, "architecture", "running")
        db.commit()

        architecture = _validate_architecture(
            await erp_architect(
                requirements,
                change_request,
                existing_architecture=revision_context.get("architecture"),
                existing_master_json=revision_context.get("master_json"),
            )
        )
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

        master_json = _validate_master_json(
            await json_transformer(
                architecture,
                existing_master_json=revision_context.get("master_json"),
                change_request=change_request,
            )
        )
        master_json = attach_erp_ui_template_metadata(master_json, template_reference)
        master_json = _apply_ui_revision_directives(master_json, change_request)
        conversation_transcript = build_chat_transcript(db, project.id)
        markdown_spec = await _invoke_markdown_blueprint_generator(
            markdown_blueprint_generator,
            project.name,
            conversation_transcript,
            requirements,
            architecture,
            master_json,
            existing_markdown=revision_context.get("build_markdown"),
            change_request=change_request,
            template_reference=template_reference,
        )
        documentation = dict(master_json.get("documentation") or {})
        documentation["erp_build_markdown"] = markdown_spec
        documentation["source_summary"] = requirement_session.summary or architecture.get("description", "")
        documentation["chat_transcript_markdown"] = conversation_transcript
        master_json["documentation"] = documentation
        update_stage(project, "json_transform", "complete", master_json)
        add_project_message(db, project.id, "assistant", "Blueprint normalized into the master ERP JSON contract.", agent="json_transformer")
        db.commit()

        project.status = "GENERATING_FRONTEND"
        job.current_stage = "frontend_generation"
        update_stage(project, "frontend_generation", "running")
        update_stage(project, "backend_generation", "running")
        db.commit()

        frontend_bundle, backend_bundle = await generate_code_bundles(
            master_json,
            markdown_spec,
            existing_frontend_bundle=revision_context.get("frontend_bundle"),
            existing_backend_bundle=revision_context.get("backend_bundle"),
            change_request=change_request,
            template_reference=template_reference,
        )
        await _finalize_generation_success(
            db,
            project,
            job,
            blueprint_id=blueprint.id,
            blueprint_reference=blueprint.version_number,
            architecture=architecture,
            master_json=master_json,
            markdown_spec=markdown_spec,
            frontend_bundle=frontend_bundle,
            backend_bundle=backend_bundle,
            revision_context=revision_context,
            change_request=change_request,
        )
    except Exception as exc:
        db.rollback()
        project = db.query(Project).filter(Project.id == project_id).first()
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if project and job:
            failure_state = _apply_generation_failure_state(project, job, str(exc), change_request=change_request)
            add_project_message(
                db,
                project.id,
                "assistant",
                failure_state["message"],
                agent="system",
            )
            add_notification(
                db,
                job.requested_by_id or project.owner_id,
                failure_state["notification_title"],
                failure_state["notification_body"],
                project.id,
            )
            add_audit_log(
                db,
                "generation.failed",
                "generation_job",
                job.id,
                user_id=job.requested_by_id,
                project_id=project.id,
                details=failure_state["audit_details"],
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

    original_output = dict(json_stage.get("output") or {})
    output = dict(original_output)
    if not output:
        return output

    template_reference = get_project_template_reference(project)
    output = attach_erp_ui_template_metadata(output, template_reference)
    metadata_changed = output != original_output
    documentation = dict(output.get("documentation") or {})
    existing_markdown = documentation.get("erp_build_markdown")
    if existing_markdown and is_valid_markdown_blueprint(existing_markdown):
        if metadata_changed:
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
                    project_version.snapshot_json = snapshot

            db.commit()
            db.refresh(project)
        return output

    requirement_session = get_requirement_session(db, project)
    architecture_output = dict((state.get("architecture") or {}).get("output") or {})
    conversation_transcript = build_chat_transcript(db, project.id)
    markdown_spec = await _invoke_markdown_blueprint_generator(
        markdown_blueprint_generator,
        project.name,
        conversation_transcript,
        requirement_session.normalized_requirements or {},
        architecture_output,
        output,
        template_reference=template_reference,
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
