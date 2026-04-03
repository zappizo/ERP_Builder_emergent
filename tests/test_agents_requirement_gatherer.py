import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agents


ANALYSIS = {
    "business_type": "repair services",
    "industry": "electronics",
    "scale": "small",
    "suggested_modules": ["CRM", "Inventory Management", "Finance & Accounting"],
    "key_requirements": ["customer intake", "job tracking", "inventory", "billing"],
    "summary": "ERP for a small repair business.",
}


def test_requirement_gatherer_keeps_clarifying_when_gaps_remain_even_after_multiple_answers(monkeypatch):
    conversation_history = [
        {"role": "user", "content": "Build me an ERP for an electronics repair shop."},
        {"role": "assistant", "content": "What should happen after a device is received?"},
        {"role": "user", "content": "We create a job card and assign a technician."},
        {"role": "assistant", "content": "Who approves billing and completion?"},
        {"role": "user", "content": "The service manager approves billing."},
    ]

    async def fake_call_llm(messages, temperature=0.7, max_tokens=4000, timeout=None, model_group="default"):
        return json.dumps(
            {
                "complete": False,
                "question": "What reports and dashboards do you need for the service manager?",
                "current_module": "Finance & Accounting",
                "progress_summary": {"captured": ["job cards", "technician assignment", "billing approval"]},
                "completeness_score": 0.78,
                "missing_topics": ["dashboards, KPIs, and reports"],
            }
        )

    monkeypatch.setattr(agents, "call_llm", fake_call_llm)

    result = asyncio.run(agents.requirement_gatherer(ANALYSIS, conversation_history))

    assert result["complete"] is False
    assert result["question"] == "What reports and dashboards do you need for the service manager?"
    assert result["assistant_response"].endswith(result["question"])
    assert result["progress_summary"] == "captured: job cards, technician assignment, billing approval"
    assert result["completeness_score"] <= 0.84
    assert result["missing_topics"]


def test_requirement_gatherer_builds_dynamic_fallback_when_model_fails(monkeypatch):
    conversation_history = [
        {"role": "user", "content": "We need an ERP for device repairs with inventory tracking and billing."},
    ]

    async def fake_call_llm(messages, temperature=0.7, max_tokens=4000, timeout=None, model_group="default"):
        raise RuntimeError("analysis model unavailable")

    monkeypatch.setattr(agents, "call_llm", fake_call_llm)

    result = asyncio.run(agents.requirement_gatherer(ANALYSIS, conversation_history))

    assert result["complete"] is False
    assert result["current_module"] in {"CRM", "Inventory Management", "Finance & Accounting", "Cross-functional"}
    assert result["question"]
    assert result["assistant_response"].endswith(result["question"])
    assert result["missing_topics"]
    assert result["captured_topics"]


def test_requirement_gatherer_backfills_requirements_when_context_is_rich(monkeypatch):
    conversation_history = [
        {"role": "user", "content": "Build an ERP for an electronics repair shop with customer intake and billing."},
        {"role": "assistant", "content": "How does the workflow move after intake?"},
        {"role": "user", "content": "Jobs move from intake to diagnosis, approval, repair, QA, and delivery."},
        {"role": "assistant", "content": "Who uses the system and what should they see?"},
        {"role": "user", "content": "Front desk, technicians, service managers, and finance staff need role-based access."},
        {"role": "assistant", "content": "What integrations or reporting do you need?"},
        {"role": "user", "content": "We need email and WhatsApp updates, dashboards, technician productivity reports, and audit logs."},
    ]

    async def fake_call_llm(messages, temperature=0.7, max_tokens=4000, timeout=None, model_group="default"):
        return json.dumps(
            {
                "complete": True,
                "assistant_response": "I have enough detail to generate the ERP.",
                "completeness_score": 0.92,
            }
        )

    monkeypatch.setattr(agents, "call_llm", fake_call_llm)

    result = asyncio.run(agents.requirement_gatherer(ANALYSIS, conversation_history))

    assert result["complete"] is True
    assert isinstance(result["requirements"], dict)
    assert result["requirements"]["business_type"] == "repair services"
    assert result["requirements"]["general_requirements"]["integrations"]
    assert result["requirements"]["general_requirements"]["reporting_needs"]
    assert result["requirements"]["general_requirements"]["access_requirements"]


def test_apply_modification_enriches_requirements_for_workflow_actions():
    base_requirements = {
        "business_type": "repair services",
        "industry": "electronics",
        "scale": "small",
        "modules": [
            {
                "name": "CRM",
                "description": "Customer management",
                "features": ["Lead capture"],
                "entities": ["Customer"],
                "workflows": [],
                "user_roles": ["Admin"],
            }
        ],
        "general_requirements": {"integrations": [], "special_needs": []},
    }

    updated = agents._apply_modification(
        base_requirements,
        "Add approval buttons, dashboard alerts, and role-based permissions to CRM.",
    )

    assert updated["general_requirements"]["change_requests"]
    assert "Granular role-based permissions" in updated["general_requirements"]["access_requirements"]
    assert "Dashboard and reporting workspace" in updated["modules"][0]["features"]
    assert "Approval Flow" in updated["modules"][0]["workflows"]
    assert "Interactive workflow action buttons" in updated["modules"][0]["features"]
