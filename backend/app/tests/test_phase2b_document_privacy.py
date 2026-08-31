"""Phase 2b: document privacy ceilings and promotions."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case, CaseStatus
from app.models.case_document import CaseDocument, CaseDocumentStatus, CaseDocumentVisibility
from app.models.child import Child
from app.models.document_comment import DocumentComment
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_id(email: str) -> int:
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == email)).first()
        assert user is not None
        return int(user.id)


def _case_id(case_code: str) -> int:
    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == case_code)).first()
        assert case is not None
        return int(case.id)


def _first_case_id(headers: dict[str, str]) -> int:
    res = client.get("/api/v1/cases?page_size=20", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    items = data if isinstance(data, list) else data.get("items", data)
    assert items, "expected at least one accessible case"
    return int(items[0]["id"])


def _case_id_from_payload(payload: list[dict], case_code: str) -> int:
    match = next((row for row in payload if row.get("caseCode") == case_code or row.get("case_code") == case_code), None)
    assert match is not None
    return int(match["id"])


def _parent_case_id() -> int:
    res = client.get("/api/v1/parent/home", headers=_login("parent@demo.com"))
    assert res.status_code == 200, res.text
    cases = res.json().get("cases") or []
    assert cases, "parent needs at least one linked case"
    return int(cases[0]["id"])


def _create_upload_document(case_id: int, headers: dict[str, str], title: str) -> int:
    payload = {
        "category": "OTHER",
        "title": title,
        "source_type": "UPLOAD",
    }
    pdf = io.BytesIO(b"%PDF-1.4 phase2b")
    res = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        data=payload,
        files={"file": (f"{uuid4().hex}.pdf", pdf, "application/pdf")},
    )
    assert res.status_code == 201, res.text
    return int(res.json()["id"])


def _create_link_document(case_id: int, headers: dict[str, str], title: str) -> int:
    res = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=headers,
        json={
            "category": "OTHER",
            "title": title,
            "source_type": "EXTERNAL_LINK",
            "external_url": "https://docs.google.com/document/d/phase2b/edit",
        },
    )
    assert res.status_code == 201, res.text
    return int(res.json()["id"])


def _set_document_fields(document_id: int, **fields) -> None:
    with SessionLocal() as db:
        doc = db.get(CaseDocument, document_id)
        assert doc is not None
        for key, value in fields.items():
            setattr(doc, key, value)
        db.commit()


def _set_mentor(therapist_email: str, mentor_email: str) -> None:
    with SessionLocal() as db:
        therapist = db.scalars(select(User).where(User.email == therapist_email)).first()
        mentor = db.scalars(select(User).where(User.email == mentor_email)).first()
        assert therapist is not None and mentor is not None
        profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)).first()
        assert profile is not None
        profile.mentor_user_id = mentor.id
        db.commit()


def _create_unassigned_case() -> int:
    with SessionLocal() as db:
        child = Child(first_name="Phase", last_name="TwoB")
        db.add(child)
        db.flush()
        case_mgr_id = _user_id("casemanager@demo.com")
        case = Case(
            case_code=f"PH2B-{uuid4().hex[:8]}",
            child_id=child.id,
            service_type="Shadow Support",
            product_module="shadow_support",
            status=CaseStatus.ACTIVE,
            case_manager_user_id=case_mgr_id,
        )
        db.add(case)
        db.commit()
        return int(case.id)


def test_parent_internal_by_id_is_hidden():
    therapist_headers = _login("therapist@demo.com")
    case_id = _parent_case_id()
    doc_id = _create_upload_document(case_id, therapist_headers, "Parent internal doc")
    _set_document_fields(
        doc_id,
        visibility=CaseDocumentVisibility.INTERNAL_ONLY.value,
        status=CaseDocumentStatus.CLIENT_REVIEW.value,
    )

    parent_headers = _login("parent@demo.com")
    res = client.get(f"/api/v1/documents/{doc_id}", headers=parent_headers)
    assert res.status_code == 404


def test_parent_client_doc_not_published_is_hidden():
    therapist_headers = _login("therapist@demo.com")
    case_id = _parent_case_id()
    doc_id = _create_upload_document(case_id, therapist_headers, "Parent client pending")
    _set_document_fields(
        doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE.value,
        status=CaseDocumentStatus.DRAFT.value,
    )

    parent_headers = _login("parent@demo.com")
    res = client.get(f"/api/v1/documents/{doc_id}", headers=parent_headers)
    assert res.status_code == 404


def test_therapist_unassigned_case_is_hidden():
    case_id = _create_unassigned_case()
    therapist_headers = _login("therapist@demo.com")
    superadmin_headers = _login("superadmin@demo.com")
    doc_id = _create_upload_document(case_id, superadmin_headers, "Unassigned case doc")
    _set_document_fields(
        doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
        status=CaseDocumentStatus.APPROVED.value,
    )

    res = client.get(f"/api/v1/documents/{doc_id}", headers=therapist_headers)
    assert res.status_code == 404


def test_therapist_assigned_sees_care_team_not_internal():
    therapist_headers = _login("therapist@demo.com")
    case_id = _first_case_id(therapist_headers)
    internal_doc_id = _create_upload_document(case_id, therapist_headers, "Assigned internal")
    care_team_doc_id = _create_upload_document(case_id, therapist_headers, "Assigned care team")
    _set_document_fields(
        internal_doc_id,
        visibility=CaseDocumentVisibility.INTERNAL_ONLY.value,
        status=CaseDocumentStatus.APPROVED.value,
    )
    _set_document_fields(
        care_team_doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
        status=CaseDocumentStatus.APPROVED.value,
    )

    res = client.get(f"/api/v1/cases/{case_id}/documents", headers=therapist_headers)
    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}
    assert care_team_doc_id in ids
    assert internal_doc_id not in ids

    detail = client.get(f"/api/v1/documents/{internal_doc_id}", headers=therapist_headers)
    assert detail.status_code == 404


def test_mentor_reads_all_three_and_cannot_promote():
    _set_mentor("therapist@demo.com", "shadowcm@demo.com")
    therapist_headers = _login("therapist@demo.com")
    mentor_headers = _login("shadowcm@demo.com")
    mentor_cases = client.get("/api/v1/cases?page_size=20", headers=mentor_headers)
    assert mentor_cases.status_code == 200, mentor_cases.text
    items = mentor_cases.json()
    items = items if isinstance(items, list) else items.get("items", items)
    case_id = _case_id_from_payload(items, "IC-2026-053")
    internal_doc_id = _create_upload_document(case_id, therapist_headers, "Mentor internal")
    care_team_doc_id = _create_upload_document(case_id, therapist_headers, "Mentor care team")
    client_doc_id = _create_upload_document(case_id, therapist_headers, "Mentor client")
    _set_document_fields(internal_doc_id, visibility=CaseDocumentVisibility.INTERNAL_ONLY.value, status=CaseDocumentStatus.APPROVED.value)
    _set_document_fields(
        care_team_doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
        status=CaseDocumentStatus.APPROVED.value,
    )
    _set_document_fields(
        client_doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE.value,
        status=CaseDocumentStatus.CLIENT_REVIEW.value,
    )

    res = client.get(f"/api/v1/cases/{case_id}/documents", headers=mentor_headers)
    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}
    assert {internal_doc_id, care_team_doc_id, client_doc_id}.issubset(ids)

    promote = client.post(
        f"/api/v1/documents/{internal_doc_id}/visibility",
        headers=mentor_headers,
        json={"to": "CLIENT", "reason": "Mentor should not be able to promote"},
    )
    assert promote.status_code == 403


def test_promote_internal_to_client_keeps_comments_hidden_from_parent():
    therapist_headers = _login("therapist@demo.com")
    case_id = _parent_case_id()
    doc_id = _create_upload_document(case_id, therapist_headers, "Comment privacy doc")
    comment = client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=therapist_headers,
        json={"body": "Keep this internal until family-ready.", "comment_type": "GENERAL"},
    )
    assert comment.status_code == 201, comment.text
    comment_id = int(comment.json()["id"])
    with SessionLocal() as db:
        row = db.get(DocumentComment, comment_id)
        assert row is not None
        assert row.visibility == "internal_only"

    _set_document_fields(
        doc_id,
        visibility=CaseDocumentVisibility.INTERNAL_ONLY.value,
        status=CaseDocumentStatus.CLIENT_REVIEW.value,
    )

    superadmin_headers = _login("superadmin@demo.com")
    promote = client.post(
        f"/api/v1/documents/{doc_id}/visibility",
        headers=superadmin_headers,
        json={"to": "CLIENT", "reason": "Ready for family"},
    )
    assert promote.status_code == 200, promote.text

    parent_headers = _login("parent@demo.com")
    detail = client.get(f"/api/v1/documents/{doc_id}", headers=parent_headers)
    assert detail.status_code == 200, detail.text
    comments = client.get(f"/api/v1/documents/{doc_id}/comments", headers=parent_headers)
    assert comments.status_code == 200, comments.text
    assert comments.json() == []


def test_external_link_cannot_promote_above_internal():
    therapist_headers = _login("therapist@demo.com")
    case_id = _first_case_id(therapist_headers)
    doc_id = _create_link_document(case_id, therapist_headers, "External link doc")
    promote = client.post(
        f"/api/v1/documents/{doc_id}/visibility",
        headers=_login("superadmin@demo.com"),
        json={"to": "CLIENT", "reason": "Should be blocked"},
    )
    assert promote.status_code == 400, promote.text


def test_download_404_matches_list_for_out_of_audience_cases():
    therapist_headers = _login("therapist@demo.com")
    case_id = _first_case_id(therapist_headers)
    internal_doc_id = _create_upload_document(case_id, therapist_headers, "Download internal")
    client_doc_id = _create_upload_document(case_id, therapist_headers, "Download client")
    _set_document_fields(
        internal_doc_id,
        visibility=CaseDocumentVisibility.INTERNAL_ONLY.value,
        status=CaseDocumentStatus.CLIENT_REVIEW.value,
    )
    _set_document_fields(
        client_doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE.value,
        status=CaseDocumentStatus.DRAFT.value,
    )

    parent_headers = _login("parent@demo.com")
    for doc_id in (internal_doc_id, client_doc_id):
        listed = client.get(f"/api/v1/documents/{doc_id}", headers=parent_headers)
        downloaded = client.get(f"/api/v1/documents/{doc_id}/download", headers=parent_headers)
        assert listed.status_code == 404
        assert downloaded.status_code == 404

    unassigned_case_id = _create_unassigned_case()
    unassigned_doc_id = _create_upload_document(
        unassigned_case_id, _login("superadmin@demo.com"), "Download unassigned"
    )
    _set_document_fields(
        unassigned_doc_id,
        visibility=CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
        status=CaseDocumentStatus.APPROVED.value,
    )
    therapist_detail = client.get(f"/api/v1/documents/{unassigned_doc_id}", headers=therapist_headers)
    therapist_download = client.get(f"/api/v1/documents/{unassigned_doc_id}/download", headers=therapist_headers)
    assert therapist_detail.status_code == 404
    assert therapist_download.status_code == 404
