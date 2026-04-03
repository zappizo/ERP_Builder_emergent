from __future__ import annotations

import copy
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from .config import get_settings


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_from_repo_root(value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


def _repo_relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_text(path: Path, warnings: list[str], description: str) -> str:
    if not path.exists():
        warnings.append(f"{description} not found at {path}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        warnings.append(f"Could not read {description} at {path}: {exc}")
        return ""


def _content_hash(content: str) -> str | None:
    normalized = content.strip()
    if not normalized:
        return None
    return sha256(normalized.encode("utf-8")).hexdigest()


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n... (truncated)"


def _css_variables(css_text: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css_text):
        variables[name.strip()] = value.strip()
    return variables


def _normalize_language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".css": "css",
        ".js": "js",
        ".jsx": "jsx",
        ".ts": "ts",
        ".tsx": "tsx",
    }.get(suffix, "text")


def _template_definitions() -> list[dict[str, Any]]:
    settings = get_settings()
    templates_root = Path(settings.generated_erp_templates_dir).as_posix().rstrip("/")
    return [
        {
            "id": "template_1",
            "name": "Template 1",
            "display_name": "Template 1 - Athena",
            "reference_project": "Athena",
            "relative_directory": f"{templates_root}/Template 1",
            "summary": (
                "Dark command-center ERP shell with glass panels, dense dashboard staging, "
                "workflow strips, and bold row-level actions inspired by Athena."
            ),
            "source_files": [
                {"relative_path": "style.css", "role": "theme"},
                {"relative_path": "templates.ts", "role": "ui-shell"},
                {"relative_path": "main.ts", "role": "app-entry"},
            ],
            "design_cues": {
                "project": "Athena",
                "theme": {
                    "palette": {
                        "primary": "#00c3ff",
                        "secondary": "#4aa8ff",
                        "background": "#060912",
                        "surface": "#0e1528",
                        "text": {"primary": "#eef4ff", "secondary": "#c3d0ea"},
                        "border": "rgba(74, 168, 255, 0.18)",
                        "success": "#5de2ae",
                        "danger": "#ff9b93",
                    },
                    "spacing": {
                        "container_padding": "32px",
                        "card_gap": "24px",
                        "border_radius": "24px",
                    },
                },
                "layout": {"navigation": "sidebar", "density": "comfortable"},
                "branding": {
                    "kicker": "Athena reference shell",
                    "hero_title": "Operate the ERP like a control center",
                    "hero_body": (
                        "Use glass panels, status strips, bold dashboards, and action-heavy records "
                        "that feel like an active operations room."
                    ),
                },
                "typography": {"heading": "'Sora', sans-serif", "body": "'Manrope', sans-serif"},
                "dashboard": {
                    "workflow_highlights": [
                        "Dashboard command cards",
                        "CRM stage strips",
                        "Sales handoff actions",
                        "Accounting snapshots",
                        "Investment allocation view",
                    ]
                },
                "components": {
                    "sidebar": {
                        "width": "260px",
                        "items": ["Overview", "CRM", "Sales", "Projects", "HRM", "Accounting", "Investment"],
                    },
                    "kpi_metrics": [
                        {"status": "positive"},
                        {"status": "positive"},
                        {"status": "neutral"},
                    ],
                    "main_chart": {
                        "type": "Area",
                        "series": [
                            {"name": "Entities", "color": "#00c3ff"},
                            {"name": "Workflows", "color": "#4aa8ff"},
                        ],
                    },
                },
                "interactions": {
                    "row_actions": ["view", "export csv", "export pdf"],
                    "detail_drawers": True,
                    "stage_strips": True,
                    "module_workspaces": True,
                },
                "motion": {"feel": "soft-glass", "cards": "lift on hover", "page": "fade-up"},
            },
        },
        {
            "id": "template_2",
            "name": "Template 2",
            "display_name": "Template 2 - Print Co",
            "reference_project": "Print Co",
            "relative_directory": f"{templates_root}/Template 2",
            "summary": (
                "Warm paper-toned ERP UI with horizontal module navigation, tactile cards, "
                "structured tables, and operational export tools inspired by Print Co."
            ),
            "source_files": [
                {"relative_path": "styles.css", "role": "theme"},
                {"relative_path": "app.js", "role": "ui-shell"},
                {"relative_path": "ui-enhance.js", "role": "ui-enhancements"},
            ],
            "design_cues": {
                "project": "Print Co",
                "theme": {
                    "palette": {
                        "primary": "#1f5f5b",
                        "secondary": "#8a6a3f",
                        "background": "#f3f0e8",
                        "surface": "#fffaf2",
                        "text": {"primary": "#1f2933", "secondary": "#5f6b76"},
                        "border": "rgba(89, 103, 120, 0.18)",
                        "success": "#2f7d4c",
                        "danger": "#a8543a",
                    },
                    "spacing": {
                        "container_padding": "28px",
                        "card_gap": "22px",
                        "border_radius": "20px",
                    },
                },
                "layout": {"navigation": "topbar", "density": "comfortable"},
                "branding": {
                    "kicker": "Print Co reference shell",
                    "hero_title": "Run the ERP with warm, tactile operations views",
                    "hero_body": (
                        "Use layered paper surfaces, horizontal module grouping, and strong export/detail "
                        "actions that feel grounded and process-driven."
                    ),
                },
                "typography": {"heading": "'Sora', sans-serif", "body": "'Manrope', sans-serif"},
                "dashboard": {
                    "workflow_highlights": [
                        "Compact KPI rows",
                        "Operational watchlists",
                        "Export-ready tables",
                        "Row detail overlays",
                        "Role-aware workspace tabs",
                    ]
                },
                "components": {
                    "sidebar": {
                        "width": "100%",
                        "items": ["Dashboard", "Procurement", "Inventory", "Sales", "Production", "Accounts"],
                    },
                    "kpi_metrics": [
                        {"status": "good"},
                        {"status": "active"},
                        {"status": "neutral"},
                    ],
                    "main_chart": {
                        "type": "Bar",
                        "series": [
                            {"name": "Operations", "color": "#1f5f5b"},
                            {"name": "Support", "color": "#8a6a3f"},
                        ],
                    },
                },
                "interactions": {
                    "row_actions": ["view", "export csv", "export pdf"],
                    "detail_drawers": True,
                    "table_exports": True,
                    "module_tabs": True,
                },
                "motion": {"feel": "paper-soft", "cards": "gentle lift", "page": "fade-in"},
            },
        },
    ]


def resolve_erp_ui_template_id(template_id: str | None) -> str:
    settings = get_settings()
    definitions = {item["id"]: item for item in _template_definitions()}
    candidate = str(template_id or settings.generated_erp_default_template_id or "template_1").strip().lower()
    if candidate in definitions:
        return candidate
    return settings.generated_erp_default_template_id


def _template_source_file_payload(
    template_dir: Path,
    source_file: dict[str, Any],
    warnings: list[str],
    *,
    include_content: bool,
) -> dict[str, Any]:
    relative_path = str(source_file.get("relative_path") or "").strip()
    absolute_path = template_dir / relative_path
    content = _read_text(absolute_path, warnings, f"ERP template source file {relative_path}")
    payload = {
        "relative_path": _repo_relative_path(absolute_path),
        "path": str(absolute_path),
        "language": source_file.get("language") or _normalize_language(relative_path),
        "role": source_file.get("role"),
        "sha256": _content_hash(content),
        "has_content": bool(content.strip()),
    }
    if include_content:
        payload["content"] = content
    return payload


def _apply_css_tokens(template_payload: dict[str, Any], css_variables: dict[str, str]) -> None:
    design_cues = template_payload["design_cues"]
    theme = design_cues.setdefault("theme", {})
    palette = theme.setdefault("palette", {})
    text_palette = palette.setdefault("text", {})
    spacing = theme.setdefault("spacing", {})

    palette["background"] = css_variables.get("--bg", palette.get("background"))
    palette["surface"] = css_variables.get("--paper-strong", css_variables.get("--paper", palette.get("surface")))
    palette["primary"] = css_variables.get("--accent", palette.get("primary"))
    palette["secondary"] = css_variables.get("--accent2", palette.get("secondary"))
    palette["border"] = css_variables.get("--border", palette.get("border"))
    palette["success"] = css_variables.get("--good", palette.get("success"))
    palette["danger"] = css_variables.get("--alert", palette.get("danger"))
    text_palette["primary"] = css_variables.get("--ink", text_palette.get("primary"))
    text_palette["secondary"] = css_variables.get("--muted", text_palette.get("secondary"))

    if "--space-4" in css_variables:
        spacing["card_gap"] = spacing.get("card_gap") or css_variables["--space-4"]


def _build_template_reference(template_definition: dict[str, Any], *, include_source_contents: bool) -> dict[str, Any]:
    template_dir = _resolve_from_repo_root(template_definition["relative_directory"])
    warnings: list[str] = []
    source_files = [
        _template_source_file_payload(
            template_dir,
            source_file,
            warnings,
            include_content=include_source_contents,
        )
        for source_file in template_definition.get("source_files", [])
    ]

    has_actionable_content = any(item.get("has_content") for item in source_files)
    css_text = "\n\n".join(
        str(item.get("content") or "")
        for item in source_files
        if item.get("language") == "css" and include_source_contents
    )
    css_variables = _css_variables(css_text)

    combined_hash = _content_hash(
        "\n".join(
            item["sha256"]
            for item in source_files
            if item.get("sha256")
        )
    )

    if not source_files:
        status = "missing_files"
        warnings.append("No ERP template source files are registered for this template.")
    elif has_actionable_content:
        status = "ready"
    else:
        status = "empty"
        warnings.append("ERP template source files exist but are empty. Save CSS and component code before generating an ERP.")

    payload = {
        "id": template_definition["id"],
        "name": template_definition["name"],
        "display_name": template_definition["display_name"],
        "reference_project": template_definition["reference_project"],
        "status": status,
        "directory": str(template_dir),
        "relative_directory": _repo_relative_path(template_dir),
        "summary": template_definition.get("summary") or "",
        "design_cues": copy.deepcopy(template_definition.get("design_cues") or {}),
        "source_files": source_files,
        "source_file_paths": [item["relative_path"] for item in source_files],
        "source_sha256": combined_hash,
        "has_actionable_content": has_actionable_content,
        "warnings": warnings,
    }
    _apply_css_tokens(payload, css_variables)
    return payload


def list_erp_ui_templates(*, include_source_contents: bool = False) -> list[dict[str, Any]]:
    return [
        _build_template_reference(template_definition, include_source_contents=include_source_contents)
        for template_definition in _template_definitions()
    ]


def load_erp_ui_template(template_id: str | None = None) -> dict[str, Any]:
    resolved_id = resolve_erp_ui_template_id(template_id)
    for template_definition in _template_definitions():
        if template_definition["id"] == resolved_id:
            return _build_template_reference(template_definition, include_source_contents=True)
    return _build_template_reference(_template_definitions()[0], include_source_contents=True)


def attach_erp_ui_template_metadata(
    master_json: dict[str, Any],
    template_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(master_json or {})
    documentation = dict(enriched.get("documentation") or {})
    template_reference = template_reference or load_erp_ui_template()

    documentation["erp_ui_template"] = {
        "id": template_reference.get("id"),
        "name": template_reference.get("name"),
        "display_name": template_reference.get("display_name"),
        "reference_project": template_reference.get("reference_project"),
        "status": template_reference.get("status"),
        "relative_directory": template_reference.get("relative_directory"),
        "source_file_paths": list(template_reference.get("source_file_paths") or []),
        "source_files": [
            {
                "relative_path": item.get("relative_path"),
                "language": item.get("language"),
                "role": item.get("role"),
                "sha256": item.get("sha256"),
            }
            for item in (template_reference.get("source_files") or [])
        ],
        "has_actionable_content": template_reference.get("has_actionable_content", False),
        "source_sha256": template_reference.get("source_sha256"),
        "summary": template_reference.get("summary") or "",
        "design_cues": template_reference.get("design_cues") or {},
        "warnings": list(template_reference.get("warnings") or []),
        "usage_directive": (
            "Apply this template only to ERP applications generated from user prompts. "
            "Do not use it to restyle the AI ERP Builder product UI."
        ),
    }
    enriched["documentation"] = documentation
    return enriched


def format_erp_ui_template_prompt_context(
    template_reference: dict[str, Any] | None,
    *,
    design_char_limit: int = 5000,
    source_char_limit: int = 5000,
) -> str:
    if not template_reference:
        return "No ERP UI/UX template was supplied."

    lines = [
        "ERP UI/UX template reference:",
        f"- Template ID: {template_reference.get('id', 'template_1')}",
        f"- Name: {template_reference.get('display_name') or template_reference.get('name', 'Template 1')}",
        f"- Reference Project: {template_reference.get('reference_project', 'Unknown')}",
        f"- Status: {template_reference.get('status', 'unknown')}",
        f"- Directory: {template_reference.get('relative_directory') or template_reference.get('directory') or 'unknown'}",
        (
            "- Usage directive: Apply this template only to the generated ERP application. "
            "Do not change the AI ERP Builder product interface."
        ),
    ]

    summary = str(template_reference.get("summary") or "").strip()
    if summary:
        lines.append(f"- Template summary: {summary}")

    source_paths = list(template_reference.get("source_file_paths") or [])
    if source_paths:
        lines.append(f"- Source files: {' | '.join(source_paths)}")

    warnings = list(template_reference.get("warnings") or [])
    if warnings:
        lines.append(f"- Warnings: {' | '.join(warnings)}")

    design_cues = template_reference.get("design_cues")
    if design_cues:
        lines.extend(
            [
                "",
                "Structured design cues:",
                _truncate(json.dumps(design_cues, indent=2), design_char_limit),
            ]
        )

    source_files = list(template_reference.get("source_files") or [])
    source_sections = []
    for source_file in source_files[:4]:
        content = str(source_file.get("content") or "").strip()
        if not content:
            continue
        language = source_file.get("language") or "text"
        relative_path = source_file.get("relative_path") or source_file.get("path") or "unknown"
        role = source_file.get("role") or "reference"
        source_sections.append(
            "\n".join(
                [
                    f"Source excerpt: {relative_path} ({role})",
                    f"```{language}",
                    _truncate(content, source_char_limit // max(len(source_files[:4]), 1)),
                    "```",
                ]
            )
        )
    if source_sections:
        lines.extend(["", "Template source excerpts:", "\n\n".join(source_sections)])

    if not template_reference.get("has_actionable_content"):
        lines.append("")
        lines.append("The template source files are present but currently empty, so there is no usable UI payload yet.")

    return "\n".join(lines).strip()
