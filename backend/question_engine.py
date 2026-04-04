"""
Question Engine for Zappizo ERP Architect.

Controls the AI's requirement-gathering behaviour:
- Tracks which coverage areas have been explored
- Detects user intent (skip / confirm / normal answer)
- Calculates per-area completeness from conversation history
- Provides coverage context to the LLM so it asks non-redundant questions
- Guards against premature completion when requirements are insufficient
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────
# COVERAGE AREAS — the engine ensures ALL areas are explored
# ───────────────────────────────────────────────────────────────────

COVERAGE_AREAS: dict[str, dict[str, Any]] = {
    "business_model": {
        "label": "Organization & Business Model",
        "description": "Company structure, revenue model, business type, scale, locations",
        "keywords": [
            "business", "company", "revenue", "model", "b2b", "b2c", "location",
            "branch", "franchise", "structure", "founded", "team", "size",
            "startup", "established", "industry", "sector", "market",
        ],
        "weight": 1.0,
        "min_depth": 2,
    },
    "sales_crm": {
        "label": "Sales & CRM",
        "description": "Lead management, quotations, sales orders, invoicing, customer management",
        "keywords": [
            "sales", "lead", "quotation", "quote", "order", "invoice", "customer",
            "client", "pricing", "discount", "crm", "pipeline", "deal", "revenue",
            "billing", "payment", "credit", "receivable",
        ],
        "weight": 1.0,
        "min_depth": 2,
    },
    "procurement": {
        "label": "Procurement & Vendor Management",
        "description": "Purchase requisitions, POs, vendor management, goods receipt",
        "keywords": [
            "purchase", "vendor", "supplier", "procurement", "requisition", "po",
            "goods receipt", "grn", "sourcing", "rfq", "tender", "buying",
        ],
        "weight": 0.9,
        "min_depth": 2,
    },
    "inventory_warehouse": {
        "label": "Inventory & Warehouse",
        "description": "Stock management, warehousing, transfers, batch tracking",
        "keywords": [
            "inventory", "stock", "warehouse", "storage", "batch", "serial",
            "fifo", "lifo", "reorder", "bin", "rack", "transfer", "count",
            "valuation", "item", "sku", "product",
        ],
        "weight": 0.9,
        "min_depth": 2,
    },
    "manufacturing": {
        "label": "Manufacturing & Production",
        "description": "BOM, production planning, work orders, quality control",
        "keywords": [
            "manufacturing", "production", "bom", "bill of material", "work order",
            "assembly", "factory", "plant", "machine", "routing", "mrp",
            "capacity", "quality", "inspection", "defect", "scrap",
        ],
        "weight": 0.8,
        "min_depth": 2,
    },
    "finance_accounting": {
        "label": "Finance & Accounting",
        "description": "GL, AP, AR, tax, financial reporting, budgeting",
        "keywords": [
            "finance", "accounting", "ledger", "tax", "gst", "journal",
            "payable", "receivable", "budget", "cost", "expense", "profit",
            "loss", "balance", "reconciliation", "audit", "compliance",
        ],
        "weight": 1.0,
        "min_depth": 2,
    },
    "hr_users": {
        "label": "HR & User Roles",
        "description": "Employees, departments, payroll, roles, permissions",
        "keywords": [
            "hr", "employee", "staff", "department", "payroll", "salary",
            "leave", "attendance", "role", "permission", "access", "admin",
            "manager", "operator", "user",
        ],
        "weight": 0.8,
        "min_depth": 1,
    },
    "approvals_exceptions": {
        "label": "Approvals & Exception Handling",
        "description": "Approval workflows, escalation, cancellations, returns, refunds",
        "keywords": [
            "approval", "approve", "reject", "escalation", "exception",
            "cancel", "return", "refund", "dispute", "hierarchy", "authority",
            "limit", "override", "hold",
        ],
        "weight": 0.9,
        "min_depth": 1,
    },
    "reporting_analytics": {
        "label": "Reporting & Analytics",
        "description": "Dashboards, reports, KPIs, data analysis needs",
        "keywords": [
            "report", "dashboard", "analytics", "kpi", "metric", "chart",
            "graph", "insight", "data", "trend", "forecast", "analysis",
            "summary", "export", "pdf", "excel",
        ],
        "weight": 0.7,
        "min_depth": 1,
    },
    "integrations": {
        "label": "Integrations & External Tools",
        "description": "Third-party APIs, email, SMS, payment gateways, e-commerce",
        "keywords": [
            "integration", "api", "connect", "sync", "email", "sms",
            "whatsapp", "payment", "gateway", "shopify", "woocommerce",
            "tally", "quickbooks", "excel", "csv", "barcode", "scanner",
            "mobile", "app",
        ],
        "weight": 0.7,
        "min_depth": 1,
    },
    "compliance_audit": {
        "label": "Compliance & Audit Requirements",
        "description": "Regulatory compliance, audit trails, data security",
        "keywords": [
            "compliance", "regulation", "audit", "trail", "log", "security",
            "gdpr", "hipaa", "fda", "iso", "certification", "standard",
            "backup", "encryption", "data protection",
        ],
        "weight": 0.6,
        "min_depth": 1,
    },
    "pain_points": {
        "label": "Current Problems & Pain Points",
        "description": "Bottlenecks, frustrations, manual processes, errors in current system",
        "keywords": [
            "problem", "pain", "issue", "challenge", "bottleneck", "frustrat",
            "manual", "error", "mistake", "slow", "delay", "inefficient",
            "workaround", "duplicate", "missing", "lost", "broken", "struggle",
            "difficult", "complicated", "spreadsheet", "excel",
        ],
        "weight": 1.0,
        "min_depth": 1,
    },
}

# Minimum overall coverage percentage to consider requirements "sufficient"
MIN_COMPLETION_THRESHOLD = 0.60

# ───────────────────────────────────────────────────────────────────
# SKIP / STOP INTENT DETECTION
# ───────────────────────────────────────────────────────────────────

SKIP_PATTERNS = [
    r"\b(skip|stop|enough|done|proceed|move on|no more|don'?t ask|thats? (?:it|all|enough)|just (?:build|generate|create|make)|finish)\b",
    r"\b(i'?m done|that'?s? sufficient|let'?s? go|go ahead|start building|wrap up|complete it|finalize)\b",
    r"\b(no need|not required|doesn'?t matter|not important|i don'?t (?:know|care)|whatever you think)\b",
]

CONFIRM_SKIP_PATTERNS = [
    r"\b(yes|yeah|yep|sure|confirm|ok|okay|go ahead|proceed|absolutely|definitely)\b",
    r"\b(i'?m sure|positive|no problem|that'?s? fine|do it|yes proceed)\b",
]


def detect_user_intent(message: str) -> str:
    """Detect the user's intent from their message.

    Returns:
        "skip"    — User wants to stop questioning (first time)
        "confirm" — User confirms they want to skip (after being warned)
        "answer"  — Normal answer to questions
    """
    lowered = message.lower().strip()

    # Very short confirmations after a skip warning
    if len(lowered.split()) <= 4:
        for pattern in CONFIRM_SKIP_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE):
                return "confirm"

    # Skip / stop intent
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            return "skip"

    return "answer"


# ───────────────────────────────────────────────────────────────────
# COVERAGE ANALYSIS — Scores what has been discussed
# ───────────────────────────────────────────────────────────────────


def _count_keyword_hits(text: str, keywords: list[str]) -> int:
    """Count how many unique keywords appear in the text."""
    lowered = text.lower()
    return sum(1 for kw in keywords if kw in lowered)


def analyze_coverage(conversation_history: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """Analyze the conversation to determine coverage scores per area.

    Returns a dict keyed by area_id with:
        - score: 0.0 to 1.0
        - hits: number of keyword matches
        - status: "not_started" | "partial" | "sufficient"
        - mentioned_in: number of messages mentioning this area
    """
    # Combine all messages for analysis
    all_user_text = " ".join(
        msg["content"] for msg in conversation_history if msg.get("role") == "user"
    )
    all_assistant_text = " ".join(
        msg["content"] for msg in conversation_history if msg.get("role") == "assistant"
    )
    combined = all_user_text + " " + all_assistant_text
    msg_count = len([m for m in conversation_history if m.get("role") == "user"])

    coverage = {}
    for area_id, area in COVERAGE_AREAS.items():
        keywords = area["keywords"]
        min_depth = area["min_depth"]

        # Count keyword hits in user messages specifically
        user_hits = _count_keyword_hits(all_user_text, keywords)
        # Count how many user messages mention this area
        mentioned_in = sum(
            1 for msg in conversation_history
            if msg.get("role") == "user" and _count_keyword_hits(msg["content"], keywords) > 0
        )

        # Score calculation
        if user_hits == 0:
            score = 0.0
            status = "not_started"
        elif mentioned_in < min_depth:
            score = min(0.5, user_hits / (len(keywords) * 0.4))
            status = "partial"
        else:
            raw = user_hits / (len(keywords) * 0.3)
            score = min(1.0, raw)
            status = "sufficient" if score >= 0.6 else "partial"

        coverage[area_id] = {
            "label": area["label"],
            "score": round(score, 2),
            "hits": user_hits,
            "mentioned_in": mentioned_in,
            "status": status,
            "weight": area["weight"],
        }

    return coverage


def calculate_overall_completeness(coverage: dict[str, dict[str, Any]]) -> float:
    """Calculate a weighted overall completeness score from area coverage."""
    total_weight = sum(area["weight"] for area in coverage.values())
    if total_weight == 0:
        return 0.0

    weighted_sum = sum(
        area["score"] * area["weight"] for area in coverage.values()
    )
    return round(weighted_sum / total_weight, 2)


def get_uncovered_areas(coverage: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """Return areas that haven't been sufficiently explored."""
    uncovered = []
    for area_id, area in coverage.items():
        if area["status"] in ("not_started", "partial"):
            uncovered.append({
                "id": area_id,
                "label": area["label"],
                "status": area["status"],
                "score": area["score"],
            })

    # Sort: not_started first, then by weight (higher = more important)
    uncovered.sort(
        key=lambda a: (0 if a["status"] == "not_started" else 1, -COVERAGE_AREAS[a["id"]]["weight"])
    )
    return uncovered


