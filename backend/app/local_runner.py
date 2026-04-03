from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import GeneratedArtifact, GenerationJob, Project


ROOT_DIR = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = ROOT_DIR / "runtime-generated"
WINDOWS_CREATION_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
)


def _sha1(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _project_slug(value: str, fallback: str = "ai-erp-builder") -> str:
    sanitized = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")
    sanitized = sanitized.strip("-")
    return sanitized or fallback


def _merge_files(scaffold_files: list[dict[str, Any]], generated_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_map: dict[str, dict[str, Any]] = {}
    for entry in [*scaffold_files, *generated_files]:
        path = str(entry.get("path") or "").strip().replace("\\", "/")
        if not path:
            continue
        file_map[path] = {
            "path": path,
            "language": entry.get("language") or "text",
            "content": str(entry.get("content") or ""),
        }
    return list(file_map.values())


def _normalize_python_package_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_map: dict[str, dict[str, Any]] = {
        str(entry.get("path") or "").strip().replace("\\", "/"): {
            "path": str(entry.get("path") or "").strip().replace("\\", "/"),
            "language": entry.get("language") or "text",
            "content": str(entry.get("content") or ""),
        }
        for entry in files
        if str(entry.get("path") or "").strip()
    }

    package_dirs: set[str] = set()
    for path in list(file_map):
        if not path.endswith(".py") or "/" not in path:
            continue
        parent_parts = path.split("/")[:-1]
        for depth in range(1, len(parent_parts) + 1):
            package_dirs.add("/".join(parent_parts[:depth]))

    for package_dir in sorted(package_dirs, key=lambda value: (value.count("/"), value)):
        module_path = f"{package_dir}.py"
        init_path = f"{package_dir}/__init__.py"
        if module_path in file_map:
            module_entry = file_map.pop(module_path)
            if init_path in file_map:
                existing = file_map[init_path]["content"].rstrip()
                incoming = module_entry["content"].strip()
                if incoming and incoming not in existing:
                    merged = f"{existing}\n\n{incoming}".strip()
                    file_map[init_path] = {**file_map[init_path], "content": f"{merged}\n"}
            else:
                file_map[init_path] = {**module_entry, "path": init_path}
        elif init_path not in file_map:
            file_map[init_path] = {"path": init_path, "language": "python", "content": ""}

    return list(file_map.values())


def _patch_backend_database_file(content: str) -> str:
    return """from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./generated_app.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""


def _patch_backend_main_file(content: str) -> str:
    normalized = _strip_code_fences(content).rstrip()
    if "app = FastAPI" not in normalized:
        return f"{normalized}\n"

    lines = normalized.splitlines()
    safe_router_names: set[str] = set()
    rewritten_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        match = re.match(r"^from\s+([A-Za-z0-9_\.]+)\s+import\s+(.+)$", stripped)
        if match:
            module_name = match.group(1)
            route_like_import = (
                module_name == "routes"
                or module_name.startswith("routes.")
                or module_name.endswith(".routes")
                or ".routes." in module_name
            )
            imported_specs = [name.strip() for name in match.group(2).split(",") if name.strip()]
            parsed_specs: list[tuple[str, str]] = []
            for imported_spec in imported_specs:
                alias_match = re.match(
                    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?$",
                    imported_spec,
                )
                if not alias_match:
                    parsed_specs = []
                    break
                original_name = alias_match.group("name")
                variable_name = alias_match.group("alias") or original_name
                parsed_specs.append((original_name, variable_name))

            if route_like_import and parsed_specs and all(
                variable_name.endswith("router") or original_name == "router"
                for original_name, variable_name in parsed_specs
            ):
                for original_name, variable_name in parsed_specs:
                    safe_router_names.add(variable_name)
                    import_target = (
                        f"{original_name} as {variable_name}" if variable_name != original_name else original_name
                    )
                    rewritten_lines.extend(
                        [
                            "try:",
                            f"    from {module_name} import {import_target}",
                            "except Exception:",
                            f"    {variable_name} = None",
                        ]
                    )
                continue
        rewritten_lines.append(line)

    final_lines: list[str] = []
    for line in rewritten_lines:
        stripped = line.strip()
        include_match = re.match(r"^app\.include_router\(\s*([A-Za-z0-9_]+)\s*,(.*)\)\s*$", stripped)
        if include_match and include_match.group(1) in safe_router_names:
            router_name = include_match.group(1)
            final_lines.append(f"if {router_name} is not None:")
            final_lines.append(f"    {stripped}")
            continue
        final_lines.append(line)

    normalized = "\n".join(final_lines).rstrip()
    if "init_db" in normalized:
        return f"{normalized}\n"

    return (
        f"{normalized}\n\n"
        "try:\n"
        "    from database import init_db\n\n"
        "    @app.on_event(\"startup\")\n"
        "    def _runtime_init_db():\n"
        "        init_db()\n"
        "except Exception:\n"
        "    pass\n"
    )


def _patch_backend_auth_file(content: str) -> str:
    normalized = _strip_code_fences(content).rstrip()
    if "def require_user(" not in normalized:
        return f"{normalized}\n"

    return """from fastapi import Header


def require_user(authorization: str | None = Header(default=None)):
    token = authorization or "Bearer local-preview"
    return {"user_id": "demo-user", "scopes": ["erp.access"], "authorization": token}
"""


def _strip_code_fences(content: str) -> str:
    lines = str(content or "").replace("\r\n", "\n").split("\n")
    filtered = [line for line in lines if not line.strip().startswith("```")]
    normalized = "\n".join(filtered).strip("\n")
    return f"{normalized}\n" if normalized else ""


def _repair_sqlalchemy_models_file(content: str) -> str:
    lines = _strip_code_fences(content).replace("\t", "    ").splitlines()
    repaired: list[str] = []
    inside_class = False

    for raw_line in lines:
      stripped = raw_line.strip()
      if not stripped:
          repaired.append("")
          continue

      if re.match(r"^(from|import)\b", stripped):
          inside_class = False
          repaired.append(stripped)
          continue

      if re.match(r"^class\s+\w+.*:\s*$", stripped):
          inside_class = True
          repaired.append(stripped)
          continue

      if inside_class and not re.match(r"^(class|from|import)\b", stripped):
          repaired.append(f"    {stripped}")
          continue

      inside_class = False
      repaired.append(stripped)

    normalized = "\n".join(repaired).strip("\n")
    return f"{normalized}\n" if normalized else ""


def _patch_sqlalchemy_extend_existing(content: str) -> str:
    normalized = _repair_sqlalchemy_models_file(content).splitlines()
    if not normalized:
        return ""

    blocks: list[tuple[str, list[str]]] = []
    prefix: list[str] = []
    current_header: str | None = None
    current_block: list[str] = []

    def flush_current() -> None:
        nonlocal current_header, current_block
        if current_header is not None:
            blocks.append((current_header, current_block[:]))
            current_header = None
            current_block = []

    for line in normalized:
        if re.match(r"^class\s+\w+.*:\s*$", line.strip()):
            flush_current()
            current_header = line.strip()
            current_block = []
            continue
        if current_header is None:
            prefix.append(line.rstrip())
        else:
            current_block.append(line.rstrip())

    flush_current()

    patched_lines: list[str] = prefix[:]
    for header, block in blocks:
        patched_lines.append(header)
        has_tablename = any("__tablename__" in line for line in block)
        has_table_args = any("__table_args__" in line for line in block)
        inserted = False
        for line in block:
            patched_lines.append(line)
            if has_tablename and not has_table_args and "__tablename__" in line and not inserted:
                indent = re.match(r"^(\s*)", line).group(1) or "    "
                patched_lines.append(f'{indent}__table_args__ = {{"extend_existing": True}}')
                inserted = True

    result = "\n".join(patched_lines).strip("\n")
    return f"{result}\n" if result else ""


def _repair_backend_source_file(file_path: Path, log_text: str) -> bool:
    if not file_path.exists() or file_path.suffix != ".py":
        return False

    original = file_path.read_text(encoding="utf-8")

    if file_path.name == "models.py" and (
        "IndentationError" in log_text or "already defined for this MetaData instance" in log_text
    ):
        repaired = _patch_sqlalchemy_extend_existing(original)
    elif file_path.name == "main.py" and (
        "SyntaxError" in log_text or "ModuleNotFoundError" in log_text or "ImportError" in log_text
    ):
        repaired = _patch_backend_main_file(original)
    else:
        repaired = _strip_code_fences(original)

    if repaired and repaired != original:
        file_path.write_text(repaired, encoding="utf-8")
        return True
    return False


def _tail_log(log_path: Path, max_lines: int = 80) -> str:
    if not log_path.exists():
        return ""
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max_lines:]).strip()


def _try_repair_backend_from_log(backend_dir: Path, log_path: Path) -> tuple[bool, str]:
    log_text = _tail_log(log_path)
    matches = re.findall(r'File "([^"]+)", line \d+', log_text)
    for match in reversed(matches):
        candidate = Path(match)
        try:
            candidate.relative_to(backend_dir)
        except ValueError:
            continue
        if _repair_backend_source_file(candidate, log_text):
            return True, f"Repaired malformed generated backend file: {candidate.name}"
    return False, log_text


def _build_frontend_runtime_files(
    project_name: str,
    generated_files: list[dict[str, Any]],
    dependencies: dict[str, Any],
    frontend_port: int,
    backend_port: int,
) -> list[dict[str, Any]]:
    react_version = str(dependencies.get("react") or "^18.3.1")
    router_version = str(dependencies.get("react-router-dom") or "^6.30.1")
    tailwind_version = str(dependencies.get("tailwindcss") or "^3.4.17")

    runtime_dependencies = {
        "react": react_version,
        "react-dom": react_version,
        "react-router-dom": router_version,
    }

    for name, version in dependencies.items():
        if name == "tailwindcss":
            continue
        runtime_dependencies[name] = str(version or "*")

    scaffold_files = [
        {
            "path": "package.json",
            "language": "json",
            "content": json.dumps(
                {
                    "name": f"{_project_slug(project_name, 'ai-erp-builder')}-frontend",
                    "private": True,
                    "version": "0.1.0",
                    "type": "module",
                    "scripts": {
                        "dev": "vite",
                        "build": "vite build",
                        "preview": "vite preview",
                    },
                    "dependencies": runtime_dependencies,
                    "devDependencies": {
                        "@vitejs/plugin-react": "^4.3.1",
                        "autoprefixer": "^10.4.20",
                        "postcss": "^8.4.49",
                        "tailwindcss": tailwind_version,
                        "vite": "^5.4.8",
                    },
                },
                indent=2,
            ),
        },
        {
            "path": "index.html",
            "language": "html",
            "content": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_name or "AI ERP Builder"}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>""",
        },
        {
            "path": "vite.config.js",
            "language": "js",
            "content": f"""import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({{
  plugins: [react()],
  server: {{
    host: "127.0.0.1",
    port: {frontend_port},
    strictPort: true,
    proxy: {{
      "/api": "http://127.0.0.1:{backend_port}",
    }},
  }},
}});""",
        },
        {
            "path": "postcss.config.js",
            "language": "js",
            "content": """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};""",
        },
        {
            "path": "tailwind.config.js",
            "language": "js",
            "content": """export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};""",
        },
        {
            "path": "src/main.jsx",
            "language": "jsx",
            "content": """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);""",
        },
        {
            "path": "src/index.css",
            "language": "css",
            "content": """@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background: #f8fafc;
  color: #0f172a;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}""",
        },
    ]

    return _merge_files(scaffold_files, generated_files)


