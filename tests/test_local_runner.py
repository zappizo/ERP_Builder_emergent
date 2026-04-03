import json
import shutil
import sys
import urllib.error
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.local_runner import (
    _build_backend_runtime_files,
    _build_frontend_runtime_files,
    _normalize_python_package_files,
    _patch_backend_main_file,
    _patch_sqlalchemy_extend_existing,
    _remove_shadowing_package_modules,
    _reset_runtime_directory,
    _repair_sqlalchemy_models_file,
    _url_ready,
)


def test_build_frontend_runtime_files_includes_runtime_proxy_and_dependencies():
    files = _build_frontend_runtime_files(
        "My ERP",
        generated_files=[{"path": "src/App.jsx", "language": "jsx", "content": "export default function App(){ return null; }"}],
        dependencies={
            "react": "^18.0.0",
            "react-router-dom": "^6.0.0",
            "tailwindcss": "^3.0.0",
            "lucide-react": "^0.264.0",
        },
        frontend_port=3123,
        backend_port=8123,
    )

    file_map = {entry["path"]: entry["content"] for entry in files}
    package_json = json.loads(file_map["package.json"])

    assert package_json["dependencies"]["lucide-react"] == "^0.264.0"
    assert package_json["dependencies"]["react"] == "^18.0.0"
    assert "8123" in file_map["vite.config.js"]
    assert "3123" in file_map["vite.config.js"]


def test_build_backend_runtime_files_patches_database_to_sqlite():
    files = _build_backend_runtime_files(
        "My ERP",
        generated_files=[
            {
                "path": "main.py",
                "language": "python",
                "content": "from fastapi import FastAPI\nfrom routes import router\nfrom procurement.routes import procurement_router\n\napp = FastAPI()\napp.include_router(router, prefix=\"/api\")\napp.include_router(procurement_router, prefix=\"/api/procurement\")",
            },
            {"path": "auth.py", "language": "python", "content": "from fastapi import Header, HTTPException\n\ndef require_user(authorization: str | None = Header(default=None)):\n    raise HTTPException(status_code=401, detail='Missing bearer token')"},
            {
                "path": "database.py",
                "language": "python",
                "content": 'DATABASE_URL = "postgresql://user:password@localhost/dbname"',
            },
        ],
        dependencies={"fastapi": ">=0.100.0", "sqlalchemy": ">=2.0.0"},
    )

    file_map = {entry["path"]: entry["content"] for entry in files}

    assert "sqlite:///./generated_app.db" in file_map["database.py"]
    assert "def init_db()" in file_map["database.py"]
    assert "@app.on_event(\"startup\")" in file_map["main.py"]
    assert "try:\n    from procurement.routes import procurement_router\nexcept Exception:\n    procurement_router = None" in file_map["main.py"]
    assert "if procurement_router is not None:\n    app.include_router(procurement_router, prefix=\"/api/procurement\")" in file_map["main.py"]
    assert "local-preview" in file_map["auth.py"]
    assert "uvicorn[standard]>=0.30.0" in file_map["requirements.txt"]


def test_patch_backend_main_file_handles_router_alias_imports_safely():
    content = """from fastapi import FastAPI
from routes import router
from project_management.routes import router as project_management_router

app = FastAPI()
app.include_router(router, prefix="/api")
app.include_router(project_management_router, prefix="/api")
"""

    patched = _patch_backend_main_file(content)

    assert "from project_management.routes import router as project_management_router" in patched
    assert "project_management_router = None" in patched
    assert "router as project_management_router = None" not in patched
    assert "if project_management_router is not None:\n    app.include_router(project_management_router, prefix=\"/api\")" in patched


