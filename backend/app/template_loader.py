from __future__ import annotations

import json
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


def _markdown_summary(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:180]
    return ""


def _select_design_cues(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    preferred_keys = (
        "theme",
        "branding",
        "layout",
        "navigation",
        "pages",
        "screens",
        "dashboard",
        "components",
        "forms",
        "tables",
        "reports",
        "charts",
        "typography",
        "spacing",
        "motion",
        "interactions",
    )
    cues = {key: payload[key] for key in preferred_keys if key in payload}
    if cues:
        return cues
    return {"top_level_keys": list(payload.keys())[:20]}


def load_erp_ui_template() -> dict[str, Any]:
    settings = get_settings()
    template_dir = _resolve_from_repo_root(settings.generated_erp_template_dir)
    json_path = template_dir / settings.generated_erp_template_json_file
    markdown_path = template_dir / settings.generated_erp_template_markdown_file

    warnings: list[str] = []
    json_raw = _read_text(json_path, warnings, "ERP template JSON file")
    markdown_raw = _read_text(markdown_path, warnings, "ERP template Markdown file")

    parsed_json: Any | None = None
    if json_raw.strip():
        try:
            parsed_json = json.loads(json_raw)
        except json.JSONDecodeError as exc:
            warnings.append(f"ERP template JSON is invalid: {exc}")

    has_json_content = bool(json_raw.strip())
    has_markdown_content = bool(markdown_raw.strip())
    has_actionable_content = parsed_json is not None or has_markdown_content

    if not has_json_content and not has_markdown_content:
        status = "empty"
        warnings.append("ERP template JSON and Markdown files are empty on disk. Save real template content before generating or revising an ERP.")
    elif has_json_content and parsed_json is None:
        status = "invalid_json"
    else:
        status = "ready"

    return {
        "name": template_dir.name or "Template 1",
        "status": status,
        "directory": str(template_dir),
        "relative_directory": _repo_relative_path(template_dir),
        "json_path": str(json_path),
        "json_relative_path": _repo_relative_path(json_path),
        "markdown_path": str(markdown_path),
        "markdown_relative_path": _repo_relative_path(markdown_path),
        "json_raw": json_raw,
        "json_data": parsed_json,
        "markdown_raw": markdown_raw,
        "has_json_content": has_json_content,
        "has_markdown_content": has_markdown_content,
        "has_actionable_content": has_actionable_content,
        "json_sha256": _content_hash(json_raw),
        "markdown_sha256": _content_hash(markdown_raw),
        "summary": _markdown_summary(markdown_raw),
        "design_cues": _select_design_cues(parsed_json),
        "warnings": warnings,
    }


def attach_erp_ui_template_metadata(
    master_json: dict[str, Any],
    template_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(master_json or {})
    documentation = dict(enriched.get("documentation") or {})
    template_reference = template_reference or load_erp_ui_template()

    documentation["erp_ui_template"] = {
        "name": template_reference.get("name"),
        "status": template_reference.get("status"),
        "relative_directory": template_reference.get("relative_directory"),
        "json_relative_path": template_reference.get("json_relative_path"),
        "markdown_relative_path": template_reference.get("markdown_relative_path"),
        "has_json_content": template_reference.get("has_json_content", False),
        "has_markdown_content": template_reference.get("has_markdown_content", False),
        "has_actionable_content": template_reference.get("has_actionable_content", False),
        "json_sha256": template_reference.get("json_sha256"),
        "markdown_sha256": template_reference.get("markdown_sha256"),
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
    json_char_limit: int = 5000,
    markdown_char_limit: int = 5000,
) -> str:
    if not template_reference:
        return "No ERP UI/UX template was supplied."

    lines = [
        "ERP UI/UX template reference:",
        f"- Name: {template_reference.get('name', 'Template 1')}",
        f"- Status: {template_reference.get('status', 'unknown')}",
        f"- Directory: {template_reference.get('relative_directory') or template_reference.get('directory') or 'unknown'}",
        (
            "- Usage directive: Apply this template only to the generated ERP application. "
            "Do not change the AI ERP Builder product interface."
        ),
    ]

    summary = str(template_reference.get("summary") or "").strip()
    if summary:
        lines.append(f"- Markdown summary: {summary}")

    warnings = list(template_reference.get("warnings") or [])
    if warnings:
        lines.append(f"- Warnings: {' | '.join(warnings)}")

    design_cues = template_reference.get("design_cues")
    if design_cues:
        lines.extend(
            [
                "",
                "Structured design cues:",
                _truncate(json.dumps(design_cues, indent=2), json_char_limit),
            ]
        )

    json_payload = ""
    if template_reference.get("json_data") is not None:
        json_payload = json.dumps(template_reference["json_data"], indent=2)
    elif template_reference.get("json_raw"):
        json_payload = str(template_reference["json_raw"])
    if json_payload.strip():
        lines.extend(["", "Template JSON:", _truncate(json_payload, json_char_limit)])

    markdown_payload = str(template_reference.get("markdown_raw") or "").strip()
    if markdown_payload:
        lines.extend(["", "Template Markdown:", _truncate(markdown_payload, markdown_char_limit)])

    if not template_reference.get("has_actionable_content"):
        lines.append("")
        lines.append("The template files are present but currently empty, so there is no usable UI payload yet.")

    return "\n".join(lines).strip()
