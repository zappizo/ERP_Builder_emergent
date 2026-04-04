"""
RAG Knowledge Base for Zappizo ERP Architect.

Stores structured domain knowledge (business concepts, ERP modules, workflows)
and provides smart retrieval functions that select relevant context based on
the user's business situation. Retrieved knowledge is injected into LLM prompts
at runtime.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SECTION 1: Business Foundation Knowledge
# ---------------------------------------------------------------------------

BUSINESS_KNOWLEDGE = {
    "BUS_001": {
        "title": "Business Fundamentals",
        "tags": ["business", "basics"],
        "content": {
            "definition": "A business is an organization that delivers value to customers through products or services while generating revenue.",
            "key_elements": [
                "Value Proposition",
                "Customers",
                "Revenue Model",
                "Cost Structure",
                "Operations",
            ],
            "objective": "Maximize profit, efficiency, and customer satisfaction",
            "erp_relevance": "ERP systems exist to integrate and optimize all business elements into a unified system",
        },
    },
    "BUS_002": {
        "title": "Business Processes",
        "tags": ["process", "workflow"],
        "content": {
            "definition": "A business process is a structured set of activities or tasks that produce a specific service or product.",
            "types": [
                "Core Processes (Sales, Production)",
                "Support Processes (HR, IT)",
                "Management Processes (Planning, Strategy)",
            ],
            "characteristics": ["Repeatable", "Measurable", "Goal-oriented"],
            "erp_relevance": "ERP systems digitize, automate, and integrate business processes",
        },
    },
    "BUS_003": {
        "title": "Business Process Mapping",
        "tags": ["process", "mapping"],
        "content": {
            "definition": "Visual representation of workflows showing sequence of tasks, decisions, and data flow",
            "tools": [
                "Flowcharts",
                "BPMN (Business Process Model and Notation)",
                "Swimlane Diagrams",
            ],
            "steps": [
                "Identify process",
                "Define start/end",
                "Map activities",
                "Identify decision points",
                "Validate with stakeholders",
            ],
            "erp_relevance": "Used to design ERP workflows and system logic",
        },
    },
    "BUS_004": {
        "title": "Business Process Reengineering (BPR)",
        "tags": ["optimization", "bpr"],
        "content": {
            "definition": "Radical redesign of business processes to achieve dramatic improvements in performance",
            "principles": [
                "Eliminate unnecessary steps",
                "Automate manual work",
                "Integrate fragmented systems",
                "Focus on outcomes",
            ],
            "metrics": ["Cost reduction", "Time reduction", "Quality improvement"],
            "erp_relevance": "ERP implementation often requires BPR before system deployment",
        },
    },
    "BUS_005": {
        "title": "Business Process Optimization",
        "tags": ["optimization"],
        "content": {
            "definition": "Continuous improvement of business processes for efficiency and effectiveness",
            "techniques": ["Lean", "Six Sigma", "Kaizen", "Automation"],
            "key_focus": ["Reduce waste", "Improve cycle time", "Enhance quality"],
            "erp_relevance": "ERP enables data-driven optimization of processes",
        },
    },
    "BUS_006": {
        "title": "Business Analysis",
        "tags": ["analysis"],
        "content": {
            "definition": "Practice of identifying business needs and determining solutions to business problems",
            "activities": [
                "Requirement gathering",
                "Stakeholder analysis",
                "Process analysis",
                "Solution evaluation",
            ],
            "deliverables": [
                "BRD (Business Requirement Document)",
                "FRD (Functional Requirement Document)",
            ],
            "erp_relevance": "Business analysts define ERP requirements and workflows",
        },
    },
    "BUS_007": {
        "title": "Requirement Types",
        "tags": ["requirements"],
        "content": {
            "types": [
                "Business Requirements",
                "Functional Requirements",
                "Non-functional Requirements",
            ],
            "examples": {
                "functional": "System should generate invoices automatically",
                "non_functional": "System should respond within 2 seconds",
            },
            "erp_relevance": "ERP modules are built based on structured requirements",
        },
    },
    "BUS_008": {
        "title": "Stakeholder Analysis",
        "tags": ["stakeholder"],
        "content": {
            "definition": "Identification and analysis of individuals or groups affected by the system",
            "types": [
                "Internal (Employees, Managers)",
                "External (Customers, Suppliers)",
            ],
            "importance": [
                "Requirement accuracy",
                "System adoption",
                "Conflict resolution",
            ],
            "erp_relevance": "ERP must satisfy multiple stakeholder needs",
        },
    },
    "BUS_009": {
        "title": "KPI and Metrics",
        "tags": ["metrics"],
        "content": {
            "definition": "Key Performance Indicators measure business performance",
            "examples": [
                "Revenue Growth",
                "Inventory Turnover",
                "Order Fulfillment Time",
            ],
            "erp_relevance": "ERP dashboards track KPIs for decision making",
        },
    },
    "BUS_010": {
        "title": "Supply Chain Concept",
        "tags": ["supply_chain"],
        "content": {
            "definition": "Network of organizations involved in producing and delivering a product",
            "components": [
                "Suppliers",
                "Manufacturers",
                "Warehouses",
                "Distribution",
                "Customers",
            ],
            "erp_relevance": "ERP integrates supply chain operations",
        },
    },
    "BUS_011": {
        "title": "Decision Making in Business",
        "tags": ["decision"],
        "content": {
            "types": ["Operational", "Tactical", "Strategic"],
            "approaches": [
                "Data-driven",
                "Experience-based",
                "Predictive analytics",
            ],
            "erp_relevance": "ERP provides real-time data for decision making",
        },
    },
    "BUS_012": {
        "title": "Data in Business",
        "tags": ["data"],
        "content": {
            "types": [
                "Transactional Data",
                "Master Data",
                "Analytical Data",
            ],
            "importance": ["Decision support", "Process tracking", "Forecasting"],
            "erp_relevance": "ERP centralizes all business data",
        },
    },
}

# ---------------------------------------------------------------------------
# SECTION 2: ERP Module Knowledge
# ---------------------------------------------------------------------------

ERP_MODULES = {
    "ERP_INV": {
        "module_name": "Inventory Management",
        "tags": ["inventory", "warehouse", "stock"],
        "description": "Manages stock levels, warehouse operations, and material movement across locations",
        "core_functions": [
            "Stock tracking",
            "Warehouse management",
            "Batch and serial tracking",
            "Stock valuation",
            "Reorder management",
        ],
        "key_entities": [
            "Item",
            "Stock",
            "Warehouse",
            "Stock Movement",
            "Batch",
            "Serial Number",
        ],
        "workflows": [
            "Goods Receipt → Stock Update",
            "Stock Transfer → Warehouse Update",
            "Stock Issue → Deduction",
            "Inventory Adjustment",
        ],
        "decision_logic": [
            "If stock < reorder level → trigger purchase",
            "If multi-warehouse → optimize stock distribution",
            "If perishable goods → apply FIFO/FEFO",
        ],
        "kpis": ["Inventory Turnover", "Stock Accuracy", "Carrying Cost"],
        "integration": [
            "Purchase Module",
            "Sales Module",
            "Production Module",
            "Accounting Module",
        ],
    },
    "ERP_SALES": {
        "module_name": "Sales Management",
        "tags": ["sales", "crm", "orders"],
        "description": "Handles customer orders, pricing, invoicing, and revenue generation",
        "core_functions": [
            "Quotation management",
            "Sales order processing",
            "Pricing and discount management",
            "Invoice generation",
            "Customer management",
        ],
        "key_entities": [
            "Customer",
            "Quotation",
            "Sales Order",
            "Invoice",
            "Payment",
        ],
        "workflows": [
            "Lead → Quotation → Sales Order → Delivery → Invoice → Payment",
            "Order Approval → Dispatch → Billing",
        ],
        "decision_logic": [
            "If credit limit exceeded → block order",
            "If stock unavailable → trigger procurement or backorder",
            "Dynamic pricing based on customer segment",
        ],
        "kpis": ["Sales Revenue", "Conversion Rate", "Order Fulfillment Time"],
        "integration": ["Inventory Module", "Accounting Module", "CRM Module"],
    },
    "ERP_PUR": {
        "module_name": "Purchase Management",
        "tags": ["procurement", "vendor"],
        "description": "Manages procurement of goods and services from vendors",
        "core_functions": [
            "Vendor management",
            "Purchase requisition",
            "Purchase order",
            "Goods receipt",
            "Invoice matching",
        ],
        "key_entities": [
            "Vendor",
            "Purchase Requisition",
            "Purchase Order",
            "Goods Receipt Note",
            "Vendor Invoice",
        ],
        "workflows": [
            "Requisition → Approval → Purchase Order → Goods Receipt → Invoice → Payment",
            "RFQ → Vendor Selection → PO Creation",
        ],
        "decision_logic": [
            "Select vendor based on price, quality, lead time",
            "If urgent demand → bypass approval hierarchy",
            "3-way matching (PO, GRN, Invoice)",
        ],
        "kpis": ["Procurement Cost", "Lead Time", "Vendor Performance"],
        "integration": [
            "Inventory Module",
            "Accounting Module",
            "Production Module",
        ],
    },
    "ERP_PROD": {
        "module_name": "Production / Manufacturing",
        "tags": ["production", "manufacturing"],
        "description": "Handles manufacturing processes, bill of materials, and production planning",
        "core_functions": [
            "Bill of Materials (BOM)",
            "Production planning",
            "Work order management",
            "Routing",
            "Material requirement planning (MRP)",
        ],
        "key_entities": [
            "BOM",
            "Work Order",
            "Routing",
            "Machine",
            "Production Batch",
        ],
        "workflows": [
            "Demand → Production Plan → Work Order → Material Issue → Production → Finished Goods",
            "MRP → Purchase/Production Trigger",
        ],
        "decision_logic": [
            "Make-to-Stock vs Make-to-Order",
            "Capacity planning based on machine load",
            "Optimize production schedule",
        ],
        "kpis": ["Production Efficiency", "Machine Utilization", "Defect Rate"],
        "integration": ["Inventory Module", "Purchase Module", "Sales Module"],
    },
    "ERP_ACC": {
        "module_name": "Accounting & Finance",
        "tags": ["finance", "accounts"],
        "description": "Manages financial transactions, reporting, and compliance",
        "core_functions": [
            "General Ledger",
            "Accounts Payable",
            "Accounts Receivable",
            "Tax management",
            "Financial reporting",
        ],
        "key_entities": [
            "Journal Entry",
            "Ledger",
            "Invoice",
            "Payment",
            "Tax",
        ],
        "workflows": [
            "Transaction → Journal Entry → Ledger Update",
            "Invoice → Payment → Reconciliation",
        ],
        "decision_logic": [
            "Ensure double-entry accounting",
            "Tax calculation based on region",
            "Cash flow management",
        ],
        "kpis": ["Cash Flow", "Profit Margin", "Accounts Receivable Days"],
        "integration": ["Sales Module", "Purchase Module", "Payroll Module"],
    },
    "ERP_HR": {
        "module_name": "Human Resource Management (HRM)",
        "tags": ["hr", "payroll"],
        "description": "Manages employee lifecycle, payroll, and performance",
        "core_functions": [
            "Employee management",
            "Attendance tracking",
            "Payroll processing",
            "Performance management",
            "Recruitment",
        ],
        "key_entities": [
            "Employee",
            "Attendance",
            "Salary",
            "Leave",
            "Performance Review",
        ],
        "workflows": [
            "Hiring → Onboarding → Attendance → Payroll → Performance Review",
            "Leave Request → Approval → Update",
        ],
        "decision_logic": [
            "Salary calculation based on attendance",
            "Leave balance validation",
            "Performance-based incentives",
        ],
        "kpis": ["Employee Productivity", "Attrition Rate", "Payroll Accuracy"],
        "integration": ["Accounting Module"],
    },
    "ERP_CRM": {
        "module_name": "Customer Relationship Management",
        "tags": ["crm", "customer"],
        "description": "Manages customer interactions, leads, and relationships",
        "core_functions": [
            "Lead management",
            "Customer communication tracking",
            "Opportunity management",
            "Sales pipeline tracking",
        ],
        "key_entities": [
            "Lead",
            "Opportunity",
            "Customer Interaction",
            "Campaign",
        ],
        "workflows": [
            "Lead → Qualification → Opportunity → Sales",
            "Campaign → Lead Generation → Conversion",
        ],
        "decision_logic": [
            "Lead scoring based on engagement",
            "Prioritize high-value customers",
            "Automate follow-ups",
        ],
        "kpis": [
            "Lead Conversion Rate",
            "Customer Retention",
            "Customer Lifetime Value",
        ],
        "integration": ["Sales Module"],
    },
    "ERP_ADMIN": {
        "module_name": "Administration & Access Control",
        "tags": ["admin", "security"],
        "description": "Controls user roles, permissions, and system configuration",
        "core_functions": [
            "User management",
            "Role-based access control",
            "System configuration",
            "Audit logs",
        ],
        "key_entities": ["User", "Role", "Permission", "Audit Log"],
        "decision_logic": [
            "Grant access based on role",
            "Restrict sensitive operations",
            "Track user actions",
        ],
        "integration": ["All modules"],
    },
}

# ---------------------------------------------------------------------------
# SECTION 3: ERP Workflow Knowledge
# ---------------------------------------------------------------------------

ERP_WORKFLOWS = {
    "WF_SALES_001": {
        "name": "Order to Cash (O2C)",
        "module": "Sales",
        "description": "Complete lifecycle from customer inquiry to payment realization",
        "steps": [
            "Lead creation",
            "Lead qualification",
            "Quotation creation",
            "Quotation approval",
            "Sales order creation",
            "Stock availability check",
            "Order confirmation",
            "Delivery / Dispatch",
            "Invoice generation",
            "Payment collection",
            "Payment reconciliation",
        ],
        "decision_points": [
            "If lead is qualified → proceed to quotation",
            "If quotation approved → create sales order",
            "If stock available → proceed to delivery",
            "If stock not available → trigger procurement or production",
            "If payment received → close order",
        ],
        "exceptions": [
            "Quotation rejected",
            "Order cancelled",
            "Partial delivery",
            "Payment delay",
        ],
        "data_flow": [
            "Lead → Customer",
            "Quotation → Sales Order",
            "Sales Order → Inventory reservation",
            "Delivery → Invoice",
            "Invoice → Accounting",
        ],
        "integrations": ["Inventory", "Accounting", "CRM"],
    },
    "WF_PROC_001": {
        "name": "Procure to Pay (P2P)",
        "module": "Purchase",
        "description": "Procurement cycle from requisition to vendor payment",
        "steps": [
            "Purchase requisition creation",
            "Requisition approval",
            "Request for quotation (RFQ)",
            "Vendor selection",
            "Purchase order creation",
            "Goods receipt",
            "Quality check",
            "Invoice receipt",
            "3-way matching (PO, GRN, Invoice)",
            "Payment processing",
        ],
        "decision_points": [
            "If requisition approved → proceed to RFQ",
            "If vendor selected → create PO",
            "If goods pass quality → accept stock",
            "If invoice matches PO and GRN → approve payment",
        ],
        "exceptions": [
            "Vendor delay",
            "Rejected materials",
            "Invoice mismatch",
            "Overpricing",
        ],
        "data_flow": [
            "Requisition → Purchase Order",
            "PO → Inventory",
            "GRN → Stock update",
            "Invoice → Accounting",
        ],
        "integrations": ["Inventory", "Accounting", "Production"],
    },
    "WF_INV_001": {
        "name": "Inventory Management Cycle",
        "module": "Inventory",
        "description": "Tracks stock movement and ensures availability",
        "steps": [
            "Stock entry (GRN)",
            "Stock storage",
            "Stock transfer",
            "Stock issue",
            "Stock adjustment",
            "Stock audit",
        ],
        "decision_points": [
            "If stock < reorder level → trigger purchase",
            "If stock discrepancy → perform adjustment",
            "If multiple warehouses → optimize allocation",
        ],
        "exceptions": ["Stock mismatch", "Damaged goods", "Lost inventory"],
        "data_flow": [
            "GRN → Stock ledger",
            "Stock movement → Warehouse update",
            "Stock issue → Sales/Production",
        ],
        "integrations": ["Sales", "Purchase", "Production"],
    },
    "WF_PROD_001": {
        "name": "Production Cycle",
        "module": "Production",
        "description": "Manufacturing process from planning to finished goods",
        "steps": [
            "Demand forecasting",
            "Production planning",
            "MRP calculation",
            "Work order creation",
            "Material issue",
            "Production execution",
            "Quality check",
            "Finished goods entry",
        ],
        "decision_points": [
            "If demand high → increase production",
            "If raw material shortage → trigger procurement",
            "If defect rate high → adjust process",
        ],
        "exceptions": [
            "Machine breakdown",
            "Material shortage",
            "Production delay",
            "Quality failure",
        ],
        "data_flow": [
            "Sales demand → Production plan",
            "MRP → Purchase",
            "Production → Inventory update",
        ],
        "integrations": ["Inventory", "Purchase", "Sales"],
    },
    "WF_ACC_001": {
        "name": "Financial Transaction Cycle",
        "module": "Accounting",
        "description": "Handles financial entries and reporting",
        "steps": [
            "Transaction initiation",
            "Journal entry creation",
            "Ledger posting",
            "Trial balance generation",
            "Financial reporting",
        ],
        "decision_points": [
            "Ensure debit = credit",
            "Apply correct tax rules",
            "Validate transaction category",
        ],
        "exceptions": [
            "Incorrect entries",
            "Tax mismatch",
            "Reconciliation issues",
        ],
        "data_flow": [
            "Invoice → Accounts receivable",
            "Payment → Cash ledger",
            "Expenses → Accounts payable",
        ],
        "integrations": ["Sales", "Purchase", "HR"],
    },
    "WF_HR_001": {
        "name": "Hire to Retire (H2R)",
        "module": "HR",
        "description": "Employee lifecycle management",
        "steps": [
            "Job posting",
            "Candidate selection",
            "Hiring",
            "Onboarding",
            "Attendance tracking",
            "Payroll processing",
            "Performance review",
            "Exit process",
        ],
        "decision_points": [
            "If candidate selected → hire",
            "If attendance recorded → calculate salary",
            "If performance high → incentives",
        ],
        "exceptions": [
            "Employee absenteeism",
            "Payroll errors",
            "Attrition",
        ],
        "data_flow": [
            "Attendance → Payroll",
            "Payroll → Accounting",
            "Performance → HR records",
        ],
        "integrations": ["Accounting"],
    },
    "WF_CRM_001": {
        "name": "Lead to Opportunity",
        "module": "CRM",
        "description": "Customer acquisition process",
        "steps": [
            "Lead generation",
            "Lead capture",
            "Lead qualification",
            "Opportunity creation",
            "Follow-ups",
            "Conversion to customer",
        ],
        "decision_points": [
            "If lead qualified → create opportunity",
            "If engagement high → prioritize lead",
            "If converted → move to sales",
        ],
        "exceptions": [
            "Cold leads",
            "Lost opportunities",
            "Customer drop-off",
        ],
        "data_flow": [
            "Lead → Opportunity",
            "Opportunity → Sales order",
        ],
        "integrations": ["Sales"],
    },
    "WF_LOG_001": {
        "name": "Logistics & Delivery Workflow",
        "module": "Logistics",
        "description": "Manages dispatch and delivery of goods",
        "steps": [
            "Order ready for dispatch",
            "Packing",
            "Shipment planning",
            "Dispatch",
            "Transportation",
            "Delivery confirmation",
        ],
        "decision_points": [
            "Select optimal route",
            "Choose delivery partner",
            "Handle delays",
        ],
        "exceptions": [
            "Delivery delay",
            "Damaged shipment",
            "Lost shipment",
        ],
        "data_flow": [
            "Sales order → Dispatch",
            "Dispatch → Delivery confirmation",
        ],
        "integrations": ["Sales", "Inventory"],
    },
}

# ---------------------------------------------------------------------------
# Module-name to module-ID mapping for fast lookups
# ---------------------------------------------------------------------------

_MODULE_NAME_MAP: dict[str, str] = {}
_MODULE_TAG_MAP: dict[str, list[str]] = {}

for _mod_id, _mod in ERP_MODULES.items():
    _name_lower = _mod["module_name"].lower()
    _MODULE_NAME_MAP[_name_lower] = _mod_id
    for _tag in _mod.get("tags", []):
        _MODULE_TAG_MAP.setdefault(_tag, []).append(_mod_id)

# Workflow-module mapping
_WORKFLOW_MODULE_MAP: dict[str, list[str]] = {}
for _wf_id, _wf in ERP_WORKFLOWS.items():
    _mod_lower = _wf["module"].lower()
    _WORKFLOW_MODULE_MAP.setdefault(_mod_lower, []).append(_wf_id)


# ===================================================================
# RETRIEVAL FUNCTIONS — Called by agents.py to inject into prompts
# ===================================================================


def get_business_foundations_summary() -> str:
    """Return a compact summary of all business foundation concepts.

    Used by the requirement_analyzer to understand business analysis
    frameworks when performing initial analysis.
    """
    lines = ["## ERP BUSINESS FOUNDATION KNOWLEDGE"]
    for bus_id, bus in BUSINESS_KNOWLEDGE.items():
        content = bus["content"]
        definition = content.get("definition", "")
        relevance = content.get("erp_relevance", "")
        lines.append(f"\n### {bus['title']}")
        if definition:
            lines.append(f"- Definition: {definition}")
        if relevance:
            lines.append(f"- ERP Relevance: {relevance}")

        # Include key structured data
        for key in ("key_elements", "types", "activities", "techniques", "approaches", "components"):
            values = content.get(key)
            if values:
                lines.append(f"- {key.replace('_', ' ').title()}: {', '.join(values)}")

    return "\n".join(lines)


def get_all_modules_summary() -> str:
    """Return a compact overview of ALL ERP modules.

    Used by the requirement_analyzer so it can suggest the right
    modules based on real knowledge of what each module does.
    """
    lines = ["## ERP MODULES KNOWLEDGE"]
    for mod_id, mod in ERP_MODULES.items():
        lines.append(f"\n### {mod['module_name']} [{mod_id}]")
        lines.append(f"- Description: {mod['description']}")
        lines.append(f"- Core Functions: {', '.join(mod['core_functions'])}")
        lines.append(f"- Key Entities: {', '.join(mod['key_entities'])}")
        lines.append(f"- KPIs: {', '.join(mod.get('kpis', []))}")
        lines.append(f"- Integrates With: {', '.join(mod.get('integration', []))}")
    return "\n".join(lines)


def _match_module_ids(module_names: list[str]) -> list[str]:
    """Find module IDs matching a list of module name strings."""
    matched = set()
    for name in module_names:
        name_lower = name.lower().strip()
        # Direct name match
        for stored_name, mod_id in _MODULE_NAME_MAP.items():
            if name_lower in stored_name or stored_name in name_lower:
                matched.add(mod_id)
                break
        else:
            # Tag-based match
            for word in name_lower.replace("&", " ").replace("/", " ").split():
                word = word.strip()
                if word in _MODULE_TAG_MAP:
                    matched.update(_MODULE_TAG_MAP[word])
    return list(matched)


def get_relevant_modules_detail(module_names: list[str]) -> str:
    """Return DETAILED knowledge for the specified modules.

    Used by the requirement_gatherer to ask informed, deep questions
    about modules relevant to the user's business.
    """
    mod_ids = _match_module_ids(module_names)
    if not mod_ids:
        # If no match, return all modules
        mod_ids = list(ERP_MODULES.keys())

    lines = ["## DETAILED MODULE KNOWLEDGE (use this to ask informed questions)"]
    for mod_id in mod_ids:
        mod = ERP_MODULES.get(mod_id)
        if not mod:
            continue
        lines.append(f"\n### {mod['module_name']}")
        lines.append(f"Description: {mod['description']}")
        lines.append(f"Core Functions: {', '.join(mod['core_functions'])}")
        lines.append(f"Key Entities: {', '.join(mod['key_entities'])}")
        lines.append(f"Workflows: {', '.join(mod.get('workflows', []))}")
        lines.append("Decision Logic:")
        for dl in mod.get("decision_logic", []):
            lines.append(f"  - {dl}")
        lines.append(f"KPIs to track: {', '.join(mod.get('kpis', []))}")
        lines.append(f"Must integrate with: {', '.join(mod.get('integration', []))}")

    return "\n".join(lines)


def _match_workflow_ids(module_names: list[str]) -> list[str]:
    """Find workflow IDs relevant to the given module names."""
    matched = set()
    for name in module_names:
        name_lower = name.lower().strip()
        for mod_key, wf_ids in _WORKFLOW_MODULE_MAP.items():
            if mod_key in name_lower or name_lower in mod_key:
                matched.update(wf_ids)
                break
        else:
            # Keyword fallback
            for word in name_lower.replace("&", " ").replace("/", " ").split():
                word = word.strip()
                for mod_key, wf_ids in _WORKFLOW_MODULE_MAP.items():
                    if word in mod_key:
                        matched.update(wf_ids)
    return list(matched)


def get_relevant_workflows(module_names: list[str]) -> str:
    """Return detailed workflow knowledge for the specified modules.

    Used by the requirement_gatherer to understand standard business
    workflows and ask about deviations, exceptions, and custom needs.
    """
    wf_ids = _match_workflow_ids(module_names)
    if not wf_ids:
        wf_ids = list(ERP_WORKFLOWS.keys())

    lines = [
        "## STANDARD ERP WORKFLOWS (use these to validate user processes and identify gaps)"
    ]
    for wf_id in wf_ids:
        wf = ERP_WORKFLOWS.get(wf_id)
        if not wf:
            continue
        lines.append(f"\n### {wf['name']} ({wf['module']})")
        lines.append(f"Description: {wf['description']}")
        lines.append("Standard Steps:")
        for i, step in enumerate(wf["steps"], 1):
            lines.append(f"  {i}. {step}")
        lines.append("Decision Points:")
        for dp in wf.get("decision_points", []):
            lines.append(f"  - {dp}")
        lines.append("Common Exceptions:")
        for ex in wf.get("exceptions", []):
            lines.append(f"  - {ex}")
        lines.append("Data Flow:")
        for df in wf.get("data_flow", []):
            lines.append(f"  - {df}")

    return "\n".join(lines)


def get_analyzer_context() -> str:
    """Build the complete knowledge context for the requirement_analyzer.

    Returns business foundations + module overview so the analyzer
    can make informed decisions about what the user's business needs.
    """
    parts = [
        get_business_foundations_summary(),
        "",
        get_all_modules_summary(),
    ]
    return "\n\n".join(parts)


def get_gatherer_context(module_names: list[str]) -> str:
    """Build the complete knowledge context for the requirement_gatherer.

    Returns detailed module knowledge + workflows for the modules
    relevant to the user's business, so the gatherer can ask deep,
    informed questions and validate processes against standards.
    """
    parts = [
        get_relevant_modules_detail(module_names),
        "",
        get_relevant_workflows(module_names),
    ]
    context = "\n\n".join(parts)
    logger.info(
        "Knowledge context built for gatherer: %d modules, %d chars",
        len(module_names),
        len(context),
    )
    return context
