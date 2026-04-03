from fastapi import APIRouter

from services import role_directory_payload

router = APIRouter(tags=["meta"])


@router.get("/roles")
def roles():
    return role_directory_payload()