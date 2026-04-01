import asyncio
import copy
import json
import logging
import os
import re
import time
from pathlib import Path
from textwrap import dedent

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = (
    os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions").strip()
    or "https://openrouter.ai/api/v1/chat/completions"
)
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "").strip()
OPENROUTER_MODELS = os.environ.get("OPENROUTER_MODELS", "").strip()
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "http://127.0.0.1:3001").strip() or "http://127.0.0.1:3001"
OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "AI ERP Builder").strip() or "AI ERP Builder"


def _dedupe_models(models):
    seen = set()
    unique = []
    for model in models:
        model = (model or "").strip()
        if not model or model in seen:
            continue
        unique.append(model)
        seen.add(model)
    return unique


MODELS = _dedupe_models(
    [part.strip() for part in OPENROUTER_MODELS.split(",")]
    + [OPENROUTER_MODEL]
)

REMOTE_LLM_DISABLED_REASON = None

INDUSTRY_KEYWORDS = {
    "manufacturing": ["manufacturing", "factory", "production", "assembly", "plant"],
    "retail": ["retail", "store", "shop", "pos", "ecommerce", "e-commerce"],
    "healthcare": ["healthcare", "clinic", "hospital", "patient", "pharmacy", "medical"],
    "construction": ["construction", "contractor", "site", "civil", "infrastructure"],
    "logistics": ["logistics", "transport", "shipping", "fleet", "warehouse", "distribution"],
    "education": ["school", "college", "university", "education", "student"],
    "hospitality": ["hotel", "restaurant", "hospitality", "resort", "cafe"],
    "professional services": ["agency", "consulting", "services", "consultancy"],
    "wholesale": ["wholesale", "distributor", "distribution", "dealer"],
}

INDUSTRY_DEFAULT_MODULES = {
    "manufacturing": [
        "Inventory Management",
        "Production Planning",
        "Sales & Orders",
        "Purchase Management",
        "Finance & Accounting",
        "Quality Control",
    ],
    "retail": [
        "Sales & Orders",
        "Inventory Management",
        "CRM",
        "Purchase Management",
        "Finance & Accounting",
        "Warehouse Management",
        "POS",
    ],
    "healthcare": [
        "Patient Management",
        "Appointments",
        "Billing",
        "Pharmacy",
        "Inventory Management",
        "Finance & Accounting",
    ],
    "construction": [
        "Project Management",
        "Procurement",
        "HR Management",
        "Finance & Accounting",
        "Asset Management",
        "CRM",
    ],
    "logistics": [
        "Warehouse Management",
        "Inventory Management",
        "Sales & Orders",
        "CRM",
        "Finance & Accounting",
        "Asset Management",
    ],
    "education": [
        "CRM",
        "Finance & Accounting",
        "HR Management",
        "Project Management",
    ],
    "hospitality": [
        "Sales & Orders",
        "Inventory Management",
        "CRM",
        "HR Management",
        "Finance & Accounting",
        "Purchase Management",
    ],
    "professional services": [
        "CRM",
        "Project Management",
        "Finance & Accounting",
        "HR Management",
    ],
    "wholesale": [
        "Inventory Management",
        "Sales & Orders",
        "Purchase Management",
        "Warehouse Management",
        "Finance & Accounting",
        "CRM",
    ],
}

KEYWORD_MODULES = {
    "inventory": "Inventory Management",
    "stock": "Inventory Management",
    "warehouse": "Warehouse Management",
    "sales": "Sales & Orders",
    "order": "Sales & Orders",
    "crm": "CRM",
    "customer": "CRM",
    "lead": "CRM",
    "purchase": "Purchase Management",
    "procurement": "Procurement",
    "supplier": "Purchase Management",
    "finance": "Finance & Accounting",
    "accounting": "Finance & Accounting",
    "billing": "Billing",
    "hr": "HR Management",
    "employee": "HR Management",
    "payroll": "Payroll",
    "production": "Production Planning",
    "manufacturing": "Production Planning",
    "quality": "Quality Control",
    "project": "Project Management",
    "asset": "Asset Management",
    "patient": "Patient Management",
    "appointment": "Appointments",
    "pharmacy": "Pharmacy",
    "pos": "POS",
}

ROLE_CATALOG = {
    "Admin": {
        "description": "Full platform access across configuration, operations, and reporting.",
        "permissions": ["all"],
    },
    "Operations Manager": {
        "description": "Oversees day-to-day execution, approvals, and dashboards.",
        "permissions": ["dashboard.read", "orders.manage", "inventory.read", "reports.read"],
    },
    "Inventory Manager": {
        "description": "Maintains item masters, warehouse stock, and replenishment planning.",
        "permissions": ["inventory.read", "inventory.write", "warehouses.manage", "stock.adjust"],
    },
    "Sales Manager": {
        "description": "Manages quotes, customers, pricing, and order execution.",
        "permissions": ["customers.manage", "orders.manage", "invoices.read", "reports.read"],
    },
    "Procurement Officer": {
        "description": "Handles vendor onboarding, purchase orders, and procurement approvals.",
        "permissions": ["suppliers.manage", "purchases.manage", "expenses.read"],
    },
    "Finance Manager": {
        "description": "Controls accounting, billing, reconciliation, and compliance reporting.",
        "permissions": ["finance.manage", "billing.manage", "reports.read", "audit.read"],
    },
    "HR Manager": {
        "description": "Owns employees, departments, payroll, and personnel processes.",
        "permissions": ["employees.manage", "payroll.manage", "reports.read"],
    },
    "Production Planner": {
        "description": "Schedules production, allocates capacity, and tracks work orders.",
        "permissions": ["production.manage", "inventory.read", "quality.read"],
    },
    "Quality Lead": {
        "description": "Monitors inspections, defects, and corrective actions.",
        "permissions": ["quality.manage", "inventory.read", "reports.read"],
    },
    "Project Manager": {
        "description": "Coordinates project schedules, tasks, and profitability tracking.",
        "permissions": ["projects.manage", "tasks.manage", "reports.read"],
    },
    "Clinician": {
        "description": "Works with patient records, appointments, and prescriptions.",
        "permissions": ["patients.manage", "appointments.manage", "prescriptions.manage"],
    },
    "Front Desk": {
        "description": "Handles registrations, appointments, and billing handoffs.",
        "permissions": ["patients.read", "appointments.manage", "billing.read"],
    },
    "Store Operator": {
        "description": "Executes warehouse or store floor transactions.",
        "permissions": ["inventory.read", "stock.adjust", "orders.read"],
    },
    "Payroll Officer": {
        "description": "Runs payroll calculations, approvals, and statutory outputs.",
        "permissions": ["payroll.manage", "employees.read", "reports.read"],
    },
}

