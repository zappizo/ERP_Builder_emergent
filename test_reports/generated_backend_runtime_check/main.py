from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, init_db
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.meta import router as meta_router
from routes.modules import router as modules_router
from seed import seed_system


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_system(db)
    finally:
        db.close()
    yield


app = FastAPI(title='Functional ERP', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")
app.include_router(meta_router, prefix="/api/meta")
app.include_router(dashboard_router, prefix="/api")
app.include_router(modules_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "system": 'Functional ERP'}