def _build_backend_runtime_files(
    project_name: str,
    generated_files: list[dict[str, Any]],
    dependencies: dict[str, Any],
) -> list[dict[str, Any]]:
    dependency_lines = []
    seen: set[str] = set()

    for name, version in dependencies.items():
        line = f"{name}{version or ''}"
        if name not in seen:
            dependency_lines.append(line)
            seen.add(name)

    for line in [
        "uvicorn[standard]>=0.30.0",
        "sqlalchemy>=2.0.0",
        "fastapi>=0.110.0",
        "pydantic>=2.0.0",
    ]:
        package_name = line.split(">=")[0].split("[")[0]
        if package_name not in seen:
            dependency_lines.append(line)
            seen.add(package_name)

    scaffold_files = [
        {
            "path": "requirements.txt",
            "language": "text",
            "content": "".join(f"{line}\n" for line in dependency_lines),
        },
        {
            "path": "README.md",
            "language": "markdown",
            "content": f"""# {project_name or "AI ERP Builder"} Backend

## Run
1. python -m venv .venv
2. .venv\\Scripts\\activate
3. pip install -r requirements.txt
4. uvicorn main:app --host 127.0.0.1 --port 8100
""",
        },
        {
            "path": ".gitignore",
            "language": "text",
            "content": "__pycache__/\n*.pyc\n.venv/\n.env\n",
        },
    ]

    merged_files = _normalize_python_package_files(_merge_files(scaffold_files, generated_files))
    patched_files = []
    for entry in merged_files:
        if entry["path"] == "database.py":
            patched_files.append({**entry, "content": _patch_backend_database_file(entry["content"])})
        elif entry["path"] == "auth.py":
            patched_files.append({**entry, "content": _patch_backend_auth_file(entry["content"])})
        elif entry["path"] == "main.py":
            patched_files.append({**entry, "content": _patch_backend_main_file(entry["content"])})
        elif entry["path"].endswith("models.py"):
            patched_files.append({**entry, "content": _patch_sqlalchemy_extend_existing(entry["content"])})
        elif entry["path"].endswith(".py"):
            patched_files.append({**entry, "content": _strip_code_fences(entry["content"])})
        else:
            patched_files.append(entry)
    return patched_files


