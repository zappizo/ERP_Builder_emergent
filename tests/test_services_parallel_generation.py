import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import services
from backend.app.template_loader import attach_erp_ui_template_metadata


def test_generate_code_bundles_runs_generators_in_parallel(monkeypatch):
    async def fake_frontend(master_json, markdown_spec):
        await asyncio.sleep(0.2)
        return {"files": [{"path": "src/App.jsx", "language": "jsx", "content": "export default function App() {}"}]}

    async def fake_backend(master_json, markdown_spec):
        await asyncio.sleep(0.2)
        return {"files": [{"path": "main.py", "language": "python", "content": "app = None"}]}

    monkeypatch.setattr(services, "frontend_generator", fake_frontend)
    monkeypatch.setattr(services, "backend_generator", fake_backend)

    start = time.perf_counter()
    frontend_bundle, backend_bundle = asyncio.run(services.generate_code_bundles({"modules": []}, "# spec"))
    elapsed = time.perf_counter() - start

    assert elapsed < 0.4
    assert frontend_bundle["files"][0]["path"] == "src/App.jsx"
    assert backend_bundle["files"][0]["path"] == "main.py"


def test_generate_code_bundles_surfaces_generation_failures(monkeypatch):
    async def fake_frontend(master_json, markdown_spec):
        raise RuntimeError("frontend timeout")

    async def fake_backend(master_json, markdown_spec):
        return {"files": [{"path": "main.py", "language": "python", "content": "app = None"}]}

    monkeypatch.setattr(services, "frontend_generator", fake_frontend)
    monkeypatch.setattr(services, "backend_generator", fake_backend)

    with pytest.raises(RuntimeError, match="Frontend generation failed"):
        asyncio.run(services.generate_code_bundles({"modules": []}, "# spec"))


def test_generate_code_bundles_merges_revision_output_with_existing_files(monkeypatch):
    async def fake_frontend(master_json, markdown_spec, existing_bundle=None, change_request=None):
        return {
            "files": [
                {"path": "src/App.jsx", "language": "jsx", "content": "export default function App() { return 'updated'; }"},
            ],
            "dependencies": {"react": "^18.0.0", "lucide-react": "^0.507.0"},
        }

    async def fake_backend(master_json, markdown_spec, existing_bundle=None, change_request=None):
        return {
            "files": [
                {"path": "routes.py", "language": "python", "content": "router = 'updated'"},
            ],
            "dependencies": {"fastapi": ">=0.100.0"},
        }

    monkeypatch.setattr(services, "frontend_generator", fake_frontend)
    monkeypatch.setattr(services, "backend_generator", fake_backend)

    frontend_bundle, backend_bundle = asyncio.run(
        services.generate_code_bundles(
            {"modules": []},
            "# spec",
            existing_frontend_bundle={
                "files": [
                    {"path": "src/App.jsx", "language": "jsx", "content": "export default function App() { return 'old'; }"},
                    {"path": "src/pages/Dashboard.jsx", "language": "jsx", "content": "export default function Dashboard() {}"},
                ],
                "dependencies": {"react-router-dom": "^6.0.0"},
            },
            existing_backend_bundle={
                "files": [
                    {"path": "main.py", "language": "python", "content": "app = 'old'"},
                    {"path": "routes.py", "language": "python", "content": "router = 'old'"},
                ],
                "dependencies": {"sqlalchemy": ">=2.0.0"},
            },
            change_request="Add a KPI widget",
        )
    )

    frontend_files = {file["path"]: file["content"] for file in frontend_bundle["files"]}
    backend_files = {file["path"]: file["content"] for file in backend_bundle["files"]}

    assert frontend_files["src/App.jsx"] == "export default function App() { return 'updated'; }"
    assert "src/pages/Dashboard.jsx" in frontend_files
    assert frontend_bundle["dependencies"]["react-router-dom"] == "^6.0.0"
    assert frontend_bundle["dependencies"]["lucide-react"] == "^0.507.0"
    assert backend_files["routes.py"] == "router = 'updated'"
    assert "main.py" in backend_files
    assert backend_bundle["dependencies"]["sqlalchemy"] == ">=2.0.0"