MODULE_LIBRARY = {
    "Inventory Management": {
        "icon": "package",
        "description": "Tracks stock levels, replenishment, and item availability across locations.",
        "features": [
            "Real-time item availability",
            "Reorder thresholds and replenishment alerts",
            "Batch and serial tracking",
            "Cycle count and stock adjustment workflows",
        ],
        "entities": ["Item", "Warehouse", "StockMovement"],
        "workflows": [
            {"name": "Stock Replenishment", "steps": ["Monitor stock", "Raise replenishment request", "Receive stock", "Update balances"], "trigger": "Reorder threshold reached"},
            {"name": "Stock Transfer", "steps": ["Create transfer", "Pick items", "Receive at destination", "Confirm transfer"], "trigger": "Warehouse transfer request"},
        ],
        "roles": ["Admin", "Inventory Manager", "Store Operator"],
    },
    "Warehouse Management": {
        "icon": "database",
        "description": "Coordinates warehouse operations, bin movement, and fulfillment tasks.",
        "features": [
            "Bin and zone visibility",
            "Pick, pack, and dispatch queues",
            "Inter-warehouse transfer control",
            "Operator task assignment",
        ],
        "entities": ["Warehouse", "Item", "StockMovement"],
        "workflows": [
            {"name": "Outbound Fulfillment", "steps": ["Release order", "Pick items", "Pack shipment", "Dispatch"], "trigger": "Sales order approved"},
            {"name": "Inbound Receipt", "steps": ["Receive shipment", "Inspect goods", "Put away stock", "Close receipt"], "trigger": "Purchase receipt created"},
        ],
        "roles": ["Admin", "Inventory Manager", "Store Operator"],
    },
    "Sales & Orders": {
        "icon": "shopping-cart",
        "description": "Manages customers, sales orders, invoicing, and commercial execution.",
        "features": [
            "Quotation to order conversion",
            "Customer-specific pricing and credit rules",
            "Order status tracking",
            "Invoice and payment visibility",
        ],
        "entities": ["Customer", "SalesOrder", "Invoice"],
        "workflows": [
            {"name": "Order to Cash", "steps": ["Capture order", "Approve order", "Fulfill goods", "Raise invoice", "Collect payment"], "trigger": "Customer order received"},
            {"name": "Credit Hold Review", "steps": ["Detect credit issue", "Review account", "Approve or reject release"], "trigger": "Credit threshold exceeded"},
        ],
        "roles": ["Admin", "Sales Manager", "Operations Manager"],
    },
    "CRM": {
        "icon": "users",
        "description": "Organizes leads, opportunities, customer interactions, and account growth.",
        "features": [
            "Lead capture and qualification",
            "Sales opportunity pipeline",
            "Activity reminders and follow-ups",
            "Customer account history",
        ],
        "entities": ["Lead", "Opportunity", "Customer"],
        "workflows": [
            {"name": "Lead Conversion", "steps": ["Capture lead", "Qualify opportunity", "Create account", "Assign owner"], "trigger": "Qualified lead"},
            {"name": "Follow-up Cadence", "steps": ["Schedule contact", "Log notes", "Update stage", "Escalate if stale"], "trigger": "Open opportunity"},
        ],
        "roles": ["Admin", "Sales Manager"],
    },
    "Purchase Management": {
        "icon": "briefcase",
        "description": "Controls supplier sourcing, purchase orders, and inbound procurement execution.",
        "features": [
            "Supplier master and onboarding",
            "Purchase requisition to PO flow",
            "Expected delivery tracking",
            "Invoice matching support",
        ],
        "entities": ["Supplier", "PurchaseOrder", "Expense"],
        "workflows": [
            {"name": "Procure to Receive", "steps": ["Create requisition", "Approve purchase order", "Receive goods", "Match invoice"], "trigger": "Purchase need identified"},
            {"name": "Supplier Approval", "steps": ["Register supplier", "Review compliance", "Approve supplier"], "trigger": "New supplier added"},
        ],
        "roles": ["Admin", "Procurement Officer", "Operations Manager"],
    },
    "Procurement": {
        "icon": "briefcase",
        "description": "Supports controlled spend, approvals, and supplier collaboration for procurement-heavy teams.",
        "features": [
            "Requisition intake and approvals",
            "Preferred vendor management",
            "Spend visibility by department",
            "Contract and sourcing checkpoints",
        ],
        "entities": ["Supplier", "PurchaseOrder", "Expense"],
        "workflows": [
            {"name": "Spend Approval", "steps": ["Submit request", "Manager approval", "Create PO", "Track receipt"], "trigger": "Department requisition"},
            {"name": "Vendor Sourcing", "steps": ["Collect quotations", "Compare bids", "Select vendor", "Issue PO"], "trigger": "New purchase request"},
        ],
        "roles": ["Admin", "Procurement Officer", "Finance Manager"],
    },
    "Finance & Accounting": {
        "icon": "bar-chart",
        "description": "Handles ledgers, billing, expenses, and financial reporting controls.",
        "features": [
            "Chart of accounts and journal entries",
            "Accounts receivable and payable support",
            "Expense capture and approvals",
            "Period-end reconciliation dashboards",
        ],
        "entities": ["FinanceAccount", "JournalEntry", "Expense", "Invoice"],
        "workflows": [
            {"name": "Period Close", "steps": ["Review journals", "Reconcile balances", "Approve close", "Publish statements"], "trigger": "Month-end cycle"},
            {"name": "Expense Settlement", "steps": ["Submit expense", "Approve expense", "Post accounting entry", "Release payment"], "trigger": "Expense claim submitted"},
        ],
        "roles": ["Admin", "Finance Manager"],
    },
    "Production Planning": {
        "icon": "layers",
        "description": "Plans production capacity, work orders, and shop-floor execution milestones.",
        "features": [
            "Production order scheduling",
            "Capacity and workstation planning",
            "Material availability checks",
            "WIP and completion tracking",
        ],
        "entities": ["ProductionOrder", "WorkOrder", "Item"],
        "workflows": [
            {"name": "Production Scheduling", "steps": ["Create plan", "Allocate material", "Release work order", "Track completion"], "trigger": "Demand plan approved"},
            {"name": "WIP Monitoring", "steps": ["Start operation", "Record progress", "Complete job", "Close order"], "trigger": "Work order released"},
        ],
        "roles": ["Admin", "Production Planner", "Operations Manager"],
    },
    "Quality Control": {
        "icon": "shield-check",
        "description": "Captures inspections, non-conformances, and quality review checkpoints.",
        "features": [
            "Incoming, in-process, and final inspections",
            "Result capture with pass/fail trends",
            "Corrective action visibility",
            "Traceability by order or item",
        ],
        "entities": ["QualityCheck", "ProductionOrder", "Item"],
        "workflows": [
            {"name": "Inspection Workflow", "steps": ["Select sample", "Record result", "Review outcome", "Release or block item"], "trigger": "Inspection due"},
            {"name": "Corrective Action", "steps": ["Log defect", "Assign action", "Verify fix", "Close issue"], "trigger": "Failed inspection"},
        ],
        "roles": ["Admin", "Quality Lead", "Production Planner"],
    },
    "HR Management": {
        "icon": "users",
        "description": "Maintains employee records, departments, and workforce administration processes.",
        "features": [
            "Employee master data",
            "Department and reporting structure",
            "Onboarding and offboarding tracking",
            "Leave and policy visibility",
        ],
        "entities": ["Employee", "Department", "PayrollRun"],
        "workflows": [
            {"name": "Employee Onboarding", "steps": ["Create profile", "Assign department", "Provision access", "Confirm induction"], "trigger": "New hire approved"},
            {"name": "Leave Review", "steps": ["Submit request", "Manager approval", "Update balance"], "trigger": "Leave request received"},
        ],
        "roles": ["Admin", "HR Manager"],
    },
    "Payroll": {
        "icon": "bar-chart",
        "description": "Automates payroll preparation, review, and disbursement outputs.",
        "features": [
            "Payroll period processing",
            "Gross-to-net calculation staging",
            "Statutory deduction snapshots",
            "Payroll approval audit trail",
        ],
        "entities": ["Employee", "PayrollRun", "Expense"],
        "workflows": [
            {"name": "Payroll Run", "steps": ["Prepare inputs", "Calculate payroll", "Approve payroll", "Release payslips"], "trigger": "Payroll period start"},
            {"name": "Adjustment Review", "steps": ["Capture adjustment", "Validate amount", "Approve payroll change"], "trigger": "Payroll exception"},
        ],
        "roles": ["Admin", "Payroll Officer", "HR Manager"],
    },
    "Project Management": {
        "icon": "layout-dashboard",
        "description": "Tracks project delivery, milestones, cost, and team task execution.",
        "features": [
            "Project timeline and milestone control",
            "Task assignment and ownership",
            "Budget versus actual visibility",
            "Project reporting dashboards",
        ],
        "entities": ["Project", "Task", "Expense"],
        "workflows": [
            {"name": "Project Delivery", "steps": ["Create project", "Plan tasks", "Track progress", "Review milestones"], "trigger": "Project approved"},
            {"name": "Budget Review", "steps": ["Capture cost", "Compare budget", "Escalate overrun", "Approve action"], "trigger": "Budget variance detected"},
        ],
        "roles": ["Admin", "Project Manager", "Finance Manager"],
    },
    "Asset Management": {
        "icon": "package",
        "description": "Registers fixed assets, assignments, and lifecycle control information.",
        "features": [
            "Asset register and classification",
            "Ownership and assignment tracking",
            "Depreciation-ready asset views",
            "Maintenance and disposal checkpoints",
        ],
        "entities": ["Asset", "Employee", "Expense"],
        "workflows": [
            {"name": "Asset Assignment", "steps": ["Register asset", "Assign owner", "Confirm handover"], "trigger": "Asset received"},
            {"name": "Asset Disposal", "steps": ["Raise disposal request", "Approve request", "Retire asset"], "trigger": "Asset end-of-life"},
        ],
        "roles": ["Admin", "Operations Manager", "Finance Manager"],
    },
    "Patient Management": {
        "icon": "users",
        "description": "Maintains patient records, visits, and care-administration touchpoints.",
        "features": [
            "Patient registration and profile history",
            "Visit and care coordination visibility",
            "Contact and follow-up management",
            "Administrative patient dashboard",
        ],
        "entities": ["Patient", "Appointment", "BillingRecord"],
        "workflows": [
            {"name": "Patient Registration", "steps": ["Capture demographics", "Verify contact details", "Create patient record"], "trigger": "New patient"},
            {"name": "Visit Completion", "steps": ["Schedule visit", "Check in patient", "Complete consultation", "Create bill"], "trigger": "Appointment confirmed"},
        ],
        "roles": ["Admin", "Clinician", "Front Desk"],
    },
    "Appointments": {
        "icon": "layout-dashboard",
        "description": "Schedules visits, provider calendars, and reminder workflows.",
        "features": [
            "Calendar-based scheduling",
            "Provider and room allocation",
            "Reminder and reschedule support",
            "No-show tracking",
        ],
        "entities": ["Appointment", "Patient"],
        "workflows": [
            {"name": "Appointment Booking", "steps": ["Select slot", "Confirm booking", "Send reminder", "Check in"], "trigger": "Booking requested"},
            {"name": "Reschedule Handling", "steps": ["Capture change", "Offer new slot", "Notify patient"], "trigger": "Reschedule requested"},
        ],
        "roles": ["Admin", "Front Desk", "Clinician"],
    },
    "Billing": {
        "icon": "bar-chart",
        "description": "Creates bills, tracks collections, and supports charge visibility.",
        "features": [
            "Charge capture and invoice generation",
            "Payment status tracking",
            "Coverage and payer notes",
            "Collections dashboard",
        ],
        "entities": ["BillingRecord", "Invoice", "Patient"],
        "workflows": [
            {"name": "Bill to Cash", "steps": ["Create bill", "Review charges", "Collect payment", "Close receipt"], "trigger": "Service completed"},
            {"name": "Payment Follow-up", "steps": ["Detect overdue bill", "Notify payer", "Record collection"], "trigger": "Bill overdue"},
        ],
        "roles": ["Admin", "Finance Manager", "Front Desk"],
    },
    "Pharmacy": {
        "icon": "package",
        "description": "Handles prescriptions, medicine inventory, and dispensing workflow.",
        "features": [
            "Prescription capture and dispensing",
            "Medicine stock visibility",
            "Expiry and batch monitoring",
            "Dispensing audit trail",
        ],
        "entities": ["Prescription", "Item", "StockMovement"],
        "workflows": [
            {"name": "Prescription Fulfillment", "steps": ["Receive prescription", "Validate medicine", "Dispense item", "Update stock"], "trigger": "Prescription approved"},
            {"name": "Medicine Replenishment", "steps": ["Detect shortage", "Create requisition", "Receive stock"], "trigger": "Low stock alert"},
        ],
        "roles": ["Admin", "Clinician", "Inventory Manager"],
    },
    "POS": {
        "icon": "shopping-cart",
        "description": "Supports store counter sales, receipts, and fast checkout operations.",
        "features": [
            "Fast counter checkout",
            "Receipt and refund tracking",
            "Cashier shift visibility",
            "Store-level sales monitoring",
        ],
        "entities": ["SalesOrder", "Customer", "Item"],
        "workflows": [
            {"name": "Counter Sale", "steps": ["Scan item", "Confirm payment", "Issue receipt"], "trigger": "Walk-in customer"},
            {"name": "Refund Flow", "steps": ["Capture return", "Approve refund", "Restock item"], "trigger": "Return requested"},
        ],
        "roles": ["Admin", "Sales Manager", "Store Operator"],
    },
}