def _find_latest_complete_job(db: Session, project: Project) -> GenerationJob:
    job = (
        db.query(GenerationJob)
        .filter(GenerationJob.project_id == project.id, GenerationJob.status == "complete")
        .order_by(GenerationJob.completed_at.desc(), GenerationJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The generated code is not ready yet. Finish the ERP generation pipeline before running it locally.",
        )
    return job


def _artifacts_by_type(db: Session, job_id: str) -> dict[str, list[GeneratedArtifact]]:
    artifacts = (
        db.query(GeneratedArtifact)
        .filter(GeneratedArtifact.generation_job_id == job_id)
        .order_by(GeneratedArtifact.file_path.asc())
        .all()
    )
    grouped: dict[str, list[GeneratedArtifact]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.artifact_type, []).append(artifact)
    return grouped


def _preferred_ports(project_id: str) -> tuple[int, int]:
    digest = int(_sha1(project_id)[:8], 16)
    return 3100 + (digest % 300), 8100 + (digest % 300)


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _allocate_port(preferred: int, lower: int, upper: int) -> int:
    if _port_free(preferred):
        return preferred
    for candidate in range(lower, upper + 1):
        if _port_free(candidate):
            return candidate
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No free localhost ports are available.")


def _state_file(workspace_root: Path) -> Path:
    return workspace_root / "runner-state.json"


def _load_state(workspace_root: Path) -> dict[str, Any]:
    path = _state_file(workspace_root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(workspace_root: Path, state: dict[str, Any]) -> None:
    _state_file(workspace_root).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _stop_process_tree(pid: int | None) -> None:
    if not pid:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _reset_runtime_directory(path: Path, preserve_names: set[str]) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.name in preserve_names:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass


def _remove_shadowing_package_modules(base_path: Path, files: list[dict[str, Any]]) -> None:
    desired_paths = {
        str(entry.get("path") or "").strip().replace("\\", "/")
        for entry in files
        if str(entry.get("path") or "").strip()
    }
    package_dirs = {
        str(Path(path).parent).replace("\\", "/")
        for path in desired_paths
        if path.endswith("/__init__.py")
    }
    for package_dir in package_dirs:
        module_path = base_path / Path(f"{package_dir}.py")
        if module_path.exists() and f"{package_dir}.py" not in desired_paths:
            try:
                module_path.unlink()
            except FileNotFoundError:
                pass


def _url_ready(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except urllib.error.HTTPError as exc:
        return 100 <= exc.code < 600
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _wait_for_url(url: str, timeout_seconds: int, failure_detail: str) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _url_ready(url):
            return
        time.sleep(1)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=failure_detail)


def _write_files(base_path: Path, files: list[dict[str, Any]]) -> None:
    for entry in files:
        target = base_path / Path(entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(entry["content"]), encoding="utf-8")


def _npm_command() -> str:
    for candidate in [shutil.which("npm"), shutil.which("npm.cmd"), r"C:\Program Files\nodejs\npm.cmd"]:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Node.js npm was not found on this machine. Install Node.js before using Run Locally.",
    )


def _ensure_frontend_dependencies(frontend_dir: Path) -> None:
    package_json_path = frontend_dir / "package.json"
    expected_hash = _sha1(package_json_path.read_text(encoding="utf-8"))
    marker = frontend_dir / ".runtime-install.hash"
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists() and marker.exists() and marker.read_text(encoding="utf-8") == expected_hash:
        return

    npm_cmd = _npm_command()
    log_path = frontend_dir / "install.log"
    with log_path.open("ab") as log_file:
        subprocess.run(
            [npm_cmd, "install", "--no-fund", "--no-audit"],
            cwd=frontend_dir,
            check=True,
            stdout=log_file,
            stderr=log_file,
        )
    marker.write_text(expected_hash, encoding="utf-8")


def _ensure_backend_environment(backend_dir: Path) -> Path:
    requirements_path = backend_dir / "requirements.txt"
    expected_hash = _sha1(requirements_path.read_text(encoding="utf-8"))
    marker = backend_dir / ".runtime-install.hash"
    venv_python = backend_dir / ".venv" / "Scripts" / "python.exe"

    if venv_python.exists() and marker.exists() and marker.read_text(encoding="utf-8") == expected_hash:
        return venv_python

    subprocess.run([sys.executable, "-m", "venv", ".venv"], cwd=backend_dir, check=True)
    log_path = backend_dir / "install.log"
    with log_path.open("ab") as log_file:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=backend_dir,
            check=True,
            stdout=log_file,
            stderr=log_file,
        )
    marker.write_text(expected_hash, encoding="utf-8")
    return venv_python