def test_generate_code_bundles_retries_noop_revision_until_code_changes(monkeypatch):
    frontend_calls = {"count": 0}

    async def fake_frontend(master_json, markdown_spec, existing_bundle=None, change_request=None):
        frontend_calls["count"] += 1
        if frontend_calls["count"] == 1:
            return {
                "files": [
                    {"path": "src/App.jsx", "language": "jsx", "content": "export default function App() { return 'old'; }"},
                ],
                "dependencies": {"react": "^18.0.0"},
            }
        return {
            "files": [
                {"path": "src/App.jsx", "language": "jsx", "content": "export default function App() { return 'updated'; }"},
            ],
            "dependencies": {"react": "^18.0.0"},
        }

    async def fake_backend(master_json, markdown_spec, existing_bundle=None, change_request=None):
        return {
            "files": [
                {"path": "main.py", "language": "python", "content": "app = 'old'"},
            ],
            "dependencies": {"fastapi": ">=0.100.0"},
        }

    monkeypatch.setattr(services, "frontend_generator", fake_frontend)
    monkeypatch.setattr(services, "backend_generator", fake_backend)

    frontend_bundle, backend_bundle = asyncio.run(
        services.generate_code_bundles(
            {"modules": []},
            "# spec",
            existing_frontend_bundle={
                "files": [{"path": "src/App.jsx", "language": "jsx", "content": "export default function App() { return 'old'; }"}],
                "dependencies": {"react": "^18.0.0"},
            },
            existing_backend_bundle={
                "files": [{"path": "main.py", "language": "python", "content": "app = 'old'"}],
                "dependencies": {"fastapi": ">=0.100.0"},
            },
            change_request="Add a revision banner",
        )
    )

    frontend_files = {file["path"]: file["content"] for file in frontend_bundle["files"]}
    backend_files = {file["path"]: file["content"] for file in backend_bundle["files"]}

    assert frontend_calls["count"] == 2
    assert frontend_files["src/App.jsx"] == "export default function App() { return 'updated'; }"
    assert backend_files["main.py"] == "app = 'old'"


def test_generate_code_bundles_raises_when_revision_makes_no_code_changes(monkeypatch):
    async def fake_frontend(master_json, markdown_spec, existing_bundle=None, change_request=None):
        return {
            "files": [{"path": "src/App.jsx", "language": "jsx", "content": "same"}],
            "dependencies": {"react": "^18.0.0"},
        }

    async def fake_backend(master_json, markdown_spec, existing_bundle=None, change_request=None):
        return {
            "files": [{"path": "main.py", "language": "python", "content": "same"}],
            "dependencies": {"fastapi": ">=0.100.0"},
        }

    monkeypatch.setattr(services, "frontend_generator", fake_frontend)
    monkeypatch.setattr(services, "backend_generator", fake_backend)

    with pytest.raises(RuntimeError, match="without changing either the frontend or backend generated code"):
        asyncio.run(
            services.generate_code_bundles(
                {"modules": []},
                "# spec",
                existing_frontend_bundle={
                    "files": [{"path": "src/App.jsx", "language": "jsx", "content": "same"}],
                    "dependencies": {"react": "^18.0.0"},
                },
                existing_backend_bundle={
                    "files": [{"path": "main.py", "language": "python", "content": "same"}],
                    "dependencies": {"fastapi": ">=0.100.0"},
                },
                change_request="Add a revision banner",
            )
        )


def test_invoke_markdown_blueprint_generator_passes_revision_context_when_supported():
    captured = {}

    async def fake_markdown_generator(
        project_name,
        conversation_transcript,
        requirements,
        architecture,
        master_json,
        existing_markdown=None,
        change_request=None,
    ):
        captured["project_name"] = project_name
        captured["conversation_transcript"] = conversation_transcript
        captured["existing_markdown"] = existing_markdown
        captured["change_request"] = change_request
        return "# Updated Guide"

    result = asyncio.run(
        services._invoke_markdown_blueprint_generator(
            fake_markdown_generator,
            "ERP",
            "chat transcript",
            {"business_type": "manufacturing"},
            {"system_name": "ERP"},
            {"version": "1.0.0"},
            existing_markdown="# Existing Guide",
            change_request="Add procurement approval flow",
        )
    )

    assert result == "# Updated Guide"
    assert captured["project_name"] == "ERP"
    assert captured["conversation_transcript"] == "chat transcript"
    assert captured["existing_markdown"] == "# Existing Guide"
    assert captured["change_request"] == "Add procurement approval flow"


def test_invoke_markdown_blueprint_generator_passes_template_reference_when_supported():
    captured = {}

    async def fake_markdown_generator(
        project_name,
        conversation_transcript,
        requirements,
        architecture,
        master_json,
        existing_markdown=None,
        change_request=None,
        template_reference=None,
    ):
        captured["template_reference"] = template_reference
        return "# Updated Guide"

    template_reference = {"name": "Template 1", "status": "ready"}
    result = asyncio.run(
        services._invoke_markdown_blueprint_generator(
            fake_markdown_generator,
            "ERP",
            "chat transcript",
            {"business_type": "manufacturing"},
            {"system_name": "ERP"},
            {"version": "1.0.0"},
            template_reference=template_reference,
        )
    )

    assert result == "# Updated Guide"
    assert captured["template_reference"] == template_reference


def test_invoke_code_generator_passes_template_reference_when_supported():
    captured = {}

    async def fake_frontend_generator(master_json, markdown_spec, template_reference=None):
        captured["template_reference"] = template_reference
        return {"files": [{"path": "src/App.jsx", "language": "jsx", "content": "export default function App() {}"}]}

    template_reference = {"name": "Template 1", "status": "ready"}
    result = asyncio.run(
        services._invoke_code_generator(
            fake_frontend_generator,
            {"version": "1.0.0"},
            "# spec",
            template_reference=template_reference,
        )
    )

    assert result["files"][0]["path"] == "src/App.jsx"
    assert captured["template_reference"] == template_reference


