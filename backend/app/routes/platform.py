from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ensure_active_user
from ..models import User
from ..schemas import (
    APIConfigurationRead,
    APIConfigurationUpsertRequest,
    AutomationWorkflowCreateRequest,
    AutomationWorkflowRead,
    DeploymentCreateRequest,
    DeploymentLogRead,
    DeploymentRead,
    NotificationRead,
)
from ..services import (
    create_automation_workflow,
    create_deployment,
    list_api_configurations,
    list_automation_workflows,
    list_deployment_logs,
    list_deployments,
    list_notifications,
    mark_notification_read,
    upsert_api_configuration,
)


router = APIRouter(tags=["platform"])


@router.post("/deployments", response_model=DeploymentRead)
def create_deployment_endpoint(
    payload: DeploymentCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> DeploymentRead:
    return create_deployment(db, user, payload)


@router.get("/deployments", response_model=list[DeploymentRead])
def list_deployments_endpoint(
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[DeploymentRead]:
    return list_deployments(db, user, project_id=project_id)


@router.get("/deployments/{deployment_id}/logs", response_model=list[DeploymentLogRead])
def list_deployment_logs_endpoint(
    deployment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[DeploymentLogRead]:
    return list_deployment_logs(db, user, deployment_id)


@router.post("/settings/api-configurations", response_model=APIConfigurationRead)
def upsert_api_configuration_endpoint(
    payload: APIConfigurationUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> APIConfigurationRead:
    return upsert_api_configuration(db, user, payload)


@router.get("/settings/api-configurations", response_model=list[APIConfigurationRead])
def list_api_configurations_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[APIConfigurationRead]:
    return list_api_configurations(db, user)


@router.post("/automations", response_model=AutomationWorkflowRead)
def create_automation_workflow_endpoint(
    payload: AutomationWorkflowCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> AutomationWorkflowRead:
    return create_automation_workflow(db, user, payload)


@router.get("/automations", response_model=list[AutomationWorkflowRead])
def list_automation_workflows_endpoint(
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[AutomationWorkflowRead]:
    return list_automation_workflows(db, user, project_id=project_id)


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications_endpoint(
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> list[NotificationRead]:
    return list_notifications(db, user)


@router.post("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read_endpoint(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(ensure_active_user),
) -> NotificationRead:
    return mark_notification_read(db, user, notification_id)