def test_patch_backend_main_file_handles_routes_submodule_imports_safely():
    content = """from fastapi import FastAPI
from routes.patient_management import router as patient_router

app = FastAPI()
app.include_router(patient_router, prefix="/api/patient-management")
"""

    patched = _patch_backend_main_file(content)

    assert "try:\n    from routes.patient_management import router as patient_router\nexcept Exception:\n    patient_router = None" in patched
    assert "if patient_router is not None:\n    app.include_router(patient_router, prefix=\"/api/patient-management\")" in patched


def test_normalize_python_package_files_promotes_shadowing_module_into_package():
    files = _normalize_python_package_files(
        [
            {"path": "routes.py", "language": "python", "content": "from fastapi import APIRouter\nrouter = APIRouter()\n"},
            {"path": "routes/patient_management.py", "language": "python", "content": "from fastapi import APIRouter\nrouter = APIRouter()\n"},
        ]
    )

    file_map = {entry["path"]: entry["content"] for entry in files}

    assert "routes.py" not in file_map
    assert "routes/__init__.py" in file_map
    assert "router = APIRouter()" in file_map["routes/__init__.py"]
    assert "routes/patient_management.py" in file_map


def test_remove_shadowing_package_modules_deletes_conflicting_module_file():
    runtime_dir = ROOT / f"_tmp_local_runner_{uuid.uuid4().hex}"
    try:
        runtime_dir.mkdir()
        (runtime_dir / "routes").mkdir()
        (runtime_dir / "routes.py").write_text("shadow", encoding="utf-8")
        (runtime_dir / "routes" / "__init__.py").write_text("", encoding="utf-8")

        _remove_shadowing_package_modules(
            runtime_dir,
            [
                {"path": "routes/__init__.py", "language": "python", "content": ""},
                {"path": "routes/patient_management.py", "language": "python", "content": ""},
            ],
        )

        assert not (runtime_dir / "routes.py").exists()
        assert (runtime_dir / "routes" / "__init__.py").exists()
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)


def test_repair_sqlalchemy_models_file_fixes_common_indentation_damage():
    broken = """from sqlalchemy import Column, String

    from database import Base

    class Patients(Base):
        __tablename__ = "patients"
        id = Column(String, primary_key=True, nullable=False)
first_name = Column(String, primary_key=False, nullable=False)
"""

    repaired = _repair_sqlalchemy_models_file(broken)

    assert "from database import Base" in repaired
    assert "\nclass Patients(Base):\n" in repaired
    assert "    __tablename__ = \"patients\"" in repaired
    assert "    first_name = Column(String, primary_key=False, nullable=False)" in repaired


def test_patch_sqlalchemy_extend_existing_adds_runtime_table_guard():
    content = """from sqlalchemy import Column, String
from database import Base

class Projects(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
"""

    patched = _patch_sqlalchemy_extend_existing(content)

    assert '__table_args__ = {"extend_existing": True}' in patched
    assert patched.index('__tablename__ = "projects"') < patched.index('__table_args__ = {"extend_existing": True}')


def test_url_ready_treats_http_error_response_as_running(monkeypatch):
    def fake_urlopen(url, timeout=3.0):
        raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("backend.app.local_runner.urllib.request.urlopen", fake_urlopen)

    assert _url_ready("http://127.0.0.1:9999/")


def test_reset_runtime_directory_preserves_dependency_cache():
    runtime_dir = ROOT / f"_tmp_local_runner_{uuid.uuid4().hex}"
    try:
        runtime_dir.mkdir()
        (runtime_dir / "src").mkdir()
        (runtime_dir / "src" / "App.jsx").write_text("old", encoding="utf-8")
        (runtime_dir / "node_modules").mkdir()
        (runtime_dir / "node_modules" / "marker.txt").write_text("keep", encoding="utf-8")
        (runtime_dir / "install.log").write_text("keep", encoding="utf-8")

        _reset_runtime_directory(runtime_dir, {"node_modules", "install.log"})

        assert not (runtime_dir / "src").exists()
        assert (runtime_dir / "node_modules" / "marker.txt").exists()
        assert (runtime_dir / "install.log").exists()
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)
