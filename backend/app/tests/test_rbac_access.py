"""RBAC catalog, preview, and grant sync."""

from app.core.rbac_access import (
    grants_to_module_assignments,
    normalize_module_access_grants,
    preview_access,
    sync_user_access_fields,
)
from app.models.user import User


def test_normalize_grants_from_module_ids():
    grants = normalize_module_access_grants(None, module_ids=["homecare", "billing"], view_only=True)
    assert grants["homecare"]["access"] == "view"
    assert grants_to_module_assignments(grants) == ["homecare", "billing"]


def test_preview_access_case_manager():
    result = preview_access(
        role_names=["CASE_MANAGER"],
        module_access_grants={
            "homecare": {"enabled": True, "access": "write"},
        },
        feature_overrides={"homecare": ["incidents"]},
        view_only=False,
    )
    assert "homecare" in result["module_assignments"]
    assert "incidents" not in result["features"]
    assert any("Cases" in a for a in result["portal_areas"])


def test_sync_super_admin_clears_grants():
    user = User(
        email="x@demo.com",
        password_hash="x",
        full_name="X",
        module_assignments=["homecare"],
        module_access_grants={"homecare": {"enabled": True, "access": "write"}},
    )
    sync_user_access_fields(user, role_names=["SUPER_ADMIN"], module_assignments=["homecare"])
    assert user.module_assignments == []
    assert user.module_access_grants == {}
