from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import AuditLog, ERPState, User
from seed import DEMO_USERS, MASTER_BLUEPRINT, ROLE_DIRECTORY


def serialize_user(user: User | dict) -> dict[str, str]:
    if isinstance(user, dict):
        return {
            "id": str(user["id"]),
            "name": str(user["name"]),
            "email": str(user["email"]),
            "role": str(user["role"]),
        }
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


def _utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _get_state_row(db: Session) -> ERPState:
    state_row = db.query(ERPState).filter(ERPState.id == 1).first()
    if not state_row:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ERP state is not seeded yet.")
    return state_row


def _get_state_payload(db: Session) -> dict:
    state_row = _get_state_row(db)
    return dict(state_row.payload or {"modules": {}})


def _save_state_payload(db: Session, payload: dict) -> None:
    state_row = _get_state_row(db)
    state_row.payload = payload
    state_row.updated_at = datetime.utcnow()
    db.add(state_row)
    db.commit()


def _module_by_id(module_id: str) -> dict:
    module_key = str(module_id or "").strip().lower()
    for module in MASTER_BLUEPRINT.get("modules", []):
        if module["id"] == module_key or module.get("path") == module_key:
            return module
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown module '{module_id}'.")


def role_capabilities(role_name: str) -> dict[str, bool]:
    lowered = str(role_name or "").lower()
    role_definition = next((role for role in ROLE_DIRECTORY if role["name"].lower() == lowered), None)
    permissions = [permission.lower() for permission in (role_definition or {}).get("permissions", [])]
    can_edit = "view" not in permissions or any(
        token in permissions for token in ["create", "update", "manage", "approve", "configure"]
    )
    can_approve = any(token in permissions for token in ["approve", "manage", "configure"])
    if "admin" in lowered:
        can_edit = True
        can_approve = True
    return {"can_view": True, "can_edit": can_edit, "can_approve": can_approve}