# ───────────────────────────────────────────────────────────────────
# COVERAGE CONTEXT for LLM Prompt Injection
# ───────────────────────────────────────────────────────────────────


def build_coverage_context(conversation_history: list[dict[str, str]]) -> str:
    """Build a coverage status summary to inject into the LLM prompt.

    This tells the LLM exactly what has been covered and what's missing
    so it can ask targeted, non-redundant questions.
    """
    coverage = analyze_coverage(conversation_history)
    uncovered = get_uncovered_areas(coverage)
    completeness = calculate_overall_completeness(coverage)

    lines = [
        f"## COVERAGE STATUS (Overall: {int(completeness * 100)}%)",
        "",
        "### Areas Explored:",
    ]

    for area_id, area in coverage.items():
        icon = "✅" if area["status"] == "sufficient" else ("🔶" if area["status"] == "partial" else "❌")
        lines.append(f"  {icon} {area['label']}: {area['status']} ({int(area['score'] * 100)}%)")

    if uncovered:
        lines.append("")
        lines.append("### PRIORITY — Ask About These NEXT:")
        for i, area in enumerate(uncovered[:4], 1):
            config = COVERAGE_AREAS[area["id"]]
            lines.append(f"  {i}. **{area['label']}** — {config['description']}")

    lines.append("")
    lines.append(f"### INSTRUCTIONS:")
    lines.append(f"- Focus your questions on the PRIORITY areas listed above")
    lines.append(f"- Do NOT re-ask about areas marked ✅ sufficient")
    lines.append(f"- For 🔶 partial areas, dig deeper into specifics")
    lines.append(f"- For ❌ not_started areas, ask foundational questions first")
    lines.append(f"- ALWAYS ask about current problems and pain points in each area you explore")

    return "\n".join(lines)


