from datetime import datetime

from models import ERPState, User

MASTER_BLUEPRINT = {'system': {'name': 'Functional ERP', 'description': 'Runtime verification'},
 'modules': [{'id': 'sales',
              'path': 'sales',
              'name': 'Sales',
              'summary': 'Sales workspace',
              'entity_name': 'Order',
              'form_fields': [{'name': 'customer_name',
                               'label': 'Customer Name',
                               'type': 'VARCHAR(255)',
                               'required': False},
                              {'name': 'amount', 'label': 'Amount', 'type': 'VARCHAR(255)', 'required': False},
                              {'name': 'due_date', 'label': 'Due Date', 'type': 'VARCHAR(255)', 'required': False}],
              'workflows': [{'name': 'Quote to cash', 'steps': ['Draft', 'Review', 'Approve', 'Complete']}]}],
 'roles': [{'id': 'administrator', 'name': 'Administrator', 'permissions': ['manage', 'approve']}]}
ROLE_DIRECTORY = [{'id': 'administrator', 'name': 'Administrator', 'permissions': ['manage', 'approve']}]
DEMO_USERS = [{'id': '1',
  'name': 'Administrator Demo',
  'role': 'Administrator',
  'email': 'administrator@demo.local',
  'password': 'administrator123'}]


def _seed_record(module: dict, record_index: int) -> dict:
    values = {}
    for field in module.get("form_fields", []):
        name = field["name"]
        lowered = name.lower()
        if "email" in lowered:
            values[name] = f"{module['id']}.{record_index}@demo.local"
        elif "date" in lowered:
            values[name] = f"2026-04-{10 + record_index:02d}"
        elif "amount" in lowered or "price" in lowered or "cost" in lowered:
            values[name] = str(1250 * record_index)
        elif "qty" in lowered or "quantity" in lowered:
            values[name] = str(10 * record_index)
        elif "phone" in lowered:
            values[name] = f"+1-555-010{record_index}"
        elif lowered in {"name", "title", "subject"}:
            values[name] = f"{module['name']} {record_index}"
        else:
            values[name] = f"{field['label']} {record_index}"

    workflow_steps = (module.get("workflows") or [{"steps": ["Draft", "Review", "Approve", "Complete"]}])[0].get("steps") or ["Draft", "Review", "Approve", "Complete"]
    stage = workflow_steps[min(record_index - 1, len(workflow_steps) - 1)]
    return {
        "id": f"{module['id']}-{record_index:03d}",
        "title": values.get("name") or values.get("title") or f"{module['name']} record {record_index}",
        "status": stage,
        "workflow_stage": stage,
        "owner": "Automation Queue" if record_index == 1 else "Operations Desk",
        "updated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "values": values,
    }


def _initial_state_payload() -> dict:
    payload = {"modules": {}}
    for module in MASTER_BLUEPRINT.get("modules", []):
        records = [_seed_record(module, 1), _seed_record(module, 2), _seed_record(module, 3)]
        payload["modules"][module["id"]] = {"sequence": len(records), "records": records}
    return payload


def seed_system(db):
    if db.query(User).count() == 0:
        for user in DEMO_USERS:
            db.add(
                User(
                    id=user["id"],
                    name=user["name"],
                    email=user["email"],
                    role=user["role"],
                    password=user["password"],
                    active=True,
                )
            )
        db.commit()

    if not db.query(ERPState).filter(ERPState.id == 1).first():
        db.add(ERPState(id=1, payload=_initial_state_payload()))
        db.commit()