def _ensure_allowed(role_name: str, required: str) -> dict[str, bool]:
    capabilities = role_capabilities(role_name)
    if required == "edit" and not capabilities["can_edit"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role cannot modify records.")
    if required == "approve" and not capabilities["can_approve"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role cannot approve workflows.")
    return capabilities


def _record_actions(role_name: str, record: dict) -> list[str]:
    capabilities = role_capabilities(role_name)
    status_value = str(record.get("status") or "").lower()
    actions: list[str] = []
    if capabilities["can_edit"] and status_value not in {"completed", "archived"}:
        actions.extend(["advance", "hold", "complete"])
    if capabilities["can_approve"] and status_value not in {"approved", "completed"}:
        actions.append("approve")
    if capabilities["can_edit"] and status_value in {"on hold", "completed", "approved"}:
        actions.append("reopen")
    return list(dict.fromkeys(actions))


def _workflow_steps(module: dict) -> list[str]:
    workflows = module.get("workflows") or []
    if workflows and workflows[0].get("steps"):
        return [str(step) for step in workflows[0]["steps"]]
    return ["Draft", "Review", "Approve", "Complete"]


def _enrich_record(module: dict, record: dict, role_name: str) -> dict:
    values = dict(record.get("values") or {})
    highlights = []
    for field in module.get("form_fields", [])[:2]:
        value = values.get(field["name"])
        if value:
            highlights.append(f"{field['label']}: {value}")

    return {
        **record,
        "summary": " | ".join(highlights) or module.get("summary") or f"{module['name']} workspace",
        "actions": _record_actions(role_name, record),
    }


def _write_audit_log(db: Session, module: dict, record: dict, action: str, actor: dict, note: str = "") -> None:
    message = f"{action.title()} completed for {record['title']}"
    if note:
        message = f"{message}: {note}"
    db.add(
        AuditLog(
            module_id=module["id"],
            record_id=record["id"],
            action=action,
            actor_id=str(actor["id"]),
            actor_name=str(actor["name"]),
            actor_role=str(actor["role"]),
            message=message,
        )
    )
    db.commit()


def recent_activity(db: Session, module_id: str | None = None, limit: int = 8) -> list[dict]:
    query = db.query(AuditLog)
    if module_id:
        query = query.filter(AuditLog.module_id == module_id)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    module_names = {module["id"]: module["name"] for module in MASTER_BLUEPRINT.get("modules", [])}
    return [
        {
            "id": row.id,
            "module_id": row.module_id,
            "module_name": module_names.get(row.module_id, row.module_id),
            "record_id": row.record_id,
            "action": row.action,
            "actor_id": row.actor_id,
            "actor_name": row.actor_name,
            "actor_role": row.actor_role,
            "message": row.message,
            "created_at": row.created_at.replace(microsecond=0).isoformat() + "Z",
        }
        for row in rows
    ]


def module_catalog(db: Session, role_name: str) -> list[dict]:
    payload = _get_state_payload(db)
    catalog = []
    for module in MASTER_BLUEPRINT.get("modules", []):
        module_state = payload.get("modules", {}).get(module["id"], {})
        records = module_state.get("records", [])
        catalog.append(
            {
                "id": module["id"],
                "path": module.get("path", module["id"]),
                "name": module["name"],
                "summary": module["summary"],
                "record_count": len(records),
                "open_count": sum(
                    1 for record in records if str(record.get("status") or "").lower() not in {"completed", "archived"}
                ),
                "available_actions": _record_actions(role_name, records[0] if records else {"status": "draft"}),
            }
        )
    return catalog


def dashboard_payload(db: Session, actor: dict) -> dict:
    payload = _get_state_payload(db)
    modules = module_catalog(db, actor["role"])
    all_records = []
    for module in MASTER_BLUEPRINT.get("modules", []):
        module_records = payload.get("modules", {}).get(module["id"], {}).get("records", [])
        for record in module_records:
            all_records.append((module, record))

    workflow_queue = [
        {
            "module_id": module["id"],
            "module_name": module["name"],
            "record_id": record["id"],
            "title": record["title"],
            "status": record["status"],
        }
        for module, record in all_records
        if str(record.get("status") or "").lower() not in {"completed", "approved", "archived"}
    ][:6]

    return {
        "system": MASTER_BLUEPRINT.get("system", {}),
        "user": actor,
        "metrics": [
            {"id": "modules", "label": "Active Modules", "value": f"{len(modules):02d}", "trend": "Connected to the generated backend", "status": "positive"},
            {"id": "records", "label": "Live Records", "value": f"{len(all_records):02d}", "trend": "Seeded and editable preview data", "status": "positive"},
            {"id": "queue", "label": "Workflow Queue", "value": f"{len(workflow_queue):02d}", "trend": f"{actor['role']} access profile applied", "status": "neutral"},
        ],
        "modules": modules,
        "workflow_queue": workflow_queue,
        "recent_activity": recent_activity(db, limit=8),
    }


def module_workspace_payload(db: Session, module_id: str, actor: dict) -> dict:
    module = _module_by_id(module_id)
    payload = _get_state_payload(db)
    module_state = payload.get("modules", {}).get(module["id"], {"sequence": 0, "records": []})
    records = [_enrich_record(module, record, actor["role"]) for record in module_state.get("records", [])]
    return {
        "module": {
            "id": module["id"],
            "name": module["name"],
            "summary": module["summary"],
            "headline": f"{module['name']} execution workspace",
            "entity_name": module.get("entity_name", "Record"),
        },
        "form_fields": [
            {
                "name": field["name"],
                "label": field["label"],
                "input_type": "number"
                if any(token in field["name"].lower() for token in ["amount", "price", "qty", "cost"])
                else ("date" if "date" in field["name"].lower() else "text"),
            }
            for field in module.get("form_fields", [])
        ],
        "records": records,
        "available_actions": _record_actions(actor["role"], records[0] if records else {"status": "draft"}),
        "recent_activity": recent_activity(db, module["id"], limit=8),
    }


def create_record(db: Session, module_id: str, payload: dict, actor: dict) -> dict:
    _ensure_allowed(actor["role"], "edit")
    module = _module_by_id(module_id)
    state = _get_state_payload(db)
    module_state = state.setdefault("modules", {}).setdefault(module["id"], {"sequence": 0, "records": []})
    module_state["sequence"] = int(module_state.get("sequence") or 0) + 1
    sequence = module_state["sequence"]
    values = dict(payload.get("values") or {})
    normalized_values = {}
    for field in module.get("form_fields", []):
        field_value = values.get(field["name"])
        normalized_values[field["name"]] = str(field_value).strip() if field_value not in (None, "") else f"{field['label']} {sequence}"

    steps = _workflow_steps(module)
    record = {
        "id": f"{module['id']}-{sequence:03d}",
        "title": normalized_values.get("name") or normalized_values.get("title") or f"{module['name']} record {sequence}",
        "status": steps[0],
        "workflow_stage": steps[0],
        "owner": actor["name"],
        "updated_at": _utc_timestamp(),
        "values": normalized_values,
    }
    module_state.setdefault("records", []).insert(0, record)
    _save_state_payload(db, state)
    _write_audit_log(db, module, record, "create", actor, payload.get("note", ""))
    return _enrich_record(module, record, actor["role"])


def run_record_action(db: Session, module_id: str, record_id: str, action: str, actor: dict, note: str = "") -> dict:
    module = _module_by_id(module_id)
    required_permission = "approve" if action == "approve" else "edit"
    _ensure_allowed(actor["role"], required_permission)
    state = _get_state_payload(db)
    module_state = state.get("modules", {}).get(module["id"], {})
    records = module_state.get("records", [])
    record = next((item for item in records if item["id"] == record_id), None)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")

    steps = _workflow_steps(module)
    current_stage = str(record.get("workflow_stage") or record.get("status") or steps[0])
    current_index = steps.index(current_stage) if current_stage in steps else 0

    if action == "advance":
        next_index = min(current_index + 1, len(steps) - 1)
        record["workflow_stage"] = steps[next_index]
        record["status"] = steps[next_index]
    elif action == "approve":
        record["workflow_stage"] = "Approved"
        record["status"] = "Approved"
    elif action == "hold":
        record["workflow_stage"] = "On Hold"
        record["status"] = "On Hold"
    elif action == "complete":
        record["workflow_stage"] = "Completed"
        record["status"] = "Completed"
    elif action == "reopen":
        record["workflow_stage"] = steps[0]
        record["status"] = steps[0]
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported workflow action.")

    record["owner"] = actor["name"]
    record["updated_at"] = _utc_timestamp()
    _save_state_payload(db, state)
    _write_audit_log(db, module, record, action, actor, note)
    return _enrich_record(module, record, actor["role"])


def role_directory_payload() -> dict:
    return {"roles": ROLE_DIRECTORY, "demo_users": DEMO_USERS}