# ───────────────────────────────────────────────────────────────────
# SKIP GUARD — Prevents premature completion
# ───────────────────────────────────────────────────────────────────


def build_skip_warning(coverage: dict[str, dict[str, Any]]) -> str:
    """Build a warning message when user tries to skip but coverage is low."""
    completeness = calculate_overall_completeness(coverage)
    uncovered = get_uncovered_areas(coverage)

    missing_labels = [a["label"] for a in uncovered[:5]]
    missing_list = "\n".join(f"  • {label}" for label in missing_labels)

    return (
        f"⚠️ **Requirements are only {int(completeness * 100)}% complete.** "
        f"The following critical areas haven't been fully explored:\n\n"
        f"{missing_list}\n\n"
        f"Incomplete requirements may result in an ERP system that doesn't match your "
        f"business needs, requiring costly revisions later.\n\n"
        f"**Would you like to continue answering a few more questions?** "
        f"Or type 'proceed anyway' if you'd like to generate with current information."
    )


def should_allow_completion(
    coverage: dict[str, dict[str, Any]],
    msg_count: int,
) -> tuple[bool, str]:
    """Decide whether the requirement gathering can be completed.

    Returns:
        (allowed, reason)
    """
    completeness = calculate_overall_completeness(coverage)

    # Always allow after many rounds
    if msg_count >= 12:
        return True, "Maximum discovery rounds reached"

    # Allow if coverage is sufficient
    if completeness >= MIN_COMPLETION_THRESHOLD:
        return True, f"Coverage is {int(completeness * 100)}%, above threshold"

    # Not enough coverage
    uncovered = get_uncovered_areas(coverage)
    missing = ", ".join(a["label"] for a in uncovered[:3])
    return False, f"Only {int(completeness * 100)}% covered. Missing: {missing}"


