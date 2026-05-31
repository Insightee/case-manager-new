from __future__ import annotations

from dataclasses import dataclass

from app.core.service_access import ORG_CAPABILITY_IDS


@dataclass(frozen=True)
class ModuleFeature:
    id: str
    label: str
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductModule:
    id: str
    label: str
    description: str
    case_product_modules: tuple[str, ...]
    features: tuple[ModuleFeature, ...]


CLINICAL_FEATURES: tuple[ModuleFeature, ...] = (
    ModuleFeature("cases", "Cases & assignments", ("case.read.all", "case.read.team", "case.read.scoped", "case.update", "case.assign")),
    ModuleFeature("session_logs", "Session logs", ("session.read",)),
    ModuleFeature(
        "reports",
        "Reports & case documents",
        ("monthly_report.approve", "case_document.create", "case_document.review"),
    ),
    ModuleFeature("iep", "IEP documents", ("attachment.manage", "iep.read")),
    ModuleFeature("cm_meetings", "CM meetings & case review calls", ("case.read.team", "case.read.scoped")),
    ModuleFeature("tickets", "Support tickets", ("ticket.manage",)),
    ModuleFeature("incidents", "Incident reports", ("incident.read_sensitive", "ticket.manage")),
)

# Legacy alias for rbac_access imports
_CLINICAL_FEATURES = CLINICAL_FEATURES

ORG_PRODUCT_MODULES: tuple[ProductModule, ...] = (
    ProductModule(
        id="billing",
        label="Billing & finance",
        description="Therapist invoices, payouts, and client payment claims.",
        case_product_modules=(),
        features=(
            ModuleFeature("invoices", "Invoice review", ("invoice.approve", "invoice.generate", "payout.override")),
            ModuleFeature("dashboard", "Finance dashboard", ()),
            ModuleFeature("tickets", "Support tickets", ("ticket.manage",)),
            ModuleFeature("incidents", "Incident reports", ("incident.read_sensitive", "ticket.manage")),
        ),
    ),
    ProductModule(
        id="people_admin",
        label="People & user admin",
        description="Staff directory, invites, and access configuration.",
        case_product_modules=(),
        features=(
            ModuleFeature("people", "People directory", ("user.manage", "user.read")),
        ),
    ),
    ProductModule(
        id="hr_ops",
        label="HR operations",
        description="Leave, memos, and therapist HR records.",
        case_product_modules=(),
        features=(
            ModuleFeature("leave", "Leave management", ("leave.manage",)),
            ModuleFeature("memos", "Memos", ("memo.send",)),
            ModuleFeature("therapist_hr", "Therapist HR", ("therapist.read",)),
            ModuleFeature("hr_reports", "HR reports & exports", ("hr_report.export",)),
            ModuleFeature("tickets", "Support tickets", ("ticket.manage",)),
            ModuleFeature("incidents", "Incident reports", ("incident.read_sensitive", "ticket.manage")),
        ),
    ),
    ProductModule(
        id="service_catalog_admin",
        label="Service catalog settings",
        description="Configure service categories and commercial products.",
        case_product_modules=(),
        features=(
            ModuleFeature("service_catalog", "Service categories", ("user.manage",)),
        ),
    ),
)

# Org capabilities only — clinical scope comes from service_categories table.
PRODUCT_MODULES: tuple[ProductModule, ...] = ORG_PRODUCT_MODULES
MODULE_BY_ID: dict[str, ProductModule] = {m.id: m for m in ORG_PRODUCT_MODULES}

ALL_FEATURE_IDS: tuple[str, ...] = tuple(
    dict.fromkeys(f.id for m in ORG_PRODUCT_MODULES for f in m.features)
)

MODULE_SCOPED_ROLES: frozenset[str] = frozenset(
    {
        "ADMIN",
        "MODULE_ADMIN",
        "VIEWER",
        "CASE_MANAGER",
        "SUPERVISOR",
        "FINANCE",
        "HR",
        "SCHOOL_COORDINATOR",
    }
)

BILLING_MODULE_ID = "billing"
FIXED_CLINICAL_IDS: tuple[str, ...] = ("homecare", "shadow_support")


def default_clinical_service_ids(db=None) -> list[str]:
    """Active service category ids (clinical access)."""
    from app.core.service_access import active_service_category_ids

    return sorted(active_service_category_ids(db))


def role_defaults_for_api(db=None) -> dict[str, dict[str, list[str]]]:
    """Role → default service ids and org capability ids."""
    clinical = default_clinical_service_ids(db)
    all_org = [m.id for m in ORG_PRODUCT_MODULES]
    return {
        "SUPER_ADMIN": {"services": [], "org": []},
        "MODULE_ADMIN": {"services": list(clinical), "org": list(all_org)},
        "CASE_MANAGER": {"services": list(clinical), "org": []},
        "FINANCE": {"services": [], "org": ["billing"]},
        "HR": {"services": [], "org": ["people_admin", "hr_ops"]},
        "ADMIN": {"services": list(clinical), "org": []},
        "VIEWER": {"services": list(clinical), "org": []},
        "SUPERVISOR": {"services": list(clinical), "org": []},
        "SCHOOL_COORDINATOR": {"services": ["shadow_support"] if "shadow_support" in clinical else clinical[:1], "org": []},
        "THERAPIST": {"services": list(clinical), "org": []},
    }


def legacy_role_defaults_flat(db=None) -> dict[str, list[str]]:
    """Flat module list for backward-compatible API consumers."""
    defaults = role_defaults_for_api(db)
    out: dict[str, list[str]] = {}
    for role, spec in defaults.items():
        out[role] = list(dict.fromkeys([*spec.get("services", []), *spec.get("org", [])]))
    return out


def module_catalog_for_api() -> list[dict]:
    return org_catalog_for_api()


def org_catalog_for_api() -> list[dict]:
    return [
        {
            "id": m.id,
            "label": m.label,
            "description": m.description,
            "case_product_modules": list(m.case_product_modules),
            "module_type": "org",
            "features": [{"id": f.id, "label": f.label, "permissions": list(f.permissions)} for f in m.features],
        }
        for m in ORG_PRODUCT_MODULES
    ]


def is_org_capability(module_id: str) -> bool:
    return str(module_id).strip().lower() in ORG_CAPABILITY_IDS
