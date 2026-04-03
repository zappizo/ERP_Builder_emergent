from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import SessionLocal, init_db
from .deps import get_or_create_bootstrap_user
from .routes.auth import router as auth_router
from .routes.platform import router as platform_router
from .routes.projects import router as projects_router
from .schemas import StatusResponse
from .services import recover_interrupted_generation_jobs


settings = get_settings()
app = FastAPI(title=settings.app_name)
api_router = APIRouter(prefix=settings.api_prefix)


@api_router.get("", response_model=StatusResponse)
@api_router.get("/", response_model=StatusResponse)
def api_root() -> StatusResponse:
    return StatusResponse(status="ok", message="Zappizo API")


@api_router.get("/health", response_model=StatusResponse)
def healthcheck() -> StatusResponse:
    return StatusResponse(status="ok", message="healthy")


api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(platform_router)
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    if not settings.auth_required:
        with SessionLocal() as db:
            get_or_create_bootstrap_user(db)
            recover_interrupted_generation_jobs(db)
