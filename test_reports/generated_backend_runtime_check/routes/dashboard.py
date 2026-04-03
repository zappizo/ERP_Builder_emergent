from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from security import get_current_user
from services import dashboard_payload, recent_activity

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return dashboard_payload(db, current_user)


@router.get("/workflow/events")
def workflow_events(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return recent_activity(db, limit=12)