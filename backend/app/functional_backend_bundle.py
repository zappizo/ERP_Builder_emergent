from __future__ import annotations

import re
from pprint import pformat
from textwrap import dedent
from typing import Any


def _slugify(value: Any, fallback: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return candidate or fallback


def _normalize_roles(master_json: dict[str, Any]) -> list[dict[str, Any]]:
    raw_roles = ((master_json.get("auth") or {}).get("roles") or []) if isinstance(master_json, dict) else []
    permissions_map = ((master_json.get("auth") or {}).get("permissions") or {}) if isinstance(master_json, dict) else {}
    roles: list[dict[str, Any]] = []

    for index, raw_role in enumerate(raw_roles, start=1):
        if isinstance(raw_role, dict):
            name = str(raw_role.get("name") or raw_role.get("id") or f"Role {index}")
            raw_permissions = raw_role.get("permissions") or permissions_map.get(_slugify(name, f"role-{index}")) or []
        else:
            name = str(raw_role or f"Role {index}")
            raw_permissions = permissions_map.get(_slugify(name, f"role-{index}")) or []
        roles.append(
            {
                "id": _slugify(name, f"role-{index}"),
                "name": name,
                "permissions": [str(permission) for permission in raw_permissions if permission not in (None, "", [], {})],
            }
        )

    if roles:
        return roles

    return [
        {"id": "administrator", "name": "Administrator", "permissions": ["manage", "approve", "configure"]},
        {"id": "operations-manager", "name": "Operations Manager", "permissions": ["view", "create", "update", "approve"]},
        {"id": "team-member", "name": "Team Member", "permissions": ["view", "create", "update"]},
    ]


def _normalize_modules(master_json: dict[str, Any]) -> list[dict[str, Any]]:
    raw_modules = master_json.get("modules", []) if isinstance(master_json, dict) else []
    modules: list[dict[str, Any]] = []

    for index, raw_module in enumerate(raw_modules, start=1):
        if not isinstance(raw_module, dict):
            continue

        name = str(raw_module.get("name") or raw_module.get("id") or f"Module {index}")
        module_id = _slugify(raw_module.get("id") or name, f"module-{index}")
        entities = raw_module.get("entities") or []
        entity = entities[0] if entities and isinstance(entities[0], dict) else {"name": "Record", "fields": []}
        raw_fields = entity.get("fields") or []
        form_fields = []
        for field_index, field in enumerate(raw_fields, start=1):
            if isinstance(field, dict):
                field_name = str(field.get("name") or f"field_{field_index}")
                field_type = str(field.get("type") or "VARCHAR(255)")
                required = bool(field.get("required", False))
            else:
                field_name = str(field or f"field_{field_index}")
                field_type = "VARCHAR(255)"
                required = False
            if field_name in {"id", "created_at", "updated_at"}:
                continue
            form_fields.append(
                {
                    "name": field_name,
                    "label": field_name.replace("_", " ").title(),
                    "type": field_type,
                    "required": required,
                }
            )

        workflows = []
        for workflow in raw_module.get("workflows") or []:
            if isinstance(workflow, dict):
                steps = []
                for step in workflow.get("steps") or []:
                    if isinstance(step, dict):
                        steps.append(str(step.get("name") or step.get("label") or "Step"))
                    elif step not in (None, "", [], {}):
                        steps.append(str(step))
                workflows.append({"name": str(workflow.get("name") or "Workflow"), "steps": steps})
            elif workflow not in (None, "", [], {}):
                workflows.append({"name": str(workflow), "steps": [str(workflow)]})

        modules.append(
            {
                "id": module_id,
                "path": _slugify(raw_module.get("path") or module_id, module_id),
                "name": name,
                "summary": str(raw_module.get("description") or f"{name} operational workspace"),
                "entity_name": str(entity.get("name") or "Record"),
                "form_fields": form_fields[:6],
                "workflows": workflows[:3],
            }
        )

    if modules:
        return modules

    return [
        {
            "id": "operations",
            "path": "operations",
            "name": "Operations",
            "summary": "Operations workspace",
            "entity_name": "Record",
            "form_fields": [
                {"name": "name", "label": "Name", "type": "VARCHAR(255)", "required": True},
                {"name": "status", "label": "Status", "type": "VARCHAR(64)", "required": False},
            ],
            "workflows": [{"name": "Review request", "steps": ["Draft", "Review", "Approve", "Complete"]}],
        }
    ]


def _build_demo_users(roles: list[dict[str, Any]]) -> list[dict[str, str]]:
    demo_users: list[dict[str, str]] = []
    used_slugs: set[str] = set()
    for index, role in enumerate(roles, start=1):
        slug_base = role["id"]
        slug = slug_base
        suffix = 2
        while slug in used_slugs:
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        used_slugs.add(slug)
        demo_users.append(
            {
                "id": str(index),
                "name": f"{role['name']} Demo",
                "role": role["name"],
                "email": f"{slug}@demo.local",
                "password": f"{slug}123",
            }
        )
    return demo_users


def build_functional_backend_bundle(master_json: dict[str, Any]) -> dict[str, Any]:
    roles = _normalize_roles(master_json)
    modules = _normalize_modules(master_json)
    demo_users = _build_demo_users(roles)
    system_name = str((master_json.get("system") or {}).get("name") or "Generated ERP API")

    blueprint_literal = pformat({"system": master_json.get("system", {}), "modules": modules, "roles": roles}, width=120, sort_dicts=False)
    roles_literal = pformat(roles, width=120, sort_dicts=False)
    demo_users_literal = pformat(demo_users, width=120, sort_dicts=False)

    main_py = dedent(
        f"""
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


        app = FastAPI(title={system_name!r}, lifespan=lifespan)
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
            return {{"status": "ok", "system": {system_name!r}}}
        """
    ).strip()

    database_py = dedent(
        """
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import declarative_base, sessionmaker

        DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./generated_app.db")
        connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

        engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
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
    ).strip()

    models_py = dedent(
        """
        from datetime import datetime

        from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

        from database import Base


        class User(Base):
            __tablename__ = "users"

            id = Column(String, primary_key=True)
            name = Column(String, nullable=False)
            email = Column(String, nullable=False, unique=True, index=True)
            role = Column(String, nullable=False, index=True)
            password = Column(String, nullable=False)
            active = Column(Boolean, nullable=False, default=True)


        class ERPState(Base):
            __tablename__ = "erp_state"

            id = Column(Integer, primary_key=True)
            payload = Column(JSON, nullable=False)
            updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


        class AuditLog(Base):
            __tablename__ = "audit_logs"

            id = Column(Integer, primary_key=True, autoincrement=True)
            module_id = Column(String, nullable=False, index=True)
            record_id = Column(String, nullable=False, index=True)
            action = Column(String, nullable=False)
            actor_id = Column(String, nullable=False)
            actor_name = Column(String, nullable=False)
            actor_role = Column(String, nullable=False)
            message = Column(Text, nullable=False)
            created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
        """
    ).strip()

    schemas_py = dedent(
        """
        from __future__ import annotations

        from typing import Any

        from pydantic import BaseModel, Field


        class LoginRequest(BaseModel):
            email: str
            password: str


        class RecordCreateRequest(BaseModel):
            values: dict[str, Any] = Field(default_factory=dict)
            note: str = ""


        class RecordActionRequest(BaseModel):
            action: str
            note: str = ""


        class AuthUserRead(BaseModel):
            id: str
            name: str
            email: str
            role: str


        class LoginResponse(BaseModel):
            user: AuthUserRead
            headers: dict[str, str]
            message: str
        """
    ).strip()

    security_py = dedent(
        """
        from fastapi import Depends, Header, HTTPException, status
        from sqlalchemy.orm import Session

        from database import get_db
        from models import User


        def get_current_user(
            x_user_id: str | None = Header(default=None, alias="x-user-id"),
            x_role: str | None = Header(default=None, alias="x-role"),
            db: Session = Depends(get_db),
        ) -> dict[str, str]:
            if not x_user_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing x-user-id header.")

            user = db.query(User).filter(User.id == x_user_id, User.active.is_(True)).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user session.")

            if x_role and x_role.strip().lower() != user.role.strip().lower():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role header does not match the user.")

            return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
        """
    ).strip()

    seed_py = (
        "from datetime import datetime\n\n"
        "from models import ERPState, User\n\n"
        f"MASTER_BLUEPRINT = {blueprint_literal}\n"
        f"ROLE_DIRECTORY = {roles_literal}\n"
        f"DEMO_USERS = {demo_users_literal}\n\n\n"
        "def _seed_record(module: dict, record_index: int) -> dict:\n"
        "    values = {}\n"
        "    for field in module.get(\"form_fields\", []):\n"
        "        name = field[\"name\"]\n"
        "        lowered = name.lower()\n"
        "        if \"email\" in lowered:\n"
        "            values[name] = f\"{module['id']}.{record_index}@demo.local\"\n"
        "        elif \"date\" in lowered:\n"
        "            values[name] = f\"2026-04-{10 + record_index:02d}\"\n"
        "        elif \"amount\" in lowered or \"price\" in lowered or \"cost\" in lowered:\n"
        "            values[name] = str(1250 * record_index)\n"
        "        elif \"qty\" in lowered or \"quantity\" in lowered:\n"
        "            values[name] = str(10 * record_index)\n"
        "        elif \"phone\" in lowered:\n"
        "            values[name] = f\"+1-555-010{record_index}\"\n"
        "        elif lowered in {\"name\", \"title\", \"subject\"}:\n"
        "            values[name] = f\"{module['name']} {record_index}\"\n"
        "        else:\n"
        "            values[name] = f\"{field['label']} {record_index}\"\n\n"
        "    workflow_steps = (module.get(\"workflows\") or [{\"steps\": [\"Draft\", \"Review\", \"Approve\", \"Complete\"]}])[0].get(\"steps\") or [\"Draft\", \"Review\", \"Approve\", \"Complete\"]\n"
        "    stage = workflow_steps[min(record_index - 1, len(workflow_steps) - 1)]\n"
        "    return {\n"
        "        \"id\": f\"{module['id']}-{record_index:03d}\",\n"
        "        \"title\": values.get(\"name\") or values.get(\"title\") or f\"{module['name']} record {record_index}\",\n"
        "        \"status\": stage,\n"
        "        \"workflow_stage\": stage,\n"
        "        \"owner\": \"Automation Queue\" if record_index == 1 else \"Operations Desk\",\n"
        "        \"updated_at\": datetime.utcnow().replace(microsecond=0).isoformat() + \"Z\",\n"
        "        \"values\": values,\n"
        "    }\n\n\n"
        "def _initial_state_payload() -> dict:\n"
        "    payload = {\"modules\": {}}\n"
        "    for module in MASTER_BLUEPRINT.get(\"modules\", []):\n"
        "        records = [_seed_record(module, 1), _seed_record(module, 2), _seed_record(module, 3)]\n"
        "        payload[\"modules\"][module[\"id\"]] = {\"sequence\": len(records), \"records\": records}\n"
        "    return payload\n\n\n"
        "def seed_system(db):\n"
        "    if db.query(User).count() == 0:\n"
        "        for user in DEMO_USERS:\n"
        "            db.add(\n"
        "                User(\n"
        "                    id=user[\"id\"],\n"
        "                    name=user[\"name\"],\n"
        "                    email=user[\"email\"],\n"
        "                    role=user[\"role\"],\n"
        "                    password=user[\"password\"],\n"
        "                    active=True,\n"
        "                )\n"
        "            )\n"
        "        db.commit()\n\n"
        "    if not db.query(ERPState).filter(ERPState.id == 1).first():\n"
        "        db.add(ERPState(id=1, payload=_initial_state_payload()))\n"
        "        db.commit()\n"
    )

    services_py = dedent(
        """
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
        """
    ).strip()

    auth_routes_py = dedent(
        """
        from fastapi import APIRouter, Depends, HTTPException, status
        from sqlalchemy.orm import Session

        from database import get_db
        from models import User
        from schemas import LoginRequest, LoginResponse
        from security import get_current_user
        from services import serialize_user

        router = APIRouter(tags=["auth"])


        @router.post("/login", response_model=LoginResponse)
        def login(payload: LoginRequest, db: Session = Depends(get_db)):
            user = db.query(User).filter(User.email == payload.email, User.active.is_(True)).first()
            if not user or user.password != payload.password:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid demo credentials.")

            headers = {"x-user-id": user.id, "x-role": user.role}
            return LoginResponse(user=serialize_user(user), headers=headers, message="Login successful.")


        @router.get("/me")
        def me(current_user: dict = Depends(get_current_user)):
            return {"user": current_user}
        """
    ).strip()

    meta_routes_py = dedent(
        """
        from fastapi import APIRouter

        from services import role_directory_payload

        router = APIRouter(tags=["meta"])


        @router.get("/roles")
        def roles():
            return role_directory_payload()
        """
    ).strip()

    dashboard_routes_py = dedent(
        """
        from fastapi import APIRouter, Depends
        from sqlalchemy.orm import Session

        from database import get_db
        from security import get_current_user
        from services import dashboard_payload, recent_activity

        router = APIRouter(tags=["dashboard"])


        @router.get("/dashboard")
        def dashboard(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
            return dashboard_payload(db, current_user)


        @router.get("/workflow/events")
        def workflow_events(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
            return recent_activity(db, limit=12)
        """
    ).strip()

    module_routes_py = dedent(
        """
        from fastapi import APIRouter, Depends
        from sqlalchemy.orm import Session

        from database import get_db
        from schemas import RecordActionRequest, RecordCreateRequest
        from security import get_current_user
        from services import create_record, module_catalog, module_workspace_payload, run_record_action

        router = APIRouter(tags=["modules"])


        @router.get("/modules")
        def list_modules(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
            return {"modules": module_catalog(db, current_user["role"])}


        @router.get("/modules/{module_id}")
        def module_summary(module_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
            return module_workspace_payload(db, module_id, current_user)


        @router.post("/modules/{module_id}/records")
        def create_module_record(
            module_id: str,
            payload: RecordCreateRequest,
            current_user: dict = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
            return create_record(db, module_id, payload.model_dump(), current_user)


        @router.post("/modules/{module_id}/records/{record_id}/actions")
        def apply_record_action(
            module_id: str,
            record_id: str,
            payload: RecordActionRequest,
            current_user: dict = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
            return run_record_action(db, module_id, record_id, payload.action, current_user, payload.note)
        """
    ).strip()
    package_init_py = '"""Generated ERP route package."""\n'

    return {
        "files": [
            {"path": "main.py", "language": "python", "content": main_py},
            {"path": "database.py", "language": "python", "content": database_py},
            {"path": "models.py", "language": "python", "content": models_py},
            {"path": "schemas.py", "language": "python", "content": schemas_py},
            {"path": "security.py", "language": "python", "content": security_py},
            {"path": "seed.py", "language": "python", "content": seed_py},
            {"path": "services.py", "language": "python", "content": services_py},
            {"path": "routes/__init__.py", "language": "python", "content": package_init_py},
            {"path": "routes/auth.py", "language": "python", "content": auth_routes_py},
            {"path": "routes/meta.py", "language": "python", "content": meta_routes_py},
            {"path": "routes/dashboard.py", "language": "python", "content": dashboard_routes_py},
            {"path": "routes/modules.py", "language": "python", "content": module_routes_py},
        ],
        "dependencies": {
            "fastapi": ">=0.110.0",
            "sqlalchemy": ">=2.0.0",
            "pydantic": ">=2.0.0",
        },
    }