def test_attach_erp_ui_template_metadata_records_usage_directive():
    enriched = attach_erp_ui_template_metadata(
        {"version": "1.0.0", "system": {"name": "ERP"}},
        {
            "name": "Template 1",
            "status": "ready",
            "relative_directory": "Template/Template 1",
            "json_relative_path": "Template/Template 1/Json1.json",
            "markdown_relative_path": "Template/Template 1/Md1.md",
            "has_json_content": True,
            "has_markdown_content": True,
            "has_actionable_content": True,
            "json_sha256": "json-hash",
            "markdown_sha256": "md-hash",
            "summary": "A shared ERP shell",
            "design_cues": {"layout": {"navigation": "sidebar"}},
            "warnings": [],
        },
    )

    template_metadata = enriched["documentation"]["erp_ui_template"]
    assert template_metadata["name"] == "Template 1"
    assert template_metadata["design_cues"]["layout"]["navigation"] == "sidebar"
    assert "Do not use it to restyle the AI ERP Builder product UI" in template_metadata["usage_directive"]


def test_reset_generation_stages_can_preserve_existing_outputs_for_revisions():
    class DummyProject:
        pipeline_state = {
            "requirement_analysis": {"status": "complete", "output": {"a": 1}, "updated_at": None},
            "requirement_gathering": {"status": "complete", "output": {"b": 1}, "updated_at": None},
            "architecture": {"status": "complete", "output": {"system_name": "ERP"}, "updated_at": None},
            "json_transform": {"status": "complete", "output": {"version": "1.0.0"}, "updated_at": None},
            "frontend_generation": {"status": "complete", "output": {"files": [{"path": "src/App.jsx"}]}, "updated_at": None},
            "backend_generation": {"status": "complete", "output": {"files": [{"path": "main.py"}]}, "updated_at": None},
            "code_review": {"status": "complete", "output": {"overall_score": 8.5}, "updated_at": None},
        }

    project = DummyProject()

    services.reset_generation_stages(project, preserve_existing_outputs=True)

    assert project.pipeline_state["architecture"]["status"] == "complete"
    assert project.pipeline_state["architecture"]["output"]["system_name"] == "ERP"
    assert project.pipeline_state["json_transform"]["output"]["version"] == "1.0.0"
    assert project.pipeline_state["frontend_generation"]["output"]["files"][0]["path"] == "src/App.jsx"


def test_hydrate_pipeline_outputs_from_current_version_backfills_missing_stage_outputs():
    class FakeQuery:
        def __init__(self, payload):
            self.payload = payload

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return self.payload

        def all(self):
            return list(self.payload)

    class FakeSession:
        def __init__(self, project_version, artifacts):
            self.project_version = project_version
            self.artifacts = artifacts

        def query(self, model):
            if model is services.ProjectVersion:
                return FakeQuery(self.project_version)
            if model is services.GeneratedArtifact:
                return FakeQuery(self.artifacts)
            raise AssertionError(f"Unexpected model queried: {model}")

    project = SimpleNamespace(
        id="project-1",
        status="COMPLETE",
        current_project_version_id="version-1",
        pipeline_state=services.default_pipeline_state(),
    )
    project_version = SimpleNamespace(
        id="version-1",
        generation_job_id="job-1",
        snapshot_json={
            "architecture": {"system_name": "ERP"},
            "master_json": {"version": "1.0.0", "documentation": {}},
            "build_markdown": "# Existing build",
            "review": {"overall_score": 8.9},
        },
    )
    artifacts = [
        SimpleNamespace(
            artifact_type="frontend",
            file_path="src/App.jsx",
            language="jsx",
            content_text="export default function App() {}",
            metadata_json={"dependencies": {"react": "^18.0.0"}},
        ),
        SimpleNamespace(
            artifact_type="backend",
            file_path="main.py",
            language="python",
            content_text="app = FastAPI()",
            metadata_json={"dependencies": {"fastapi": ">=0.100.0"}},
        ),
    ]

    services.hydrate_pipeline_outputs_from_current_version(FakeSession(project_version, artifacts), project)

    assert project.pipeline_state["architecture"]["status"] == "complete"
    assert project.pipeline_state["architecture"]["output"]["system_name"] == "ERP"
    assert project.pipeline_state["json_transform"]["status"] == "complete"
    assert project.pipeline_state["json_transform"]["output"]["documentation"]["erp_build_markdown"] == "# Existing build"
    assert project.pipeline_state["frontend_generation"]["status"] == "complete"
    assert project.pipeline_state["frontend_generation"]["output"]["files"][0]["path"] == "src/App.jsx"
    assert project.pipeline_state["backend_generation"]["status"] == "complete"
    assert project.pipeline_state["backend_generation"]["output"]["files"][0]["path"] == "main.py"
    assert project.pipeline_state["code_review"]["status"] == "complete"
    assert project.pipeline_state["code_review"]["output"]["overall_score"] == 8.9
