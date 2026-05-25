from __future__ import annotations

from app.core.module_access import user_has_feature
from app.core.permissions import RoleName, case_scope_check, user_has_permission
from app.models.case import Case
from app.models.case_document import (
    CLINICAL_CATEGORIES,
    CaseDocument,
    CaseDocumentStatus,
    CaseDocumentVisibility,
)
from app.models.user import User
from app.services import case_service, parent_service

OPERATIONAL_ROLES = frozenset(
    {
        RoleName.SUPER_ADMIN.value,
        RoleName.ADMIN.value,
        RoleName.CASE_MANAGER.value,
        RoleName.SUPERVISOR.value,
        RoleName.THERAPIST.value,
    }
)

PARENT_VISIBLE_STATUSES = frozenset(
    {
        CaseDocumentStatus.CLIENT_REVIEW.value,
        CaseDocumentStatus.APPROVED.value,
    }
)


def _role_names(user: User) -> set[str]:
    return set(user.role_names or [])


def is_finance_only_clinical_denied(user: User) -> bool:
    names = _role_names(user)
    if RoleName.FINANCE.value in names and not names.intersection(OPERATIONAL_ROLES):
        return True
    return False


def is_hr_only_clinical_denied(user: User) -> bool:
    names = _role_names(user)
    if RoleName.HR.value in names and not names.intersection(OPERATIONAL_ROLES):
        return True
    return False


def can_access_clinical_documents(user: User) -> bool:
    if is_finance_only_clinical_denied(user) or is_hr_only_clinical_denied(user):
        return False
    has_case_access = (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "case.read.assigned")
        or user_has_permission(user, "case.read.scoped")
        or user_has_permission(user, "admin.override")
    )
    if not has_case_access:
        return False
    if user_has_permission(user, "case_document.create") or user_has_permission(
        user, "case_document.review"
    ):
        return True
    return user_has_feature(user, "reports")


def parent_can_read_document(doc: CaseDocument) -> bool:
    if doc.visibility == CaseDocumentVisibility.INTERNAL_ONLY.value:
        return False
    if doc.visibility == CaseDocumentVisibility.CLIENT_VISIBLE.value:
        return doc.status in PARENT_VISIBLE_STATUSES
    if doc.visibility == CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value:
        return doc.status in (
            CaseDocumentStatus.APPROVED.value,
            CaseDocumentStatus.CLIENT_REVIEW.value,
        )
    return False


def can_read(db, user: User, doc: CaseDocument, case: Case | None = None) -> bool:
    case = case or case_service.get_case(db, doc.case_id)
    if not case:
        return False
    if RoleName.PARENT.value in _role_names(user):
        child_ids = parent_service.child_ids_for_parent(db, user.id)
        if case.child_id not in child_ids:
            return False
        return parent_can_read_document(doc)
    if not can_access_clinical_documents(user):
        return False
    if doc.category in CLINICAL_CATEGORIES and (
        is_finance_only_clinical_denied(user) or is_hr_only_clinical_denied(user)
    ):
        return False
    return case_scope_check(db, user, case)


def can_create(db, user: User, case: Case) -> bool:
    if not user_has_permission(user, "case_document.create"):
        return False
    if not can_access_clinical_documents(user):
        return False
    return case_scope_check(db, user, case)


def can_review(db, user: User, doc: CaseDocument, case: Case | None = None) -> bool:
    if not user_has_permission(user, "case_document.review"):
        return False
    case = case or case_service.get_case(db, doc.case_id)
    if not case:
        return False
    return case_scope_check(db, user, case)


def can_edit_metadata(user: User, doc: CaseDocument) -> bool:
    if doc.status not in (
        CaseDocumentStatus.DRAFT.value,
        CaseDocumentStatus.CHANGES_REQUESTED.value,
    ):
        return False
    if doc.submitted_by_user_id == user.id:
        return True
    return user_has_permission(user, "case_document.review")


def allowed_actions(db, user: User, doc: CaseDocument, case: Case | None = None) -> list[str]:
    if not can_read(db, user, doc, case):
        return []
    actions: list[str] = []
    case = case or case_service.get_case(db, doc.case_id)
    if can_edit_metadata(user, doc):
        actions.extend(["edit", "add_version"])
    if doc.submitted_by_user_id == user.id and doc.status in (
        CaseDocumentStatus.DRAFT.value,
        CaseDocumentStatus.CHANGES_REQUESTED.value,
    ):
        actions.append("submit")
    if can_review(db, user, doc, case):
        if doc.status in (
            CaseDocumentStatus.SUBMITTED.value,
            CaseDocumentStatus.SUPERVISOR_REVIEW.value,
        ):
            actions.extend(["approve", "request_changes"])
        if doc.status == CaseDocumentStatus.APPROVED.value:
            actions.append("publish_client")
        if doc.status not in (CaseDocumentStatus.ARCHIVED.value,):
            actions.append("archive")
    if RoleName.PARENT.value in _role_names(user) and parent_can_read_document(doc):
        if doc.status == CaseDocumentStatus.CLIENT_REVIEW.value:
            actions.extend(["parent_approve", "parent_feedback"])
        actions.append("comment")
    elif can_read(db, user, doc, case):
        actions.append("comment")
    return sorted(set(actions))