def _start_process(command: list[str], cwd: Path, log_path: Path) -> int:
    cwd.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=log_handle,
            stderr=log_handle,
            stdin=subprocess.DEVNULL,
            creationflags=WINDOWS_CREATION_FLAGS,
        )
    finally:
        log_handle.close()
    return process.pid


def _ensure_backend_running(backend_dir: Path, logs_dir: Path, backend_url: str, backend_port: int) -> int | None:
    if _url_ready(f"{backend_url}/"):
        return None

    venv_python = _ensure_backend_environment(backend_dir)
    log_path = logs_dir / "backend.log"
    attempts = 0
    repair_messages: list[str] = []
    last_log_excerpt = ""

    while attempts < 3:
        log_path.write_text("", encoding="utf-8")
        backend_pid = _start_process(
            [str(venv_python), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
            backend_dir,
            log_path,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if _url_ready(f"{backend_url}/"):
                return backend_pid
            time.sleep(1)

        repaired, detail = _try_repair_backend_from_log(backend_dir, log_path)
        last_log_excerpt = detail
        if not repaired:
            break
        repair_messages.append(detail)
        attempts += 1

    detail_parts = ["The generated backend did not start successfully on localhost."]
    if repair_messages:
        detail_parts.extend(repair_messages)
    if last_log_excerpt:
        detail_parts.append(last_log_excerpt)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="\n\n".join(detail_parts))


def _resolve_runtime_ports(project: Project, workspace_root: Path) -> tuple[int, int]:
    state = _load_state(workspace_root)
    saved_frontend = int(state.get("frontend_port") or 0)
    saved_backend = int(state.get("backend_port") or 0)
    if saved_frontend and saved_backend:
        return saved_frontend, saved_backend

    preferred_frontend, preferred_backend = _preferred_ports(project.id)
    frontend_port = _allocate_port(preferred_frontend, 3100, 3499)
    backend_port = _allocate_port(preferred_backend, 8100, 8499)
    return frontend_port, backend_port


def _build_runtime_bundle(db: Session, project: Project, frontend_port: int, backend_port: int) -> dict[str, Any]:
    job = _find_latest_complete_job(db, project)
    grouped = _artifacts_by_type(db, job.id)
    frontend_artifacts = grouped.get("frontend", [])
    backend_artifacts = grouped.get("backend", [])
    spec_artifacts = grouped.get("spec", [])

    if not frontend_artifacts or not backend_artifacts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project does not have both frontend and backend artifacts yet.",
        )

    frontend_files = [
        {"path": artifact.file_path, "language": artifact.language, "content": artifact.content_text}
        for artifact in frontend_artifacts
    ]
    backend_files = [
        {"path": artifact.file_path, "language": artifact.language, "content": artifact.content_text}
        for artifact in backend_artifacts
    ]
    spec_files = [
        {"path": artifact.file_path, "language": artifact.language, "content": artifact.content_text}
        for artifact in spec_artifacts
    ]

    frontend_dependencies = dict(frontend_artifacts[0].metadata_json.get("dependencies") or {})
    backend_dependencies = dict(backend_artifacts[0].metadata_json.get("dependencies") or {})

    return {
        "frontend_files": _build_frontend_runtime_files(
            project.name,
            frontend_files,
            frontend_dependencies,
            frontend_port,
            backend_port,
        ),
        "backend_files": _build_backend_runtime_files(project.name, backend_files, backend_dependencies),
        "spec_files": spec_files,
        "job_id": job.id,
    }