# ───────────────────────────────────────────────────────────────────
# QUESTION ENGINE — Main orchestration
# ───────────────────────────────────────────────────────────────────


class QuestionEngine:
    """Stateless question engine that analyzes conversation state and
    controls the gathering flow.

    Usage in services.py:
        engine = QuestionEngine(conversation_history, analysis, gathering_state)
        decision = engine.evaluate(user_message)
    """

    def __init__(
        self,
        conversation_history: list[dict[str, str]],
        analysis: dict[str, Any],
        gathering_state: dict[str, Any] | None = None,
    ):
        self.conversation_history = conversation_history
        self.analysis = analysis
        self.gathering_state = gathering_state or {}
        self.msg_count = len([m for m in conversation_history if m.get("role") == "user"])
        self.coverage = analyze_coverage(conversation_history)
        self.completeness = calculate_overall_completeness(self.coverage)
        self.uncovered = get_uncovered_areas(self.coverage)

    def evaluate(self, user_message: str) -> dict[str, Any]:
        """Evaluate the user's message and decide the next action.

        Returns a decision dict:
        {
            "action": "continue" | "warn_skip" | "force_complete" | "allow_complete",
            "coverage_context": str,  # inject into LLM prompt
            "completeness": float,
            "uncovered_areas": [...],
            "message": str | None,  # override message if action is warn_skip
            "gathering_state": dict,  # updated state to persist
        }
        """
        intent = detect_user_intent(user_message)
        state = dict(self.gathering_state)
        pending_skip = state.get("pending_skip", False)

        # Case 1: User previously got a skip warning, now confirming
        if pending_skip and intent == "confirm":
            state["pending_skip"] = False
            state["user_forced_complete"] = True
            return {
                "action": "allow_complete",
                "coverage_context": build_coverage_context(self.conversation_history),
                "completeness": self.completeness,
                "uncovered_areas": self.uncovered,
                "message": None,
                "gathering_state": state,
            }

        # Case 2: User wants to skip
        if intent == "skip":
            allowed, reason = should_allow_completion(self.coverage, self.msg_count)
            if allowed:
                state["pending_skip"] = False
                state["user_forced_complete"] = True
                return {
                    "action": "allow_complete",
                    "coverage_context": build_coverage_context(self.conversation_history),
                    "completeness": self.completeness,
                    "uncovered_areas": self.uncovered,
                    "message": None,
                    "gathering_state": state,
                }
            else:
                # Warn the user
                state["pending_skip"] = True
                return {
                    "action": "warn_skip",
                    "coverage_context": build_coverage_context(self.conversation_history),
                    "completeness": self.completeness,
                    "uncovered_areas": self.uncovered,
                    "message": build_skip_warning(self.coverage),
                    "gathering_state": state,
                }

        # Case 3: Normal answer — clear any pending skip
        state["pending_skip"] = False

        # Track rounds
        state["rounds_completed"] = state.get("rounds_completed", 0) + 1

        return {
            "action": "continue",
            "coverage_context": build_coverage_context(self.conversation_history),
            "completeness": self.completeness,
            "uncovered_areas": self.uncovered,
            "message": None,
            "gathering_state": state,
        }

    def get_prompt_enhancers(self) -> str:
        """Build the full coverage + instruction context for the LLM prompt."""
        return build_coverage_context(self.conversation_history)
