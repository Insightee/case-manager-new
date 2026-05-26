from __future__ import annotations

from dataclasses import dataclass, field


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


_CLINICAL_FEATURES: tuple[ModuleFeature, ...] = (
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
    ModuleFeature("incidents", "Incident reports", ("incident.read_sensitive",)),
)

PRODUCT_MODULES: tuple[ProductModule, ...] = (
    ProductModule(
        id="homecare",
        label="Homecare",
        description="In-home therapy programmes and guardian-facing reports.",
        case_product_modules=("homecare",),
        features=_CLINICAL_FEATURES,
    ),
    ProductModule(
        id="shadow_support",
        label="Shadow Support",
        description="School and community shadow support cases.",
        case_product_modules=("shadow_support",),
        features=_CLINICAL_FEATURES,
    ),
    ProductModule(
        id="billing",
        label="Billing & finance",
        description="Therapist invoices, payouts, and finance operations (all programmes).",
        case_product_modules=(),
        features=(
            ModuleFeature("invoices", "Invoice review", ("invoice.approve", "invoice.generate", "payout.override")),
            ModuleFeature("dashboard", "Finance dashboard", ()),
        ),
    ),
)

MODULE_BY_ID: dict[str, ProductModule] = {m.id: m for m in PRODUCT_MODULES}

ALL_FEATURE_IDS: tuple[str, ...] = tuple(
    dict.fromkeys(f.id for m in PRODUCT_MODULES for f in m.features)
)

# Roles that must be scoped to at least one product module (unless super admin).
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

ROLE_DEFAULT_MODULES: dict[str, list[str]] = {
    "MODULE_ADMIN": ["homecare", "shadow_support", "billing"],
    "ADMIN": ["homecare", "shadow_support"],
    "VIEWER": ["homecare", "shadow_support"],
    "CASE_MANAGER": ["homecare", "shadow_support"],
    "SUPERVISOR": ["homecare", "shadow_support"],
    "FINANCE": ["billing"],
    "HR": ["homecare", "shadow_support"],
    "SCHOOL_COORDINATOR": ["shadow_support"],
}


def module_catalog_for_api() -> list[dict]:
    return [
        {
            "id": m.id,
            "label": m.label,
            "description": m.description,
            "case_product_modules": list(m.case_product_modules),
            "features": [{"id": f.id, "label": f.label, "permissions": list(f.permissions)} for f in m.features],
        }
        for m in PRODUCT_MODULES
    ]