def start_project_locally(db: Session, project: Project) -> dict[str, Any]:
    workspace_root = RUNTIME_ROOT / project.id
    frontend_dir = workspace_root / "frontend"
    backend_dir = workspace_root / "backend"
    spec_dir = workspace_root / "spec"
    logs_dir = workspace_root / "logs"
    workspace_root.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(workspace_root)

    frontend_port, backend_port = _resolve_runtime_ports(project, workspace_root)
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    backend_url = f"http://127.0.0.1:{backend_port}"

    bundle = _build_runtime_bundle(db, project, frontend_port, backend_port)
    job_changed = str(state.get("job_id") or "") != bundle["job_id"]
    if job_changed:
        _stop_process_tree(int(state.get("frontend_pid") or 0))
        _stop_process_tree(int(state.get("backend_pid") or 0))
        _reset_runtime_directory(frontend_dir, {"node_modules", ".runtime-install.hash", "install.log"})
        _reset_runtime_directory(
            backend_dir,
            {".venv", ".runtime-install.hash", "install.log", "generated_app.db", "__pycache__"},
        )
        _reset_runtime_directory(spec_dir, set())
        time.sleep(2)
    _remove_shadowing_package_modules(frontend_dir, bundle["frontend_files"])
    _remove_shadowing_package_modules(backend_dir, bundle["backend_files"])
    _write_files(frontend_dir, bundle["frontend_files"])
    _write_files(backend_dir, bundle["backend_files"])
    _write_files(spec_dir, bundle["spec_files"])

    backend_pid = _ensure_backend_running(backend_dir, logs_dir, backend_url, backend_port)

    if not _url_ready(frontend_url):
        _ensure_frontend_dependencies(frontend_dir)
        frontend_pid = _start_process(
            [_npm_command(), "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            frontend_dir,
            logs_dir / "frontend.log",
        )
    else:
        frontend_pid = None

    _wait_for_url(
        frontend_url,
        timeout_seconds=120,
        failure_detail="The generated frontend did not start successfully on localhost.",
    )

    state = {
        "project_id": project.id,
        "job_id": bundle["job_id"],
        "workspace_path": str(workspace_root),
        "frontend_port": frontend_port,
        "backend_port": backend_port,
        "frontend_url": frontend_url,
        "backend_url": backend_url,
        "frontend_pid": frontend_pid or state.get("frontend_pid"),
        "backend_pid": backend_pid or state.get("backend_pid"),
        "updated_at": time.time(),
    }
    _save_state(workspace_root, state)
    return {
        "project_id": project.id,
        "status": "ready",
        "message": "Generated ERP app is running locally.",
        "workspace_path": str(workspace_root),
        "frontend_url": frontend_url,
        "backend_url": backend_url,
        "frontend_port": frontend_port,
        "backend_port": backend_port,
    }
