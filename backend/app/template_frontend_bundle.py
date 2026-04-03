from __future__ import annotations

import json
import re
from textwrap import dedent
from typing import Any

from .functional_frontend_bundle import build_functional_template_frontend_bundle


def _lookup(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = payload
        matched = True
        for part in path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                matched = False
                break
        if matched and current not in (None, "", [], {}):
            return current
    return None


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _slugify(value: Any, fallback: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return candidate or fallback


def _normalize_modules(master_json: dict[str, Any]) -> list[dict[str, Any]]:
    raw_modules = master_json.get("modules", [])
    modules: list[dict[str, Any]] = []

    if not isinstance(raw_modules, list):
        raw_modules = []

    for index, module in enumerate(raw_modules, start=1):
        if not isinstance(module, dict):
            continue

        name = str(module.get("name") or module.get("id") or f"Module {index}")
        raw_id = str(module.get("id") or name)
        module_id = raw_id or _slugify(name, f"module-{index}")
        route_path = _slugify(module.get("path") or raw_id or name, f"module-{index}")

        entities: list[dict[str, Any]] = []
        for entity in module.get("entities", []) or []:
            if isinstance(entity, dict):
                field_names = [
                    str(field.get("name") if isinstance(field, dict) else field)
                    for field in (entity.get("fields") or [])
                    if field not in (None, "", [], {})
                ][:6]
                entities.append(
                    {
                        "name": str(entity.get("name") or entity.get("id") or "Record"),
                        "fields": field_names,
                    }
                )
            elif entity not in (None, "", [], {}):
                entities.append({"name": str(entity), "fields": []})

        workflows: list[dict[str, Any]] = []
        for workflow in module.get("workflows", []) or []:
            if isinstance(workflow, dict):
                step_values = [
                    str(step.get("name") if isinstance(step, dict) else step)
                    for step in (workflow.get("steps") or [])
                    if step not in (None, "", [], {})
                ]
                workflows.append(
                    {
                        "name": str(workflow.get("name") or workflow.get("id") or "Workflow"),
                        "steps": step_values,
                    }
                )
            elif workflow not in (None, "", [], {}):
                workflows.append({"name": str(workflow), "steps": [str(workflow)]})

        endpoints: list[dict[str, Any]] = []
        for endpoint in module.get("endpoints", []) or []:
            if not isinstance(endpoint, dict):
                continue
            endpoints.append(
                {
                    "method": str(endpoint.get("method") or "GET"),
                    "path": str(endpoint.get("path") or f"/api/{route_path}"),
                    "description": str(endpoint.get("description") or name),
                }
            )

        modules.append(
            {
                "id": module_id,
                "path": route_path,
                "name": name,
                "icon": str(module.get("icon") or "package"),
                "summary": str(module.get("description") or f"{name} workspace"),
                "entities": entities,
                "workflows": workflows,
                "endpoints": endpoints[:8],
            }
        )

    if modules:
        return modules

    return [
        {
            "id": "operations",
            "path": "operations",
            "name": "Operations",
            "icon": "package",
            "summary": "Operational workspace",
            "entities": [{"name": "Record", "fields": ["id", "status", "owner"]}],
            "workflows": [{"name": "Review request", "steps": ["Capture", "Review", "Approve"]}],
            "endpoints": [{"method": "GET", "path": "/api/operations", "description": "Operations summary"}],
        }
    ]


def _normalize_profile(
    master_json: dict[str, Any],
    modules: list[dict[str, Any]],
    template_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    raw = template_reference.get("json_data") if isinstance(template_reference, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    metadata = dict((master_json.get("documentation") or {}).get("erp_ui_template") or {})

    palette = _first(
        _lookup(raw, ("theme", "palette")),
        _lookup(raw, ("theme", "colors")),
        _lookup(raw, ("colors",)),
        {},
    )
    palette = palette if isinstance(palette, dict) else {}
    text_palette = palette.get("text") if isinstance(palette.get("text"), dict) else {}
    spacing = _first(_lookup(raw, ("theme", "spacing")), _lookup(raw, ("spacing",)), {})
    spacing = spacing if isinstance(spacing, dict) else {}

    layout_mode = str(
        _first(
            _lookup(raw, ("layout", "navigation")),
            _lookup(raw, ("layout", "mode")),
            _lookup(raw, ("navigation", "type")),
            "sidebar",
        )
    ).lower()
    if layout_mode not in {"sidebar", "topbar"}:
        layout_mode = "sidebar"

    workflow_highlights = _lookup(raw, ("dashboard", "workflow_highlights"))
    if not isinstance(workflow_highlights, list) or not workflow_highlights:
        workflow_highlights = []
        for module in modules[:3]:
            for workflow in module.get("workflows", [])[:2]:
                workflow_highlights.append(workflow.get("name") or "Workflow")
        workflow_highlights = workflow_highlights[:5]

    total_entities = sum(len(module.get("entities", [])) for module in modules)
    total_workflows = sum(len(module.get("workflows", [])) for module in modules)
    total_endpoints = sum(len(module.get("endpoints", [])) for module in modules)
    primary_module = modules[0]

    kpi_statuses = []
    for item in _lookup(raw, ("components", "kpi_metrics")) or []:
        if isinstance(item, dict):
            kpi_statuses.append(str(item.get("status") or "neutral").lower())

    def _kpi_status(index: int, fallback: str) -> str:
        if index < len(kpi_statuses) and kpi_statuses[index] in {"positive", "negative", "neutral"}:
            return kpi_statuses[index]
        return fallback

    chart_config = _lookup(raw, ("components", "main_chart"))
    chart_config = chart_config if isinstance(chart_config, dict) else {}
    raw_series = chart_config.get("series") if isinstance(chart_config.get("series"), list) else []

    chart_modules = modules[: max(3, min(len(modules), 6))]
    chart_categories = [
        module.get("name", "Module").replace(" Management", "").replace(" & ", " / ")
        for module in chart_modules
    ]
    entity_series = [max(len(module.get("entities", [])), 1) for module in chart_modules]
    workflow_series = [max(len(module.get("workflows", [])), 1) for module in chart_modules]
    chart_max = max(entity_series + workflow_series + [1])

    def _series_name(index: int, fallback: str) -> str:
        if index < len(raw_series) and isinstance(raw_series[index], dict):
            return str(raw_series[index].get("name") or fallback)
        return fallback

    def _series_color(index: int, fallback: str) -> str:
        if index < len(raw_series) and isinstance(raw_series[index], dict):
            return str(raw_series[index].get("color") or fallback)
        return fallback

    activity_rows: list[dict[str, str]] = []
    for module in modules[:6]:
        focus = ", ".join(entity.get("name", "") for entity in module.get("entities", [])[:2]).strip(", ")
        activity_rows.append(
            {
                "workspace": module.get("name", "Workspace"),
                "focus": focus or module.get("summary", "Workspace ready"),
                "route": (module.get("endpoints") or [{"path": f"/{module.get('path', 'workspace')}"}])[0].get("path", "/"),
                "status": "Ready" if module.get("endpoints") else "Scaffold",
            }
        )

    return {
        "name": metadata.get("name") or (template_reference or {}).get("name") or "Template 1",
        "status": metadata.get("status") or (template_reference or {}).get("status") or "unknown",
        "summary": metadata.get("summary") or (template_reference or {}).get("summary") or "",
        "reference_project": str(_first(raw.get("project"), "Finance Analytics Dashboard")),
        "layout_mode": layout_mode,
        "density": str(_first(_lookup(raw, ("layout", "density")), "comfortable")).lower(),
        "hero_kicker": _first(_lookup(raw, ("branding", "kicker")), raw.get("project"), "ERP Control Room"),
        "hero_title": _first(
            _lookup(raw, ("branding", "hero_title")),
            _lookup(raw, ("dashboard", "hero_title")),
            f"{master_json.get('system', {}).get('name', 'ERP Platform')} Operations Dashboard",
        ),
        "hero_body": _first(
            _lookup(raw, ("branding", "hero_body")),
            _lookup(raw, ("dashboard", "hero_body")),
            master_json.get("system", {}).get("description"),
            metadata.get("summary"),
            "Operate the generated ERP from a template-driven shell that mirrors the saved design reference.",
        ),
        "primary_color": str(_first(palette.get("primary"), "#3B82F6")),
        "accent_color": str(_first(palette.get("secondary"), palette.get("accent"), "#A855F7")),
        "accent_cyan": str(_first(palette.get("accent_cyan"), "#06B6D4")),
        "background_color": str(_first(palette.get("background"), "#0B0E14")),
        "surface_color": str(_first(palette.get("surface"), "#161B22")),
        "text_color": str(_first(text_palette.get("primary"), palette.get("text"), "#FFFFFF")),
        "muted_color": str(_first(text_palette.get("secondary"), palette.get("muted"), "#8B949E")),
        "disabled_color": str(_first(text_palette.get("disabled"), "#484F58")),
        "border_color": str(_first(palette.get("border"), "#21262D")),
        "success_color": str(_first(palette.get("success"), "#10B981")),
        "danger_color": str(_first(palette.get("danger"), "#EF4444")),
        "font_heading": str(_first(_lookup(raw, ("typography", "heading")), "'Inter', 'Segoe UI', sans-serif")),
        "font_body": str(_first(_lookup(raw, ("typography", "body")), "'Inter', 'Segoe UI', sans-serif")),
        "container_padding": str(_first(spacing.get("container_padding"), "32px")),
        "card_gap": str(_first(spacing.get("card_gap"), "24px")),
        "border_radius": str(_first(spacing.get("border_radius"), "12px")),
        "sidebar_width": str(_first(_lookup(raw, ("components", "sidebar", "width")), "260px")),
        "sidebar_items": [
            str(item)
            for item in (_lookup(raw, ("components", "sidebar", "items")) or [])
            if item not in (None, "", [], {})
        ],
        "workflow_highlights": workflow_highlights,
        "kpi_metrics": [
            {
                "id": "modules",
                "label": "Active Modules",
                "value": f"{len(modules):02d}",
                "trend": f"{total_entities} tracked entities",
                "status": _kpi_status(0, "positive"),
            },
            {
                "id": "workflows",
                "label": "Workflow Coverage",
                "value": f"{total_workflows:02d}",
                "trend": f"{len(workflow_highlights)} highlighted flows",
                "status": _kpi_status(1, "positive"),
            },
            {
                "id": "api",
                "label": "API Surface",
                "value": f"{total_endpoints:02d}",
                "trend": f"{primary_module.get('name', 'Primary workspace')} is ready",
                "status": _kpi_status(2, "neutral"),
            },
        ],
        "chart": {
            "type": str(_first(chart_config.get("type"), "Area")),
            "categories": chart_categories,
            "max_value": chart_max,
            "series": [
                {
                    "name": _series_name(0, "Entities"),
                    "data": entity_series,
                    "color": _series_color(0, str(_first(palette.get("primary"), "#3B82F6"))),
                },
                {
                    "name": _series_name(1, "Workflows"),
                    "data": workflow_series,
                    "color": _series_color(1, str(_first(palette.get("secondary"), "#A855F7"))),
                },
            ],
        },
        "activity_rows": activity_rows,
    }


def build_template_driven_frontend_bundle(
    master_json: dict[str, Any],
    template_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    modules = _normalize_modules(master_json)
    profile = _normalize_profile(master_json, modules, template_reference)
    return build_functional_template_frontend_bundle(master_json, modules, profile)
    schema_payload = json.dumps(
        {
            "system": master_json.get("system", {}),
            "template": profile,
            "modules": modules,
        },
        indent=2,
    )

    app_jsx = dedent(
        """
        import "./styles/template.css";
        import { BrowserRouter, Routes, Route } from "react-router-dom";
        import Layout from "./components/Layout";
        import Dashboard from "./pages/Dashboard";
        import ModuleWorkspace from "./pages/ModuleWorkspace";

        export default function App() {
          return (
            <BrowserRouter>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/:moduleId" element={<ModuleWorkspace />} />
                </Routes>
              </Layout>
            </BrowserRouter>
          );
        }
        """
    ).strip()

    template_css = dedent(
        f"""
        :root {{
          --erp-primary: {profile["primary_color"]};
          --erp-accent: {profile["accent_color"]};
          --erp-accent-cyan: {profile["accent_cyan"]};
          --erp-background: {profile["background_color"]};
          --erp-surface: {profile["surface_color"]};
          --erp-text: {profile["text_color"]};
          --erp-muted: {profile["muted_color"]};
          --erp-disabled: {profile["disabled_color"]};
          --erp-border: {profile["border_color"]};
          --erp-success: {profile["success_color"]};
          --erp-danger: {profile["danger_color"]};
          --erp-font-heading: {profile["font_heading"]};
          --erp-font-body: {profile["font_body"]};
          --erp-shell-padding: {profile["container_padding"]};
          --erp-card-gap: {profile["card_gap"]};
          --erp-radius: {profile["border_radius"]};
          --erp-sidebar-width: {profile["sidebar_width"]};
          --erp-sidebar-compact-width: 88px;
        }}
        * {{
          box-sizing: border-box;
        }}
        html {{
          background: var(--erp-background);
        }}
        body {{
          margin: 0;
          color: var(--erp-text);
          font-family: var(--erp-font-body);
          background:
            radial-gradient(circle at top left, color-mix(in srgb, var(--erp-primary) 22%, transparent) 0%, transparent 34%),
            radial-gradient(circle at top right, color-mix(in srgb, var(--erp-accent) 18%, transparent) 0%, transparent 32%),
            linear-gradient(180deg, color-mix(in srgb, var(--erp-background) 94%, black 6%) 0%, var(--erp-background) 48%, #06090f 100%);
        }}
        a {{
          color: inherit;
          text-decoration: none;
        }}
        #root {{
          min-height: 100vh;
        }}
        .erp-shell {{
          min-height: 100vh;
          color: var(--erp-text);
        }}
        .erp-sidebar {{
          position: sticky;
          top: 0;
          height: 100vh;
          border-right: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-surface) 82%, var(--erp-background) 18%);
          backdrop-filter: blur(18px);
        }}
        .erp-topbar,
        .erp-panel,
        .erp-subpanel {{
          border: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-surface) 82%, transparent 18%);
          box-shadow: 0 28px 90px rgba(0, 0, 0, 0.28);
          backdrop-filter: blur(18px);
        }}
        .erp-subpanel {{
          background: color-mix(in srgb, var(--erp-surface) 90%, transparent 10%);
        }}
        .erp-hero {{
          border: 1px solid color-mix(in srgb, var(--erp-primary) 28%, var(--erp-border) 72%);
          background:
            radial-gradient(circle at top right, color-mix(in srgb, var(--erp-accent-cyan) 26%, transparent) 0%, transparent 32%),
            linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 18%, var(--erp-surface) 82%) 0%, color-mix(in srgb, var(--erp-accent) 14%, var(--erp-background) 86%) 100%);
        }}
        .erp-heading {{
          font-family: var(--erp-font-heading);
          letter-spacing: -0.03em;
        }}
        .erp-muted {{
          color: var(--erp-muted);
        }}
        .erp-search {{
          width: min(100%, 360px);
          border: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-background) 45%, var(--erp-surface) 55%);
          color: var(--erp-text);
          border-radius: 999px;
          padding: 0.85rem 1rem;
          outline: none;
        }}
        .erp-search::placeholder {{
          color: var(--erp-muted);
        }}
        .erp-action {{
          display: inline-flex;
          align-items: center;
          gap: 0.55rem;
          border: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-background) 36%, var(--erp-surface) 64%);
          color: var(--erp-text);
          padding: 0.7rem 1rem;
          border-radius: 999px;
          font-size: 0.85rem;
          font-weight: 600;
        }}
        .erp-action-primary {{
          background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 84%, white 16%) 0%, color-mix(in srgb, var(--erp-accent) 72%, var(--erp-primary) 28%) 100%);
          border-color: transparent;
          color: white;
        }}
        .erp-nav-link {{
          display: flex;
          align-items: center;
          gap: 0.85rem;
          border-radius: 18px;
          border: 1px solid transparent;
          padding: 0.9rem 0.95rem;
          color: var(--erp-muted);
          transition: transform 160ms ease, border-color 160ms ease, background 160ms ease, color 160ms ease;
        }}
        .erp-nav-link:hover {{
          transform: translateY(-1px);
          border-color: color-mix(in srgb, var(--erp-primary) 30%, var(--erp-border) 70%);
          color: var(--erp-text);
          background: color-mix(in srgb, var(--erp-primary) 10%, transparent 90%);
        }}
        .erp-nav-link-active {{
          color: white;
          border-color: color-mix(in srgb, var(--erp-primary) 40%, var(--erp-border) 60%);
          background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 26%, transparent) 0%, color-mix(in srgb, var(--erp-accent) 18%, transparent) 100%);
        }}
        .erp-nav-icon {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 2rem;
          height: 2rem;
          border-radius: 999px;
          background: color-mix(in srgb, var(--erp-background) 26%, var(--erp-primary) 74%);
          font-size: 0.78rem;
          font-weight: 700;
          text-transform: uppercase;
        }}
        .erp-kpi-card {{
          transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
        }}
        .erp-kpi-card:hover {{
          transform: translateY(-4px);
          border-color: color-mix(in srgb, var(--erp-primary) 34%, var(--erp-border) 66%);
          box-shadow: 0 18px 48px rgba(0, 0, 0, 0.22);
        }}
        .erp-pill {{
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 0.4rem 0.72rem;
          font-size: 0.74rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }}
        .erp-pill-positive {{
          background: color-mix(in srgb, var(--erp-success) 16%, transparent);
          color: var(--erp-success);
        }}
        .erp-pill-negative {{
          background: color-mix(in srgb, var(--erp-danger) 16%, transparent);
          color: var(--erp-danger);
        }}
        .erp-pill-neutral {{
          background: color-mix(in srgb, var(--erp-primary) 14%, transparent);
          color: color-mix(in srgb, var(--erp-primary) 82%, white 18%);
        }}
        .erp-legend {{
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          color: var(--erp-muted);
          font-size: 0.8rem;
        }}
        .erp-legend-swatch {{
          width: 0.8rem;
          height: 0.8rem;
          border-radius: 999px;
        }}
        .erp-chart-frame {{
          position: relative;
          overflow: hidden;
          border-radius: 28px;
          border: 1px solid var(--erp-border);
          background:
            linear-gradient(180deg, color-mix(in srgb, var(--erp-surface) 82%, transparent) 0%, color-mix(in srgb, var(--erp-background) 46%, transparent) 100%);
          padding: 1.35rem 1rem 0.95rem;
        }}
        .erp-chart-grid {{
          position: absolute;
          inset: 1rem 0.75rem 2.4rem;
          background-image: linear-gradient(to top, color-mix(in srgb, var(--erp-border) 72%, transparent) 1px, transparent 1px);
          background-size: 100% 25%;
          pointer-events: none;
        }}
        .erp-chart-columns {{
          position: relative;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(68px, 1fr));
          gap: 1rem;
          align-items: end;
          min-height: 280px;
        }}
        .erp-chart-column {{
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: end;
          gap: 0.75rem;
          min-height: 280px;
        }}
        .erp-chart-bars {{
          display: flex;
          align-items: end;
          gap: 0.4rem;
          height: 220px;
        }}
        .erp-chart-bar {{
          width: 16px;
          min-height: 12px;
          border-radius: 999px 999px 6px 6px;
          box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
        }}
        .erp-chart-label {{
          font-size: 0.78rem;
          color: var(--erp-muted);
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }}
        .erp-table-wrap {{
          overflow: hidden;
          border-radius: 24px;
          border: 1px solid var(--erp-border);
          background: color-mix(in srgb, var(--erp-surface) 88%, transparent);
        }}
        .erp-table {{
          width: 100%;
          border-collapse: collapse;
          min-width: 640px;
        }}
        .erp-table th {{
          padding: 1rem 1.15rem;
          text-align: left;
          color: var(--erp-muted);
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          border-bottom: 1px solid var(--erp-border);
        }}
        .erp-table td {{
          padding: 1rem 1.15rem;
          border-bottom: 1px solid color-mix(in srgb, var(--erp-border) 74%, transparent);
          vertical-align: top;
        }}
        .erp-table tbody tr:nth-child(odd) {{
          background: color-mix(in srgb, var(--erp-background) 22%, transparent);
        }}
        .erp-avatar {{
          display: inline-flex;
          width: 32px;
          height: 32px;
          border-radius: 999px;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 78%, white 22%) 0%, color-mix(in srgb, var(--erp-accent-cyan) 72%, white 28%) 100%);
          color: white;
          font-size: 0.78rem;
          font-weight: 700;
          text-transform: uppercase;
        }}
        .erp-badge {{
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 88px;
          border-radius: 999px;
          padding: 0.45rem 0.8rem;
          font-size: 0.76rem;
          font-weight: 700;
        }}
        .erp-badge-ready {{
          background: color-mix(in srgb, var(--erp-success) 16%, transparent);
          color: var(--erp-success);
        }}
        .erp-badge-scaffold {{
          background: color-mix(in srgb, var(--erp-primary) 14%, transparent);
          color: color-mix(in srgb, var(--erp-primary) 82%, white 18%);
        }}
        @media (max-width: 1279px) {{
          :root {{
            --erp-shell-padding: 24px;
            --erp-card-gap: 20px;
          }}
        }}
        @media (max-width: 1023px) {{
          :root {{
            --erp-shell-padding: 18px;
          }}
          .erp-table {{
            min-width: 560px;
          }}
        }}
        """
    ).strip()

    layout_jsx = dedent(
        """
        import { Link, useLocation } from "react-router-dom";
        import { erpSchema } from "../data/schema";

        export default function Layout({ children }) {
          const location = useLocation();
          const isTopbar = erpSchema.template?.layout_mode === "topbar";
          const navItems = erpSchema.modules.map((module) => ({
            id: module.id,
            name: module.name,
            path: `/${module.path || module.id}`,
            short: (module.name || "M").slice(0, 1),
          }));

          return (
            <div className="erp-shell text-white">
              <div className={`${isTopbar ? "block" : "lg:flex"}`}>
                {!isTopbar ? (
                  <aside
                    className="erp-sidebar hidden lg:flex lg:w-[var(--erp-sidebar-compact-width)] lg:flex-col lg:justify-between lg:px-3 lg:py-5 xl:w-[var(--erp-sidebar-width)] xl:px-5 xl:py-6"
                  >
                    <div className="space-y-6">
                      <div className="px-1">
                        <p className="text-[10px] uppercase tracking-[0.28em] erp-muted xl:text-xs">
                          {erpSchema.template?.hero_kicker || "ERP shell"}
                        </p>
                        <h1 className="erp-heading mt-3 hidden text-2xl font-semibold xl:block">
                          {erpSchema.system.name}
                        </h1>
                        <p className="erp-muted mt-3 hidden text-sm leading-6 xl:block">
                          {erpSchema.template?.reference_project}
                        </p>
                      </div>
                      <nav className="space-y-2">
                        <Link
                          to="/"
                          className={`erp-nav-link ${location.pathname === "/" ? "erp-nav-link-active" : ""}`}
                          title="Overview"
                          aria-label="Overview"
                        >
                          <span className="erp-nav-icon">D</span>
                          <span className="hidden xl:inline">Overview</span>
                        </Link>
                        {navItems.map((item) => {
                          const active = location.pathname === item.path;
                          return (
                            <Link
                              key={item.id}
                              to={item.path}
                              className={`erp-nav-link ${active ? "erp-nav-link-active" : ""}`}
                              title={item.name}
                              aria-label={item.name}
                            >
                              <span className="erp-nav-icon">{item.short}</span>
                              <span className="hidden xl:inline">{item.name}</span>
                            </Link>
                          );
                        })}
                      </nav>
                    </div>
                    <div className="erp-subpanel hidden rounded-[24px] p-4 xl:block">
                      <p className="text-[10px] uppercase tracking-[0.22em] erp-muted">Template</p>
                      <h2 className="erp-heading mt-2 text-lg font-semibold">
                        {erpSchema.template?.name || "Design shell"}
                      </h2>
                      <p className="mt-2 text-sm leading-6 erp-muted">
                        {erpSchema.template?.summary || "Generated from the current ERP blueprint."}
                      </p>
                    </div>
                  </aside>
                ) : null}
                <div className="flex min-h-screen flex-1 flex-col">
                  <header className="erp-topbar sticky top-0 z-20 m-3 rounded-[28px] px-4 py-4 md:px-5">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.28em] erp-muted">
                          {erpSchema.template?.reference_project}
                        </p>
                        <h1 className="erp-heading mt-2 text-2xl font-semibold md:text-3xl">
                          {erpSchema.template?.hero_title}
                        </h1>
                      </div>
                      <div className="flex flex-col gap-3 md:flex-row md:items-center">
                        <input
                          className="erp-search"
                          placeholder={`Search ${erpSchema.modules[0]?.entities?.[0]?.name || "records"}, workflows, routes...`}
                          readOnly
                        />
                        <div className="flex flex-wrap gap-2">
                          <span className="erp-action">
                            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" />
                            Template synced
                          </span>
                          <span className="erp-action erp-action-primary">Live preview shell</span>
                        </div>
                      </div>
                    </div>
                    <nav className={`mt-4 flex flex-wrap gap-2 ${isTopbar ? "" : "lg:hidden"}`}>
                      <Link to="/" className={`erp-nav-link ${location.pathname === "/" ? "erp-nav-link-active" : ""}`}>
                        <span className="erp-nav-icon">D</span>
                        <span>Overview</span>
                      </Link>
                      {navItems.map((item) => {
                        const active = location.pathname === item.path;
                        return (
                          <Link key={item.id} to={item.path} className={`erp-nav-link ${active ? "erp-nav-link-active" : ""}`}>
                            <span className="erp-nav-icon">{item.short}</span>
                            <span>{item.name}</span>
                          </Link>
                        );
                      })}
                    </nav>
                  </header>
                  <main className="flex-1 px-3 pb-6 md:px-4 xl:px-6">
                    <div className="mx-auto w-full max-w-7xl" style={{ padding: "var(--erp-shell-padding)" }}>
                      {children}
                    </div>
                  </main>
                </div>
              </div>
            </div>
          );
        }
        """
    ).strip()

    dashboard_jsx = dedent(
        """
        import { erpSchema } from "../data/schema";

        function pillClass(status) {
          if (status === "positive") return "erp-pill erp-pill-positive";
          if (status === "negative") return "erp-pill erp-pill-negative";
          return "erp-pill erp-pill-neutral";
        }

        export default function Dashboard() {
          const chart = erpSchema.template?.chart || { categories: [], max_value: 1, series: [] };
          const primarySeries = chart.series?.[0] || { data: [], color: "var(--erp-primary)", name: "Primary" };
          const secondarySeries = chart.series?.[1] || { data: [], color: "var(--erp-accent)", name: "Secondary" };
          const maxValue = Math.max(chart.max_value || 1, 1);

          return (
            <div className="space-y-6">
              <section className="erp-hero rounded-[32px] p-6 md:p-8">
                <div className="grid gap-6 xl:grid-cols-[1.45fr,0.85fr] xl:items-end">
                  <div>
                    <p className="text-xs uppercase tracking-[0.28em] erp-muted">{erpSchema.template?.hero_kicker}</p>
                    <h2 className="erp-heading mt-4 max-w-3xl text-4xl font-semibold leading-tight md:text-5xl">
                      {erpSchema.template?.hero_title}
                    </h2>
                    <p className="mt-4 max-w-2xl text-sm leading-7 erp-muted md:text-base">
                      {erpSchema.template?.hero_body}
                    </p>
                  </div>
                  <div className="grid gap-3">
                    <div className="erp-subpanel rounded-[24px] p-4">
                      <p className="text-[11px] uppercase tracking-[0.22em] erp-muted">Primary workspace</p>
                      <h3 className="erp-heading mt-2 text-2xl font-semibold">{erpSchema.modules[0]?.name}</h3>
                      <p className="mt-2 text-sm leading-6 erp-muted">{erpSchema.modules[0]?.summary}</p>
                    </div>
                    <div className="erp-subpanel rounded-[24px] p-4">
                      <p className="text-[11px] uppercase tracking-[0.22em] erp-muted">Template reference</p>
                      <h3 className="erp-heading mt-2 text-xl font-semibold">{erpSchema.template?.reference_project}</h3>
                      <p className="mt-2 text-sm leading-6 erp-muted">{erpSchema.template?.summary}</p>
                    </div>
                  </div>
                </div>
              </section>

              <section className="grid gap-6 lg:grid-cols-3">
                {(erpSchema.template?.kpi_metrics || []).map((metric) => (
                  <article key={metric.id} className="erp-panel erp-kpi-card rounded-[28px] p-5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.24em] erp-muted">{metric.label}</p>
                      <span className={pillClass(metric.status)}>{metric.status}</span>
                    </div>
                    <p className="erp-heading mt-5 text-4xl font-semibold">{metric.value}</p>
                    <p className="mt-3 text-sm leading-6 erp-muted">{metric.trend}</p>
                  </article>
                ))}
              </section>

              <section className="grid gap-6 xl:grid-cols-[1.7fr,0.95fr]">
                <article className="erp-panel rounded-[32px] p-6">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] erp-muted">Analytics chart</p>
                      <h3 className="erp-heading mt-2 text-2xl font-semibold">Workspace coverage by module</h3>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <span className="erp-legend">
                        <span className="erp-legend-swatch" style={{ background: primarySeries.color }} />
                        {primarySeries.name}
                      </span>
                      <span className="erp-legend">
                        <span className="erp-legend-swatch" style={{ background: secondarySeries.color }} />
                        {secondarySeries.name}
                      </span>
                    </div>
                  </div>
                  <div className="erp-chart-frame mt-8">
                    <div className="erp-chart-grid" />
                    <div className="erp-chart-columns">
                      {chart.categories.map((label, index) => {
                        const primaryValue = primarySeries.data?.[index] || 0;
                        const secondaryValue = secondarySeries.data?.[index] || 0;
                        const primaryHeight = `${Math.max((primaryValue / maxValue) * 100, 10)}%`;
                        const secondaryHeight = `${Math.max((secondaryValue / maxValue) * 100, 10)}%`;
                        return (
                          <div key={label} className="erp-chart-column">
                            <div className="erp-chart-bars">
                              <div className="erp-chart-bar" style={{ height: primaryHeight, background: primarySeries.color }} />
                              <div className="erp-chart-bar" style={{ height: secondaryHeight, background: secondarySeries.color }} />
                            </div>
                            <span className="erp-chart-label">{label}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </article>

                <aside className="space-y-6">
                  <div className="erp-panel rounded-[32px] p-6">
                    <p className="text-xs uppercase tracking-[0.22em] erp-muted">Workflow lane</p>
                    <div className="mt-6 space-y-3">
                      {(erpSchema.template?.workflow_highlights || []).map((item) => (
                        <article key={item} className="erp-subpanel rounded-[24px] p-4">
                          <p className="text-sm font-semibold text-white">{item}</p>
                          <p className="mt-2 text-sm leading-6 erp-muted">
                            Template-guided workflow block ready for the generated ERP shell.
                          </p>
                        </article>
                      ))}
                    </div>
                  </div>
                  <div className="erp-panel rounded-[32px] p-6">
                    <p className="text-xs uppercase tracking-[0.22em] erp-muted">Workspace index</p>
                    <div className="mt-6 space-y-3">
                      {erpSchema.modules.slice(0, 4).map((module) => (
                        <article key={module.id} className="erp-subpanel rounded-[24px] p-4">
                          <p className="text-sm font-semibold text-white">{module.name}</p>
                          <p className="mt-2 text-sm leading-6 erp-muted">{module.summary}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                </aside>
              </section>

              <section className="erp-panel rounded-[32px] p-6">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.22em] erp-muted">Activity table</p>
                    <h3 className="erp-heading mt-2 text-2xl font-semibold">Module routing and workspace focus</h3>
                  </div>
                  <span className="erp-action">{(erpSchema.template?.activity_rows || []).length} tracked rows</span>
                </div>
                <div className="erp-table-wrap mt-6 overflow-x-auto">
                  <table className="erp-table">
                    <thead>
                      <tr>
                        <th>Workspace</th>
                        <th>Focus</th>
                        <th>Route</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(erpSchema.template?.activity_rows || []).map((row) => (
                        <tr key={`${row.workspace}-${row.route}`}>
                          <td>
                            <div className="flex items-center gap-3">
                              <span className="erp-avatar">{row.workspace.slice(0, 1)}</span>
                              <div>
                                <p className="font-semibold text-white">{row.workspace}</p>
                                <p className="mt-1 text-sm erp-muted">{erpSchema.template?.reference_project}</p>
                              </div>
                            </div>
                          </td>
                          <td className="text-sm erp-muted">{row.focus}</td>
                          <td className="font-mono text-sm text-slate-200">{row.route}</td>
                          <td>
                            <span className={`erp-badge ${row.status === "Ready" ? "erp-badge-ready" : "erp-badge-scaffold"}`}>
                              {row.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          );
        }
        """
    ).strip()

    module_workspace_jsx = dedent(
        """
        import { useParams } from "react-router-dom";
        import { erpSchema } from "../data/schema";

        export default function ModuleWorkspace() {
          const params = useParams();
          const module =
            erpSchema.modules.find((entry) => entry.path === params.moduleId || entry.id === params.moduleId) ||
            erpSchema.modules[0] ||
            { name: "Workspace", summary: "Generated ERP workspace", entities: [], workflows: [], endpoints: [] };

          const stats = [
            {
              id: "entities",
              label: "Entities",
              value: String(module.entities?.length || 0).padStart(2, "0"),
              detail: "Structured records available in this workspace.",
            },
            {
              id: "workflows",
              label: "Workflows",
              value: String(module.workflows?.length || 0).padStart(2, "0"),
              detail: "Process lanes aligned to the template shell.",
            },
            {
              id: "routes",
              label: "Routes",
              value: String(module.endpoints?.length || 0).padStart(2, "0"),
              detail: "Connected API endpoints for the generated module.",
            },
          ];

          return (
            <div className="space-y-6">
              <section className="erp-hero rounded-[32px] p-6 md:p-8">
                <p className="text-xs uppercase tracking-[0.24em] erp-muted">{module.name}</p>
                <h2 className="erp-heading mt-3 text-4xl font-semibold md:text-5xl">{module.name} workspace</h2>
                <p className="mt-4 max-w-3xl text-sm leading-7 erp-muted md:text-base">{module.summary}</p>
              </section>
              <section className="grid gap-6 lg:grid-cols-3">
                {stats.map((stat) => (
                  <article key={stat.id} className="erp-panel rounded-[28px] p-5">
                    <p className="text-xs uppercase tracking-[0.22em] erp-muted">{stat.label}</p>
                    <p className="erp-heading mt-4 text-4xl font-semibold">{stat.value}</p>
                    <p className="mt-3 text-sm leading-6 erp-muted">{stat.detail}</p>
                  </article>
                ))}
              </section>

              <section className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
                <div className="erp-panel rounded-[32px] p-6">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.22em] erp-muted">Entities</p>
                      <h3 className="erp-heading mt-2 text-2xl font-semibold">Record model blocks</h3>
                    </div>
                    <span className="erp-action">{module.entities?.length || 0} records</span>
                  </div>
                  <div className="mt-6 grid gap-6 md:grid-cols-2">
                    {(module.entities || []).map((entity) => (
                      <article key={entity.name} className="erp-subpanel rounded-[28px] p-5">
                        <h4 className="erp-heading text-xl font-semibold">{entity.name}</h4>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {(entity.fields || []).map((field) => (
                            <span key={field} className="erp-pill erp-pill-neutral">
                              {field}
                            </span>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>

                <div className="space-y-6">
                  <aside className="erp-panel rounded-[32px] p-6">
                    <p className="text-xs uppercase tracking-[0.22em] erp-muted">Workflow lane</p>
                    <div className="mt-6 space-y-3">
                      {(module.workflows || []).map((workflow) => (
                        <article key={workflow.name} className="erp-subpanel rounded-[24px] p-4">
                          <p className="text-sm font-semibold text-white">{workflow.name}</p>
                          <p className="mt-2 text-sm leading-6 erp-muted">
                            {(workflow.steps || []).join(" -> ") || "Operational workflow ready for implementation."}
                          </p>
                        </article>
                      ))}
                    </div>
                  </aside>

                  <aside className="erp-panel rounded-[32px] p-6">
                    <p className="text-xs uppercase tracking-[0.22em] erp-muted">API routes</p>
                    <div className="erp-table-wrap mt-6 overflow-x-auto">
                      <table className="erp-table">
                        <thead>
                          <tr>
                            <th>Method</th>
                            <th>Path</th>
                            <th>Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(module.endpoints || []).map((endpoint) => (
                            <tr key={`${endpoint.method}-${endpoint.path}`}>
                              <td className="font-semibold text-white">{endpoint.method}</td>
                              <td className="font-mono text-sm text-slate-200">{endpoint.path}</td>
                              <td className="text-sm erp-muted">{endpoint.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </aside>
                </div>
              </section>
            </div>
          );
        }
        """
    ).strip()

    return {
        "files": [
            {"path": "src/App.jsx", "language": "jsx", "content": app_jsx},
            {"path": "src/styles/template.css", "language": "css", "content": template_css},
            {"path": "src/components/Layout.jsx", "language": "jsx", "content": layout_jsx},
            {"path": "src/pages/Dashboard.jsx", "language": "jsx", "content": dashboard_jsx},
            {"path": "src/pages/ModuleWorkspace.jsx", "language": "jsx", "content": module_workspace_jsx},
            {"path": "src/data/schema.js", "language": "js", "content": f"export const erpSchema = {schema_payload};"},
        ],
        "dependencies": {
            "react": "^18.3.1",
            "react-router-dom": "^6.30.1",
            "tailwindcss": "^3.4.17",
        },
    }
