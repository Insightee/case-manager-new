"""Unit tests for admin case pipeline filter helpers (mirrors frontend adminCasePipeline.js)."""

from __future__ import annotations

STAFF_ROLES_BLOCKING_CM_ONLY = frozenset(
    {"SUPER_ADMIN", "MODULE_ADMIN", "FINANCE", "HR", "ADMIN"}
)


def is_case_manager_only_role(roles: list[str]) -> bool:
    if "CASE_MANAGER" not in roles:
        return False
    return not any(r in STAFF_ROLES_BLOCKING_CM_ONLY for r in roles)


def test_case_manager_only_excludes_finance_hr():
    assert is_case_manager_only_role(["CASE_MANAGER"]) is True
    assert is_case_manager_only_role(["CASE_MANAGER", "FINANCE"]) is False
    assert is_case_manager_only_role(["CASE_MANAGER", "HR"]) is False
    assert is_case_manager_only_role(["CASE_MANAGER", "ADMIN"]) is False


def test_super_admin_not_cm_only():
    assert is_case_manager_only_role(["CASE_MANAGER", "SUPER_ADMIN"]) is False
