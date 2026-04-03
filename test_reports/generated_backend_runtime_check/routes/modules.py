from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import RecordActionRequest, RecordCreateRequest
from security import get_current_user
from services import create_record, module_catalog, module_workspace_payload, run_record_action

router = APIRouter(tags=["modules"])


@router.get("/modules")
def list_modules(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"modules": module_catalog(db, current_user["role"])}


@router.get("/modules/{module_id}")
def module_summary(module_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return module_workspace_payload(db, module_id, current_user)


@router.post("/modules/{module_id}/records")
def create_module_record(
    module_id: str,
    payload: RecordCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_record(db, module_id, payload.model_dump(), current_user)


@router.post("/modules/{module_id}/records/{record_id}/actions")
def apply_record_action(
    module_id: str,
    record_id: str,
    payload: RecordActionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return run_record_action(db, module_id, record_id, payload.action, current_user, payload.note)