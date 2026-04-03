import sys
from pathlib import Path
import asyncio


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agents
from backend.app.template_frontend_bundle import build_template_driven_frontend_bundle


def test_template_driven_frontend_file_bundle_uses_template_profile():
    master_json = {
        "system": {"name": "Template Driven ERP", "description": "Operational workspace"},
        "modules": [
            {
                "id": "sales",
                "name": "Sales",
                "icon": "shopping-bag",
                "entities": [{"name": "Order", "fields": [{"name": "id"}, {"name": "status"}, {"name": "customer"}]}],
                "workflows": [{"name": "Quote to cash", "steps": ["Quote", "Approve", "Invoice"]}],
                "endpoints": [{"method": "GET", "path": "/api/sales/orders", "description": "List orders"}],
            }
        ],
        "documentation": {
            "erp_ui_template": {
                "name": "Template 1",
                "status": "ready",
                "summary": "A compact command-center layout for operations teams.",
            }
        },
    }
    template_reference = {
        "name": "Template 1",
        "status": "ready",
        "summary": "A compact command-center layout for operations teams.",
        "json_data": {
            "theme": {
                "palette": {
                    "primary": "#123456",
                    "secondary": "#654321",
                    "background": "#f7f6f2",
                    "surface": "#ffffff",
                    "text": {"primary": "#0f172a", "secondary": "#475569"},
                    "border": "#dbe4f0",
                }
            },
            "components": {"sidebar": {"width": "260px"}},
            "layout": {"navigation": "topbar", "density": "compact"},
            "branding": {"kicker": "Operations cockpit", "hero_title": "Command the workflow"},
            "typography": {"heading": "'Fraunces', serif", "body": "'Manrope', sans-serif"},
        },
    }

    bundle = build_template_driven_frontend_bundle(master_json, template_reference=template_reference)
    file_map = {item["path"]: item["content"] for item in bundle["files"]}

    assert "src/styles/template.css" in file_map
    assert 'import "./styles/template.css";' in file_map["src/App.jsx"]
    assert '"layout_mode": "topbar"' in file_map["src/data/schema.js"]
    assert '"sidebar_width": "260px"' in file_map["src/data/schema.js"]
    assert "Command the workflow" in file_map["src/data/schema.js"]
    assert "#123456" in file_map["src/styles/template.css"]
    assert "useLocation" in file_map["src/components/Layout.jsx"]
    assert "ModuleWorkspace" in file_map["src/App.jsx"]
    assert "src/pages/ModuleWorkspace.jsx" in file_map
    assert "src/lib/api.js" in file_map
    assert "Login to Preview" in file_map["src/components/AuthScreen.jsx"]
    assert "/api/modules/" in file_map["src/lib/api.js"]


def test_frontend_generator_uses_template_bundle_when_template_is_actionable():
    master_json = {
        "system": {"name": "ERP", "description": "Desc"},
        "modules": [{"id": "sales", "name": "Sales", "entities": [{"name": "Order", "fields": [{"name": "id"}]}], "workflows": [], "endpoints": []}],
        "documentation": {"erp_ui_template": {"name": "Template 1", "summary": "Summary", "status": "ready"}},
    }
    template_reference = {
        "name": "Template 1",
        "status": "ready",
        "summary": "Summary",
        "has_actionable_content": True,
        "json_data": {
            "layout": {"navigation": "topbar"},
            "theme": {"palette": {"primary": "#123456", "secondary": "#654321", "text": {"primary": "#ffffff"}}},
        },
    }

    bundle = asyncio.run(agents.frontend_generator(master_json, "# guide", template_reference=template_reference))
    file_map = {item["path"]: item["content"] for item in bundle["files"]}

    assert "src/styles/template.css" in file_map
    assert "#123456" in file_map["src/styles/template.css"]
    assert "ModuleWorkspace" in file_map["src/App.jsx"]
    assert "src/lib/api.js" in file_map
    assert "generated-erp-session" in file_map["src/lib/api.js"]


def test_backend_fallback_bundle_uses_routes_package_init():
    master_json = {
        "system": {"name": "ERP", "description": "Desc"},
        "modules": [
            {
                "id": "sales",
                "name": "Sales",
                "entities": [{"name": "Order", "fields": [{"name": "id", "primary": True}, {"name": "status"}]}],
            }
        ],
    }

    bundle = agents._backend_file_bundle(master_json)
    file_map = {item["path"]: item["content"] for item in bundle["files"]}

    assert "routes/__init__.py" in file_map
    assert "routes/auth.py" in file_map
    assert "routes/modules.py" in file_map
    assert "security.py" in file_map
    assert "routes.py" not in file_map
    assert "from routes.auth import router as auth_router" in file_map["main.py"]
    assert "/modules/{module_id}/records/{record_id}/actions" in file_map["routes/modules.py"]
    assert "x-user-id" in file_map["security.py"]