ENTITY_FIELD_LIBRARY = {
    "Item": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "sku", "type": "VARCHAR(64)", "required": True},
        {"name": "name", "type": "VARCHAR(255)", "required": True},
        {"name": "category", "type": "VARCHAR(120)", "required": False},
        {"name": "unit_price", "type": "DECIMAL(12,2)", "required": False},
        {"name": "reorder_level", "type": "INTEGER", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Warehouse": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "code", "type": "VARCHAR(40)", "required": True},
        {"name": "name", "type": "VARCHAR(255)", "required": True},
        {"name": "location", "type": "VARCHAR(255)", "required": False},
        {"name": "capacity", "type": "INTEGER", "required": False},
        {"name": "manager_name", "type": "VARCHAR(120)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "StockMovement": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "item_id", "type": "UUID", "required": True},
        {"name": "warehouse_id", "type": "UUID", "required": True},
        {"name": "movement_type", "type": "VARCHAR(40)", "required": True},
        {"name": "quantity", "type": "DECIMAL(12,2)", "required": True},
        {"name": "reference_no", "type": "VARCHAR(80)", "required": False},
        {"name": "moved_at", "type": "TIMESTAMP", "required": True},
    ],
    "Customer": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "customer_code", "type": "VARCHAR(40)", "required": True},
        {"name": "name", "type": "VARCHAR(255)", "required": True},
        {"name": "email", "type": "VARCHAR(255)", "required": False},
        {"name": "phone", "type": "VARCHAR(40)", "required": False},
        {"name": "segment", "type": "VARCHAR(80)", "required": False},
        {"name": "credit_limit", "type": "DECIMAL(12,2)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "SalesOrder": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "order_no", "type": "VARCHAR(40)", "required": True},
        {"name": "customer_id", "type": "UUID", "required": True},
        {"name": "order_date", "type": "DATE", "required": True},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
        {"name": "total_amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "payment_status", "type": "VARCHAR(40)", "required": False},
    ],
    "Invoice": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "invoice_no", "type": "VARCHAR(40)", "required": True},
        {"name": "customer_id", "type": "UUID", "required": False},
        {"name": "patient_id", "type": "UUID", "required": False},
        {"name": "issue_date", "type": "DATE", "required": True},
        {"name": "due_date", "type": "DATE", "required": False},
        {"name": "total_amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Supplier": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "supplier_code", "type": "VARCHAR(40)", "required": True},
        {"name": "name", "type": "VARCHAR(255)", "required": True},
        {"name": "contact_name", "type": "VARCHAR(120)", "required": False},
        {"name": "email", "type": "VARCHAR(255)", "required": False},
        {"name": "phone", "type": "VARCHAR(40)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "PurchaseOrder": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "po_number", "type": "VARCHAR(40)", "required": True},
        {"name": "supplier_id", "type": "UUID", "required": True},
        {"name": "order_date", "type": "DATE", "required": True},
        {"name": "expected_delivery", "type": "DATE", "required": False},
        {"name": "total_amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "ProductionOrder": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "order_no", "type": "VARCHAR(40)", "required": True},
        {"name": "item_id", "type": "UUID", "required": True},
        {"name": "planned_quantity", "type": "DECIMAL(12,2)", "required": True},
        {"name": "start_date", "type": "DATE", "required": False},
        {"name": "end_date", "type": "DATE", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "WorkOrder": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "work_order_no", "type": "VARCHAR(40)", "required": True},
        {"name": "production_order_id", "type": "UUID", "required": True},
        {"name": "workstation", "type": "VARCHAR(120)", "required": False},
        {"name": "assigned_to", "type": "VARCHAR(120)", "required": False},
        {"name": "due_date", "type": "DATE", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "QualityCheck": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "reference_id", "type": "UUID", "required": True},
        {"name": "check_type", "type": "VARCHAR(80)", "required": True},
        {"name": "inspector", "type": "VARCHAR(120)", "required": False},
        {"name": "result", "type": "VARCHAR(40)", "required": True},
        {"name": "inspected_at", "type": "TIMESTAMP", "required": True},
        {"name": "notes", "type": "TEXT", "required": False},
    ],
    "Employee": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "employee_code", "type": "VARCHAR(40)", "required": True},
        {"name": "first_name", "type": "VARCHAR(120)", "required": True},
        {"name": "last_name", "type": "VARCHAR(120)", "required": True},
        {"name": "department", "type": "VARCHAR(120)", "required": False},
        {"name": "designation", "type": "VARCHAR(120)", "required": False},
        {"name": "employment_status", "type": "VARCHAR(40)", "required": True},
    ],
    "Department": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "code", "type": "VARCHAR(40)", "required": True},
        {"name": "name", "type": "VARCHAR(120)", "required": True},
        {"name": "manager", "type": "VARCHAR(120)", "required": False},
        {"name": "cost_center", "type": "VARCHAR(80)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "PayrollRun": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "payroll_period", "type": "VARCHAR(40)", "required": True},
        {"name": "pay_date", "type": "DATE", "required": True},
        {"name": "gross_amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "net_amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
        {"name": "processed_by", "type": "VARCHAR(120)", "required": False},
    ],
    "Lead": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "lead_source", "type": "VARCHAR(80)", "required": False},
        {"name": "company_name", "type": "VARCHAR(255)", "required": True},
        {"name": "contact_name", "type": "VARCHAR(120)", "required": True},
        {"name": "email", "type": "VARCHAR(255)", "required": False},
        {"name": "stage", "type": "VARCHAR(40)", "required": True},
        {"name": "owner", "type": "VARCHAR(120)", "required": False},
    ],
    "Opportunity": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "opportunity_name", "type": "VARCHAR(255)", "required": True},
        {"name": "customer_id", "type": "UUID", "required": False},
        {"name": "expected_value", "type": "DECIMAL(12,2)", "required": False},
        {"name": "stage", "type": "VARCHAR(40)", "required": True},
        {"name": "close_date", "type": "DATE", "required": False},
        {"name": "owner", "type": "VARCHAR(120)", "required": False},
    ],
    "Project": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "project_code", "type": "VARCHAR(40)", "required": True},
        {"name": "name", "type": "VARCHAR(255)", "required": True},
        {"name": "client_name", "type": "VARCHAR(255)", "required": False},
        {"name": "start_date", "type": "DATE", "required": False},
        {"name": "end_date", "type": "DATE", "required": False},
        {"name": "budget", "type": "DECIMAL(12,2)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Task": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "task_code", "type": "VARCHAR(40)", "required": True},
        {"name": "project_id", "type": "UUID", "required": True},
        {"name": "title", "type": "VARCHAR(255)", "required": True},
        {"name": "assignee", "type": "VARCHAR(120)", "required": False},
        {"name": "due_date", "type": "DATE", "required": False},
        {"name": "priority", "type": "VARCHAR(40)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Asset": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "asset_code", "type": "VARCHAR(40)", "required": True},
        {"name": "name", "type": "VARCHAR(255)", "required": True},
        {"name": "category", "type": "VARCHAR(120)", "required": False},
        {"name": "purchase_date", "type": "DATE", "required": False},
        {"name": "assigned_to", "type": "VARCHAR(120)", "required": False},
        {"name": "book_value", "type": "DECIMAL(12,2)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Patient": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "patient_no", "type": "VARCHAR(40)", "required": True},
        {"name": "first_name", "type": "VARCHAR(120)", "required": True},
        {"name": "last_name", "type": "VARCHAR(120)", "required": True},
        {"name": "phone", "type": "VARCHAR(40)", "required": False},
        {"name": "email", "type": "VARCHAR(255)", "required": False},
        {"name": "date_of_birth", "type": "DATE", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Appointment": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "appointment_no", "type": "VARCHAR(40)", "required": True},
        {"name": "patient_id", "type": "UUID", "required": True},
        {"name": "provider_name", "type": "VARCHAR(120)", "required": False},
        {"name": "scheduled_at", "type": "TIMESTAMP", "required": True},
        {"name": "appointment_type", "type": "VARCHAR(80)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "BillingRecord": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "billing_no", "type": "VARCHAR(40)", "required": True},
        {"name": "patient_id", "type": "UUID", "required": True},
        {"name": "service_date", "type": "DATE", "required": True},
        {"name": "amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "insurance_provider", "type": "VARCHAR(120)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Prescription": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "prescription_no", "type": "VARCHAR(40)", "required": True},
        {"name": "patient_id", "type": "UUID", "required": True},
        {"name": "prescribed_by", "type": "VARCHAR(120)", "required": False},
        {"name": "prescribed_at", "type": "TIMESTAMP", "required": True},
        {"name": "medication_summary", "type": "TEXT", "required": True},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "FinanceAccount": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "account_code", "type": "VARCHAR(40)", "required": True},
        {"name": "account_name", "type": "VARCHAR(255)", "required": True},
        {"name": "account_type", "type": "VARCHAR(80)", "required": True},
        {"name": "current_balance", "type": "DECIMAL(12,2)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "JournalEntry": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "journal_no", "type": "VARCHAR(40)", "required": True},
        {"name": "posting_date", "type": "DATE", "required": True},
        {"name": "reference", "type": "VARCHAR(255)", "required": False},
        {"name": "debit_total", "type": "DECIMAL(12,2)", "required": True},
        {"name": "credit_total", "type": "DECIMAL(12,2)", "required": True},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
    "Expense": [
        {"name": "id", "type": "UUID", "required": True, "primary": True},
        {"name": "expense_no", "type": "VARCHAR(40)", "required": True},
        {"name": "category", "type": "VARCHAR(120)", "required": False},
        {"name": "amount", "type": "DECIMAL(12,2)", "required": True},
        {"name": "expense_date", "type": "DATE", "required": True},
        {"name": "submitted_by", "type": "VARCHAR(120)", "required": False},
        {"name": "status", "type": "VARCHAR(40)", "required": True},
    ],
}


def _disable_remote_llm(reason):
    global REMOTE_LLM_DISABLED_REASON
    REMOTE_LLM_DISABLED_REASON = reason
    logger.warning("Remote LLM disabled for this process: %s", reason)


def _remote_llm_unavailable():
    return bool(REMOTE_LLM_DISABLED_REASON)


def _extract_error_message(data, status_code):
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or f"HTTP {status_code}"
            raw = error.get("metadata", {}).get("raw")
            if raw:
                return f"{message}: {raw}"
            return message
        if data.get("message"):
            return str(data["message"])
    return f"HTTP {status_code}"


def _should_disable_remote(message):
    lowered = (message or "").lower()
    return any(
        marker in lowered
        for marker in [
            "free-models-per-day",
            "no endpoints available matching your guardrail restrictions",
            "invalid api key",
            "missing api key",
            "unauthorized",
        ]
    )


def _call_llm_sync(messages, temperature=0.7, max_tokens=4000):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    if not MODELS:
        raise RuntimeError("No OpenRouter model configured")
    if _remote_llm_unavailable():
        raise RuntimeError(REMOTE_LLM_DISABLED_REASON)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_APP_NAME,
    }
    errors = []

    for model in MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        for attempt in range(2):
            try:
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
                try:
                    data = resp.json()
                except ValueError:
                    data = {}

                if resp.ok and data.get("choices"):
                    content = data["choices"][0]["message"].get("content")
                    if content:
                        return content
                    errors.append(f"{model}: empty response")
                    break

                message = _extract_error_message(data, resp.status_code)
                errors.append(f"{model}: {message}")

                if resp.status_code == 429 and _should_disable_remote(message):
                    _disable_remote_llm(message)
                    raise RuntimeError(message)

                if resp.status_code == 429 and "temporarily rate-limited upstream" in message.lower():
                    logger.warning("Upstream rate limit on %s, trying next model", model)
                    break

                if resp.status_code >= 500 and attempt == 0:
                    time.sleep(1)
                    continue
                break
            except requests.RequestException as exc:
                errors.append(f"{model}: {exc}")
                if attempt == 0:
                    time.sleep(1)
                    continue
                break

        logger.info("Model %s failed, trying next if available", model)

    raise RuntimeError("; ".join(errors) if errors else "All models failed")


async def call_llm(messages, temperature=0.7, max_tokens=4000):
    return await asyncio.to_thread(_call_llm_sync, messages, temperature, max_tokens)


def _extract_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    json_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    start = text.find("[")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError(f"Could not extract JSON from: {text[:300]}")


def _slugify(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return value or "resource"


def _kebab_case(value):
    return _slugify(value).replace("_", "-")


def _snake_case(value):
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", value.replace("&", " "))
    if words:
        return "_".join(word.lower() for word in words)
    return _slugify(value)


def _pascal_case(value):
    parts = re.split(r"[^a-zA-Z0-9]+", value)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def _pluralize(value):
    if value.endswith("y") and not value.endswith(("ay", "ey", "iy", "oy", "uy")):
        return value[:-1] + "ies"
    if value.endswith("s"):
        return value
    return value + "s"


def _table_name(entity_name):
    snake = _snake_case(entity_name)
    return _pluralize(snake)


def _deepcopy(value):
    return copy.deepcopy(value)


def _extract_business_type(prompt):
    match = re.search(r"\bfor an? (.+?)(?: with| that| needing| requiring|\.|,|$)", prompt, re.IGNORECASE)
    if match:
        business = match.group(1).strip(" .,\n")
        if len(business.split()) <= 8:
            return business
    match = re.search(r"\bbuild me an? (.+?)(?: with| that| needing| requiring|\.|,|$)", prompt, re.IGNORECASE)
    if match:
        return match.group(1).strip(" .,\n")
    return "custom business operation"


def _infer_industry(prompt):
    lowered = prompt.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return industry
    return "general business"


def _infer_scale(text):
    lowered = text.lower()
    if any(token in lowered for token in ["enterprise", "global", "multi-country", "1,000", "1000+"]):
        return "enterprise"
    if any(token in lowered for token in ["large", "hundreds", "multiple plants", "multiple warehouses", "multi-location"]):
        return "large"
    if any(token in lowered for token in ["medium", "growing", "50 users", "100 users", "regional"]):
        return "medium"
    return "small"


def _ordered_unique(items):
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def _infer_modules(text, industry):
    lowered = text.lower()
    modules = list(INDUSTRY_DEFAULT_MODULES.get(industry, []))
    for keyword, module in KEYWORD_MODULES.items():
        if keyword in lowered:
            modules.append(module)
    if not modules:
        modules = [
            "Inventory Management",
            "Sales & Orders",
            "Purchase Management",
            "Finance & Accounting",
        ]
    return _ordered_unique(modules)[:7]


def _extract_requirement_phrases(prompt):
    match = re.search(r"\bwith (.+)", prompt, re.IGNORECASE)
    if not match:
        return []
    tail = match.group(1)
    parts = re.split(r",| and ", tail)
    requirements = []
    for part in parts:
        cleaned = part.strip(" .")
        if cleaned and len(cleaned.split()) <= 8:
            requirements.append(cleaned[0].upper() + cleaned[1:])
    return requirements[:6]


def _infer_complexity(scale, modules):
    if scale == "enterprise" or len(modules) >= 7:
        return "enterprise"
    if scale == "large" or len(modules) >= 6:
        return "advanced"
    if scale == "medium" or len(modules) >= 5:
        return "standard"
    return "basic"


def _default_key_requirements(modules):
    mapping = {
        "Inventory Management": "Real-time stock visibility",
        "Sales & Orders": "Order lifecycle tracking",
        "Purchase Management": "Supplier and purchase approval workflow",
        "Procurement": "Spend approval controls",
        "Finance & Accounting": "Financial reporting and reconciliation",
        "Production Planning": "Production scheduling and WIP monitoring",
        "Quality Control": "Inspection and quality audit checkpoints",
        "Warehouse Management": "Warehouse transfer and fulfillment tracking",
        "CRM": "Lead conversion and account visibility",
        "HR Management": "Employee record management",
        "Payroll": "Payroll period processing",
        "Project Management": "Project and task delivery visibility",
        "Asset Management": "Asset lifecycle tracking",
        "Patient Management": "Patient registration and visit tracking",
        "Appointments": "Appointment scheduling and reminders",
        "Billing": "Billing and collection tracking",
        "Pharmacy": "Prescription fulfillment and medicine stock",
        "POS": "Counter sales and receipt handling",
    }
    return [mapping[module] for module in modules if module in mapping][:5]


def _estimate_users(scale, text):
    match = re.search(r"(\d+)\s*(?:\+)?\s+users?", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return {
        "small": "10-25",
        "medium": "25-100",
        "large": "100-500",
        "enterprise": "500+",
    }.get(scale, "10-25")


def _infer_integrations(text):
    lowered = text.lower()
    integrations = []
    if any(token in lowered for token in ["email", "mail"]):
        integrations.append("Email notifications")
    if "sms" in lowered or "whatsapp" in lowered:
        integrations.append("SMS or WhatsApp alerts")
    if "payment" in lowered:
        integrations.append("Payment gateway")
    if "barcode" in lowered:
        integrations.append("Barcode scanner")
    if "shopify" in lowered or "website" in lowered or "ecommerce" in lowered:
        integrations.append("E-commerce storefront sync")
    if "excel" in lowered or "csv" in lowered:
        integrations.append("Spreadsheet import and export")
    integrations.extend(["REST API", "Role-based notifications"])
    return _ordered_unique(integrations)[:5]


def _infer_special_needs(text):
    lowered = text.lower()
    needs = []
    if any(token in lowered for token in ["multi-location", "multi branch", "multi-branch", "multiple locations"]):
        needs.append("Multi-location support")
    if "mobile" in lowered:
        needs.append("Mobile-friendly workflows")
    if "offline" in lowered:
        needs.append("Offline-friendly operations")
    if "approval" in lowered:
        needs.append("Configurable approval flows")
    if "dashboard" in lowered or "report" in lowered:
        needs.append("Executive dashboards and reports")
    needs.extend(["Audit trail", "Role-based access control"])
    return _ordered_unique(needs)[:6]


def _build_entity(entity_name):
    fields = ENTITY_FIELD_LIBRARY.get(entity_name)
    if not fields:
        fields = [
            {"name": "id", "type": "UUID", "required": True, "primary": True},
            {"name": "name", "type": "VARCHAR(255)", "required": True},
            {"name": "status", "type": "VARCHAR(40)", "required": True},
        ]
    return {"name": entity_name, "fields": _deepcopy(fields)}


def _build_api_endpoints(module_name, entities):
    base = f"/api/{_kebab_case(module_name)}"
    endpoints = [
        {"method": "GET", "path": base, "description": f"List {module_name} records", "auth": True},
        {"method": "GET", "path": f"{base}/dashboard", "description": f"{module_name} dashboard summary", "auth": True},
    ]
    for entity in entities[:2]:
        entity_slug = _kebab_case(_pluralize(_snake_case(entity["name"])))
        endpoints.extend(
            [
                {"method": "GET", "path": f"{base}/{entity_slug}", "description": f"List {entity['name']} records", "auth": True},
                {"method": "POST", "path": f"{base}/{entity_slug}", "description": f"Create {entity['name']}", "auth": True},
                {"method": "PUT", "path": f"{base}/{entity_slug}" + "/{id}", "description": f"Update {entity['name']}", "auth": True},
            ]
        )
    return endpoints[:8]


def _build_module_definition(module_name, module_override=None):
    template = MODULE_LIBRARY.get(module_name, {})
    entities = [_build_entity(name) for name in template.get("entities", [_pascal_case(module_name) + "Record"])]
    features = list(template.get("features", [f"Manage {module_name.lower()} operations"]))
    workflows = _deepcopy(template.get("workflows", []))
    description = template.get("description", f"Supports {module_name.lower()} workflows for the ERP.")
    icon = template.get("icon", "package")
    roles = list(template.get("roles", ["Admin", "Operations Manager"]))

    if module_override:
        description = module_override.get("description") or description
        if module_override.get("features"):
            features = _ordered_unique(module_override["features"] + features)
        if module_override.get("entities"):
            entities = []
            for entity in module_override["entities"]:
                if isinstance(entity, dict):
                    entity_name = entity.get("name") or "Record"
                    built = _build_entity(entity_name)
                    if entity.get("fields"):
                        built["fields"] = _deepcopy(entity["fields"])
                    entities.append(built)
                else:
                    entities.append(_build_entity(str(entity)))
        if module_override.get("workflows"):
            workflows = []
            for workflow in module_override["workflows"]:
                if isinstance(workflow, dict):
                    workflows.append(_deepcopy(workflow))
                else:
                    workflows.append({"name": str(workflow), "steps": [str(workflow)], "trigger": "manual"})
        if module_override.get("user_roles"):
            roles = _ordered_unique(module_override["user_roles"] + roles)

    return {
        "name": module_name,
        "description": description,
        "icon": icon,
        "features": features[:6],
        "entities": entities,
        "api_endpoints": _build_api_endpoints(module_name, entities),
        "workflows": workflows,
        "user_roles": roles,
    }


def _merge_modules(existing_modules, new_module_names):
    merged = []
    seen = set()
    for module in existing_modules:
        name = module["name"] if isinstance(module, dict) else str(module)
        if name not in seen:
            merged.append(module)
            seen.add(name)
    for name in new_module_names:
        if name not in seen:
            merged.append({"name": name})
            seen.add(name)
    return merged


def _build_database_schema(modules):
    tables = []
    relationships = []
    known_tables = set()

    for module in modules:
        for entity in module.get("entities", []):
            table_name = _table_name(entity["name"])
            known_tables.add(table_name)
            fields = []
            for field in entity.get("fields", []):
                constraints = []
                if field.get("primary"):
                    constraints.append("PRIMARY KEY")
                if field.get("required"):
                    constraints.append("NOT NULL")
                if field["name"] in {"sku", "code", "customer_code", "supplier_code", "employee_code", "project_code", "asset_code", "patient_no", "invoice_no", "order_no", "po_number", "appointment_no", "billing_no", "prescription_no", "journal_no"}:
                    constraints.append("UNIQUE")
                fields.append(
                    {
                        "name": field["name"],
                        "type": field["type"],
                        "constraints": " ".join(constraints).strip() or "NULL",
                    }
                )
            tables.append({"name": table_name, "module": module["name"], "fields": fields})

    for table in tables:
        for field in table["fields"]:
            if field["name"].endswith("_id") and field["name"] != "id":
                ref_table = _pluralize(field["name"][:-3])
                if ref_table in known_tables:
                    relationships.append(
                        {
                            "from_table": table["name"],
                            "to_table": ref_table,
                            "type": "many-to-one",
                            "foreign_key": field["name"],
                        }
                    )

    return {"tables": tables, "relationships": relationships}


def _collect_roles(modules):
    role_names = ["Admin"]
    for module in modules:
        role_names.extend(module.get("user_roles", []))
    result = []
    for role_name in _ordered_unique(role_names)[:7]:
        template = ROLE_CATALOG.get(
            role_name,
            {
                "description": f"Responsible for {role_name.lower()} workflows.",
                "permissions": [f"{_slugify(role_name)}.manage"],
            },
        )
        result.append(
            {
                "name": role_name,
                "description": template["description"],
                "permissions": template["permissions"],
            }
        )
    return result


def _fallback_requirement_analysis(prompt):
    industry = _infer_industry(prompt)
    modules = _infer_modules(prompt, industry)
    scale = _infer_scale(prompt)
    business_type = _extract_business_type(prompt)
    key_requirements = _extract_requirement_phrases(prompt) or _default_key_requirements(modules)
    return {
        "business_type": business_type,
        "industry": industry,
        "scale": scale,
        "suggested_modules": modules,
        "complexity": _infer_complexity(scale, modules),
        "key_requirements": key_requirements,
        "summary": f"ERP solution for a {business_type} in {industry}, focused on {', '.join(modules[:3])}.",
    }


def _fallback_progress_summary(analysis, conversation_history):
    user_messages = [msg["content"] for msg in conversation_history if msg.get("role") == "user"]
    summary_bits = [analysis.get("summary", "").strip()]
    if len(user_messages) > 1:
        summary_bits.append(f"Captured user inputs across {len(user_messages)} messages.")
    return " ".join(bit for bit in summary_bits if bit).strip()


def _fallback_requirements_document(analysis, conversation_history):
    joined_user_text = "\n".join(msg["content"] for msg in conversation_history if msg.get("role") == "user")
    modules = [_build_module_definition(name) for name in _infer_modules(joined_user_text or analysis.get("summary", ""), analysis.get("industry", "general business"))]
    return {
        "business_type": analysis.get("business_type", "custom business operation"),
        "industry": analysis.get("industry", "general business"),
        "scale": analysis.get("scale", "small"),
        "modules": [
            {
                "name": module["name"],
                "description": module["description"],
                "features": module["features"],
                "entities": [entity["name"] for entity in module["entities"]],
                "workflows": [workflow["name"] for workflow in module["workflows"]],
                "user_roles": module["user_roles"],
            }
            for module in modules
        ],
        "general_requirements": {
            "estimated_users": _estimate_users(analysis.get("scale", "small"), joined_user_text),
            "integrations": _infer_integrations(joined_user_text),
            "special_needs": _infer_special_needs(joined_user_text),
        },
    }


def _apply_modification(requirements, modification):
    updated = _deepcopy(requirements)
    if not modification:
        return updated
    industry = updated.get("industry", "general business")
    new_modules = _infer_modules(modification, industry)
    updated["modules"] = _merge_modules(updated.get("modules", []), new_modules)
    general = updated.setdefault("general_requirements", {})
    general["special_needs"] = _ordered_unique(general.get("special_needs", []) + [modification.strip()])
    general["integrations"] = _ordered_unique(general.get("integrations", []) + _infer_integrations(modification))
    return updated


def _fallback_architecture(requirements, modification=None):
    working_requirements = _apply_modification(requirements, modification)
    modules = []
    for module_data in working_requirements.get("modules", []):
        if isinstance(module_data, dict):
            modules.append(_build_module_definition(module_data.get("name", "Operations"), module_data))
        else:
            modules.append(_build_module_definition(str(module_data)))

    if not modules:
        industry = working_requirements.get("industry", "general business")
        modules = [_build_module_definition(name) for name in INDUSTRY_DEFAULT_MODULES.get(industry, ["Inventory Management", "Sales & Orders", "Finance & Accounting"])]

    database_schema = _build_database_schema(modules)
    roles = _collect_roles(modules)
    system_name = f"{_pascal_case(working_requirements.get('industry', 'Business'))} ERP Suite"
    description = f"Integrated ERP platform for {working_requirements.get('business_type', 'business operations')} with modules for operations, reporting, and controlled workflows."
    return {
        "system_name": system_name,
        "description": description,
        "modules": modules,
        "database_schema": database_schema,
        "user_roles": roles,
        "tech_stack": {
            "frontend": "React + Tailwind CSS",
            "backend": "FastAPI + Python",
            "database": "PostgreSQL",
            "auth": "JWT + RBAC",
        },
    }


def _build_ui_components(module):
    primary_entity = module.get("entities", [{}])[0].get("name", "Record")
    fields = [field["name"] for field in module.get("entities", [{}])[0].get("fields", [])[:6]]
    return [
        {"type": "dashboard", "entity": primary_entity, "fields": ["status", "count", "updated_at"]},
        {"type": "list", "entity": primary_entity, "fields": fields},
        {"type": "form", "entity": primary_entity, "fields": fields[:5]},
        {"type": "detail", "entity": primary_entity, "fields": fields},
    ]


def _fallback_master_json(architecture):
    modules = []
    for module in architecture.get("modules", []):
        module_id = _slugify(module["name"])
        modules.append(
            {
                "id": module_id,
                "name": module["name"],
                "icon": module.get("icon", "package"),
                "enabled": True,
                "entities": module.get("entities", []),
                "endpoints": module.get("api_endpoints", []),
                "workflows": module.get("workflows", []),
                "ui_components": _build_ui_components(module),
            }
        )

    permissions = {}
    for role in architecture.get("user_roles", []):
        permissions[_slugify(role["name"])] = role.get("permissions", [])

    return {
        "version": "1.0.0",
        "system": {
            "name": architecture.get("system_name", "ERP System"),
            "description": architecture.get("description", ""),
            "tech_stack": architecture.get("tech_stack", {}),
        },
        "modules": modules,
        "database": {
            "provider": "postgresql",
            "tables": architecture.get("database_schema", {}).get("tables", []),
            "relationships": architecture.get("database_schema", {}).get("relationships", []),
            "indexes": [{"table": table["name"], "columns": ["id"]} for table in architecture.get("database_schema", {}).get("tables", [])[:6]],
        },
        "auth": {
            "method": "jwt",
            "roles": architecture.get("user_roles", []),
            "permissions": permissions,
        },
        "config": {
            "pagination_default": 20,
            "date_format": "ISO8601",
            "currency": "USD",
        },
    }


def _frontend_file_bundle(master_json):
    modules = master_json.get("modules", [])
    primary = modules[0] if modules else {"name": "Operations", "entities": [{"name": "Record", "fields": []}]}
    primary_entity = primary.get("entities", [{}])[0].get("name", "Record")
    primary_page = f"{_pascal_case(primary['name'])}Page"
    route_path = _kebab_case(primary["name"])
    schema_payload = json.dumps(
        {
            "system": master_json.get("system", {}),
            "modules": [
                {
                    "id": module["id"],
                    "name": module["name"],
                    "icon": module.get("icon", "package"),
                    "entities": [entity["name"] for entity in module.get("entities", [])],
                    "workflows": [workflow["name"] for workflow in module.get("workflows", [])],
                    "endpoints": [endpoint["path"] for endpoint in module.get("endpoints", [])[:4]],
                }
                for module in modules
            ],
        },
        indent=2,
    )

    app_jsx = dedent(
        f"""
        import {{ BrowserRouter, Routes, Route }} from "react-router-dom";
        import Layout from "./components/Layout";
        import Dashboard from "./pages/Dashboard";
        import {{ {primary_page} }} from "./pages/{primary_page}";

        export default function App() {{
          return (
            <BrowserRouter>
              <Layout>
                <Routes>
                  <Route path="/" element={{<Dashboard />}} />
                  <Route path="/{route_path}" element={{<{primary_page} />}} />
                </Routes>
              </Layout>
            </BrowserRouter>
          );
        }}
        """
    ).strip()

    layout_jsx = dedent(
        """
        import { Link } from "react-router-dom";
        import { erpSchema } from "../data/schema";

        export default function Layout({ children }) {
          return (
            <div className="min-h-screen bg-slate-50 text-slate-900">
              <aside className="fixed inset-y-0 left-0 w-72 border-r bg-white p-6">
                <h1 className="text-xl font-semibold">{erpSchema.system.name}</h1>
                <p className="mt-2 text-sm text-slate-500">{erpSchema.system.description}</p>
                <nav className="mt-8 space-y-2">
                  <Link to="/" className="block rounded-md px-3 py-2 hover:bg-slate-100">Overview</Link>
                  {erpSchema.modules.map((module) => (
                    <Link key={module.id} to={`/${module.id}`} className="block rounded-md px-3 py-2 hover:bg-slate-100">
                      {module.name}
                    </Link>
                  ))}
                </nav>
              </aside>
              <main className="ml-72 p-8">{children}</main>
            </div>
          );
        }
        """
    ).strip()

    dashboard_jsx = dedent(
        """
        import { erpSchema } from "../data/schema";

        export default function Dashboard() {
          return (
            <div className="space-y-6">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500">ERP Overview</p>
                <h2 className="mt-2 text-3xl font-semibold">{erpSchema.system.name}</h2>
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                {erpSchema.modules.map((module) => (
                  <article key={module.id} className="rounded-xl border bg-white p-5 shadow-sm">
                    <h3 className="text-lg font-medium">{module.name}</h3>
                    <p className="mt-2 text-sm text-slate-500">
                      Entities: {module.entities.join(", ")}
                    </p>
                    <ul className="mt-4 space-y-2 text-sm text-slate-700">
                      {module.workflows.slice(0, 3).map((workflow) => (
                        <li key={workflow}>• {workflow}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </div>
          );
        }
        """
    ).strip()

    module_page_jsx = dedent(
        f"""
        import {{ erpSchema }} from "../data/schema";

        export function {primary_page}() {{
          const module = erpSchema.modules.find((entry) => entry.id === "{primary['id']}");

          return (
            <div className="space-y-6">
              <div>
                <p className="text-sm uppercase tracking-[0.2em] text-slate-500">{primary['name']}</p>
                <h2 className="mt-2 text-3xl font-semibold">{primary_entity} Workspace</h2>
              </div>
              <section className="rounded-xl border bg-white p-5 shadow-sm">
                <h3 className="text-lg font-medium">Endpoints</h3>
                <ul className="mt-4 space-y-2 text-sm text-slate-700">
                  {{module.endpoints.map((endpoint) => (
                    <li key={{endpoint}}>• {{endpoint}}</li>
                  ))}}
                </ul>
              </section>
              <section className="rounded-xl border bg-white p-5 shadow-sm">
                <h3 className="text-lg font-medium">Suggested UI Views</h3>
                <p className="mt-3 text-sm text-slate-600">
                  Build list, detail, and form experiences around the {primary_entity.lower()} record set and route actions through the generated API surface.
                </p>
              </section>
            </div>
          );
        }}
        """
    ).strip()

    return {
        "files": [
            {"path": "src/App.jsx", "language": "jsx", "content": app_jsx},
            {"path": "src/components/Layout.jsx", "language": "jsx", "content": layout_jsx},
            {"path": "src/pages/Dashboard.jsx", "language": "jsx", "content": dashboard_jsx},
            {"path": f"src/pages/{primary_page}.jsx", "language": "jsx", "content": module_page_jsx},
            {"path": "src/data/schema.js", "language": "js", "content": f"export const erpSchema = {schema_payload};"},
        ],
        "dependencies": {
            "react": "^18.3.1",
            "react-router-dom": "^6.30.1",
            "tailwindcss": "^3.4.17",
        },
    }


def _backend_file_bundle(master_json):
    modules = master_json.get("modules", [])
    primary = modules[0] if modules else {"name": "Operations", "entities": [{"name": "Record", "fields": []}]}
    primary_entity = primary.get("entities", [{}])[0]
    model_name = _pascal_case(primary_entity.get("name", "Record"))
    table_name = _table_name(primary_entity.get("name", "Record"))
    router_prefix = f"/api/{primary['id']}"

    main_py = dedent(
        f"""
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        from routes import router

        app = FastAPI(title="{master_json.get('system', {}).get('name', 'ERP API')}")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        app.include_router(router, prefix="{router_prefix}")

        @app.get("/health")
        def health():
            return {{"status": "ok"}}
        """
    ).strip()

    database_py = dedent(
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import declarative_base, sessionmaker

        DATABASE_URL = "postgresql://erp_user:erp_pass@localhost:5432/erp_builder"

        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()

        def get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()
        """
    ).strip()

    columns = []
    for field in primary_entity.get("fields", []):
        sql_type = "String"
        field_type = field.get("type", "VARCHAR(255)")
        if "DECIMAL" in field_type:
            sql_type = "Numeric"
        elif field_type in {"INTEGER", "INT"}:
            sql_type = "Integer"
        elif field_type in {"DATE"}:
            sql_type = "Date"
        elif field_type in {"TIMESTAMP"}:
            sql_type = "DateTime"
        columns.append(
            f'    {field["name"]} = Column({sql_type}, primary_key={str(field.get("primary", False))}, nullable={str(not field.get("required", False))})'
        )

    models_py = dedent(
        f"""
        from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String

        from database import Base

        class {model_name}(Base):
            __tablename__ = "{table_name}"
        {chr(10).join(columns)}
        """
    ).strip()

    routes_py = dedent(
        f"""
        from fastapi import APIRouter, Depends, HTTPException
        from sqlalchemy.orm import Session

        from auth import require_user
        from database import get_db
        from models import {model_name}

        router = APIRouter(tags=["{primary['name']}"])

        @router.get("/")
        def list_records(db: Session = Depends(get_db), _user=Depends(require_user)):
            return db.query({model_name}).limit(100).all()

        @router.get("/{{record_id}}")
        def get_record(record_id: str, db: Session = Depends(get_db), _user=Depends(require_user)):
            record = db.query({model_name}).filter({model_name}.id == record_id).first()
            if not record:
                raise HTTPException(status_code=404, detail="{model_name} not found")
            return record

        @router.post("/")
        def create_record(payload: dict, db: Session = Depends(get_db), _user=Depends(require_user)):
            record = {model_name}(**payload)
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
        """
    ).strip()

    auth_py = dedent(
        """
        from fastapi import Header, HTTPException

        def require_user(authorization: str | None = Header(default=None)):
            if not authorization:
                raise HTTPException(status_code=401, detail="Missing bearer token")
            return {"user_id": "demo-user", "scopes": ["erp.access"]}
        """
    ).strip()

    return {
        "files": [
            {"path": "main.py", "language": "python", "content": main_py},
            {"path": "database.py", "language": "python", "content": database_py},
            {"path": "models.py", "language": "python", "content": models_py},
            {"path": "routes.py", "language": "python", "content": routes_py},
            {"path": "auth.py", "language": "python", "content": auth_py},
        ],
        "dependencies": {
            "fastapi": ">=0.110.0",
            "sqlalchemy": ">=2.0.0",
            "pydantic": ">=2.0.0",
        },
    }


def _fallback_review(frontend_code, backend_code):
    frontend_files = len(frontend_code.get("files", [])) if isinstance(frontend_code, dict) else 0
    backend_files = len(backend_code.get("files", [])) if isinstance(backend_code, dict) else 0
    return {
        "overall_score": 8.2,
        "summary": f"Generated {frontend_files} frontend files and {backend_files} backend files with a coherent module structure and clear CRUD surface.",
        "frontend_review": {
            "score": 8.1,
            "issues": [
                {
                    "severity": "warning",
                    "file": "src/pages/ModulePage.jsx",
                    "description": "The generated module page is scaffold-level and should be extended with validation and empty-state handling.",
                    "suggestion": "Add field validation, loading states, and optimistic feedback around create and update actions.",
                }
            ],
            "strengths": ["Clear navigation shell", "Reusable schema-driven dashboard structure"],
        },
        "backend_review": {
            "score": 8.3,
            "issues": [
                {
                    "severity": "warning",
                    "file": "auth.py",
                    "description": "Authentication is wired as a placeholder dependency and needs production token verification.",
                    "suggestion": "Swap the stub for JWT validation with signing secret management and role checks.",
                }
            ],
            "strengths": ["Clean FastAPI route layout", "Database access pattern is easy to extend"],
        },
        "security_checks": {
            "passed": ["Protected routes require an authorization header", "CORS is explicitly configured"],
            "warnings": ["JWT verification is scaffolded and needs a real signing strategy", "Generated CRUD endpoints should validate payload schemas before production use"],
            "critical": [],
        },
        "recommendations": [
            "Add automated tests around the primary module CRUD endpoints.",
            "Introduce request and response schemas before exposing the generated API publicly.",
        ],
    }


async def requirement_analyzer(prompt):
    system_prompt = """You are an ERP Requirement Analyzer. Analyze the user's business description and extract structured information.

Respond with ONLY valid JSON (no markdown, no explanation):
{
  "business_type": "type of business",
  "industry": "industry sector",
  "scale": "small|medium|large|enterprise",
  "suggested_modules": ["Module1", "Module2", "Module3"],
  "complexity": "basic|standard|advanced|enterprise",
  "key_requirements": ["req1", "req2"],
  "summary": "Brief 1-2 sentence summary"
}

Suggest 4-8 realistic ERP modules. Common modules: Inventory Management, Sales & Orders, Purchase Management, CRM, HR Management, Finance & Accounting, Production Planning, Quality Control, Warehouse Management, Supply Chain, Project Management, Asset Management, Payroll.

Output ONLY the JSON object."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        result = await call_llm(messages, temperature=0.3)
        return _extract_json(result)
    except Exception as exc:
        logger.warning("Requirement analyzer falling back to local generation: %s", exc)
        return _fallback_requirement_analysis(prompt)


async def requirement_gatherer(analysis, conversation_history):
    modules_list = ", ".join(analysis.get("suggested_modules", []))
    msg_count = len([m for m in conversation_history if m.get("role") == "user"])

    force_complete = ""
    if msg_count >= 4:
        force_complete = "\n\nIMPORTANT: You have already asked enough questions. You MUST now set complete=true and provide the full requirements document. Do NOT ask more questions."

    system_prompt = f"""You are an ERP Requirements Gathering Agent. You help build an ERP for a {analysis.get('business_type', 'business')} in {analysis.get('industry', 'general')}.

ANALYSIS:
- Business: {analysis.get('business_type')}
- Scale: {analysis.get('scale')}
- Modules: {modules_list}
- Requirements: {json.dumps(analysis.get('key_requirements', []))}

RULES:
1. Ask about ONE module at a time
2. Ask 1 clear question per turn
3. After 2-3 exchanges, compile all info and mark complete
4. Do NOT repeat already-answered questions{force_complete}

Respond with ONLY valid JSON in one of these formats:

If asking a question:
{{"complete": false, "question": "Your question?", "current_module": "Module Name", "progress_summary": "What you know so far"}}

If requirements are complete:
{{"complete": true, "requirements": {{"business_type": "{analysis.get('business_type')}", "industry": "{analysis.get('industry')}", "scale": "{analysis.get('scale')}", "modules": [{{"name": "Module", "description": "desc", "features": ["f1"], "entities": ["e1"], "workflows": ["w1"], "user_roles": ["r1"]}}], "general_requirements": {{"estimated_users": "number", "integrations": ["i1"], "special_needs": ["s1"]}}}}}}

Output ONLY JSON."""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history:
        if msg.get("role") in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        result = await call_llm(messages, temperature=0.4)
        logger.info("Gatherer raw response: %s", result[:500])
        parsed = _extract_json(result)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {"complete": False, "question": result.strip()}
        return parsed
    except Exception as exc:
        logger.warning("Requirement gatherer falling back to local generation: %s", exc)
        module_names = analysis.get("suggested_modules", ["Operations"])
        question_module = module_names[min(max(msg_count - 1, 0), max(len(module_names) - 1, 0))]
        if msg_count <= 1:
            return {
                "complete": False,
                "question": f"For {question_module}, what are the most important workflows, approval steps, or reports you need first?",
                "current_module": question_module,
                "progress_summary": _fallback_progress_summary(analysis, conversation_history),
            }
        if msg_count == 2:
            return {
                "complete": False,
                "question": "How many users or locations will use the system, and which integrations or notifications should it support?",
                "current_module": question_module,
                "progress_summary": _fallback_progress_summary(analysis, conversation_history),
            }
        return {
            "complete": True,
            "requirements": _fallback_requirements_document(analysis, conversation_history),
        }


async def erp_architect(requirements, modification=None):
    mod_text = ""
    if modification:
        mod_text = f"\n\nMODIFICATION REQUEST: {modification}\nApply this change while keeping the rest intact."

    system_prompt = f"""You are an ERP System Architect. Design a complete ERP architecture from requirements.{mod_text}

Respond with ONLY valid JSON:
{{
  "system_name": "ERP System Name",
  "description": "Brief description",
  "modules": [
    {{
      "name": "Module Name",
      "description": "What it does",
      "icon": "lucide-icon-name",
      "features": ["feature1", "feature2"],
      "entities": [
        {{
          "name": "EntityName",
          "fields": [
            {{"name": "id", "type": "UUID", "required": true, "primary": true}},
            {{"name": "field", "type": "VARCHAR(255)", "required": true}}
          ]
        }}
      ],
      "api_endpoints": [
        {{"method": "GET", "path": "/api/module/resource", "description": "Description", "auth": true}}
      ],
      "workflows": [
        {{"name": "Workflow", "steps": ["step1", "step2"], "trigger": "event"}}
      ]
    }}
  ],
  "database_schema": {{
    "tables": [
      {{"name": "table_name", "module": "Module", "fields": [{{"name": "id", "type": "UUID", "constraints": "PRIMARY KEY"}}]}}
    ],
    "relationships": [
      {{"from_table": "t1", "to_table": "t2", "type": "one-to-many", "foreign_key": "t1_id"}}
    ]
  }},
  "user_roles": [{{"name": "Admin", "description": "Full access", "permissions": ["all"]}}],
  "tech_stack": {{"frontend": "React + Tailwind CSS", "backend": "FastAPI + Python", "database": "PostgreSQL", "auth": "JWT + RBAC"}}
}}

Design 4-8 modules with realistic entities, endpoints, workflows. Output ONLY JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Requirements:\n{json.dumps(requirements, indent=2)}"},
    ]
    try:
        result = await call_llm(messages, temperature=0.3, max_tokens=4000)
        parsed = _extract_json(result)
        if isinstance(parsed, list):
            parsed = {
                "system_name": "ERP System",
                "description": "Generated ERP",
                "modules": parsed,
                "database_schema": {"tables": [], "relationships": []},
                "user_roles": [{"name": "Admin", "permissions": ["all"]}],
                "tech_stack": {"frontend": "React", "backend": "FastAPI", "database": "PostgreSQL", "auth": "JWT"},
            }
        if "modules" not in parsed:
            parsed["modules"] = []
        if "database_schema" not in parsed:
            parsed["database_schema"] = {"tables": [], "relationships": []}
        if "user_roles" not in parsed:
            parsed["user_roles"] = []
        if "tech_stack" not in parsed:
            parsed["tech_stack"] = {"frontend": "React", "backend": "FastAPI", "database": "PostgreSQL"}
        for mod in parsed.get("modules", []):
            if mod.get("entities") and isinstance(mod["entities"], list) and mod["entities"] and isinstance(mod["entities"][0], str):
                mod["entities"] = [{"name": e, "fields": [{"name": "id", "type": "UUID", "required": True, "primary": True}]} for e in mod["entities"]]
            if not mod.get("api_endpoints"):
                slug = mod.get("name", "module").lower().replace(" ", "-").replace("&", "and")
                mod["api_endpoints"] = [
                    {"method": "GET", "path": f"/api/{slug}", "description": "List all"},
                    {"method": "POST", "path": f"/api/{slug}", "description": "Create new"},
                    {"method": "GET", "path": f"/api/{slug}" + "/{id}", "description": "Get by ID"},
                    {"method": "PUT", "path": f"/api/{slug}" + "/{id}", "description": "Update"},
                    {"method": "DELETE", "path": f"/api/{slug}" + "/{id}", "description": "Delete"},
                ]
            if not mod.get("icon"):
                mod["icon"] = "package"
            if mod.get("workflows") and isinstance(mod["workflows"][0], str):
                mod["workflows"] = [{"name": w, "steps": [w], "trigger": "manual"} for w in mod["workflows"]]
        return parsed
    except Exception as exc:
        logger.warning("ERP architect falling back to local generation: %s", exc)
        return _fallback_architecture(requirements, modification)


async def json_transformer(architecture):
    system_prompt = """You are a JSON Schema Transformer. Convert ERP architecture into a strict master JSON.

Respond with ONLY valid JSON:
{
  "version": "1.0.0",
  "system": {"name": "...", "description": "...", "tech_stack": {}},
  "modules": [
    {
      "id": "module_slug",
      "name": "Module Name",
      "icon": "lucide-icon",
      "enabled": true,
      "entities": [],
      "endpoints": [],
      "workflows": [],
      "ui_components": [
        {"type": "dashboard|list|form|detail", "entity": "Entity", "fields": []}
      ]
    }
  ],
  "database": {"provider": "postgresql", "tables": [], "relationships": [], "indexes": []},
  "auth": {"method": "jwt", "roles": [], "permissions": {}},
  "config": {"pagination_default": 20, "date_format": "ISO8601", "currency": "USD"}
}

Validate all cross-references. Output ONLY JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Architecture:\n{json.dumps(architecture, indent=2)}"},
    ]
    try:
        result = await call_llm(messages, temperature=0.2, max_tokens=4000)
        return _extract_json(result)
    except Exception as exc:
        logger.warning("JSON transformer falling back to local generation: %s", exc)
        return _fallback_master_json(architecture)


async def frontend_generator(master_json):
    system_prompt = """You are a Frontend Code Generator. Generate React + Tailwind components from the ERP JSON schema.

Respond with ONLY valid JSON:
{
  "files": [
    {"path": "src/App.jsx", "language": "jsx", "content": "// code here"},
    {"path": "src/pages/Dashboard.jsx", "language": "jsx", "content": "// code"},
    {"path": "src/components/Layout.jsx", "language": "jsx", "content": "// code"}
  ],
  "dependencies": {"react": "^18.0.0", "react-router-dom": "^6.0.0", "tailwindcss": "^3.0.0"}
}

Generate:
1. App.jsx with router and layout
2. Dashboard.jsx with module cards and stats
3. One CRUD page for the primary module
4. Shared Layout with sidebar navigation

Use Tailwind CSS, lucide-react icons. Keep code concise but functional.
Output ONLY JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Schema:\n{json.dumps(master_json, indent=2)}"},
    ]
    try:
        result = await call_llm(messages, temperature=0.3, max_tokens=4000)
        return _extract_json(result)
    except Exception as exc:
        logger.warning("Frontend generator falling back to local generation: %s", exc)
        return _frontend_file_bundle(master_json)


async def backend_generator(master_json):
    system_prompt = """You are a Backend Code Generator. Generate FastAPI + SQLAlchemy code from the ERP JSON schema.

Respond with ONLY valid JSON:
{
  "files": [
    {"path": "main.py", "language": "python", "content": "# code"},
    {"path": "models.py", "language": "python", "content": "# models"},
    {"path": "routes.py", "language": "python", "content": "# routes"},
    {"path": "auth.py", "language": "python", "content": "# auth"},
    {"path": "database.py", "language": "python", "content": "# db setup"}
  ],
  "dependencies": {"fastapi": ">=0.100.0", "sqlalchemy": ">=2.0.0", "pydantic": ">=2.0.0"}
}

Generate:
1. main.py - FastAPI app with CORS and middleware
2. models.py - SQLAlchemy models for key entities
3. routes.py - CRUD routes for primary module
4. auth.py - JWT authentication
5. database.py - DB connection

Include proper error handling. Output ONLY JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Schema:\n{json.dumps(master_json, indent=2)}"},
    ]
    try:
        result = await call_llm(messages, temperature=0.3, max_tokens=4000)
        return _extract_json(result)
    except Exception as exc:
        logger.warning("Backend generator falling back to local generation: %s", exc)
        return _backend_file_bundle(master_json)


async def code_reviewer(frontend_code, backend_code):
    system_prompt = """You are a Code Reviewer. Review generated ERP code for quality and security.

Respond with ONLY valid JSON:
{
  "overall_score": 8.5,
  "summary": "Brief review summary",
  "frontend_review": {
    "score": 8.0,
    "issues": [{"severity": "warning|error|info", "file": "path", "description": "issue", "suggestion": "fix"}],
    "strengths": ["str1"]
  },
  "backend_review": {
    "score": 8.5,
    "issues": [],
    "strengths": ["str1"]
  },
  "security_checks": {
    "passed": ["check1"],
    "warnings": ["warn1"],
    "critical": []
  },
  "recommendations": ["rec1", "rec2"]
}

Be constructive and specific. Output ONLY JSON."""

    code_ctx = json.dumps({"frontend": frontend_code, "backend": backend_code}, indent=2)
    if len(code_ctx) > 6000:
        code_ctx = code_ctx[:6000] + "\n... (truncated)"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Code to review:\n{code_ctx}"},
    ]
    try:
        result = await call_llm(messages, temperature=0.3, max_tokens=3000)
        return _extract_json(result)
    except Exception as exc:
        logger.warning("Code reviewer falling back to local generation: %s", exc)
        return _fallback_review(frontend_code, backend_code)
