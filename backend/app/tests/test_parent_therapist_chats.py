import io
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.parent_therapist_message import ParentTherapistMessage
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.parent import ParentGuardian
from app.core.database import SessionLocal

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_direct_chats_flow():
    admin_headers = _login("superadmin@demo.com")

    # 1. Create a parent/child family
    fam = client.post(
        "/api/v1/admin/families",
        headers=admin_headers,
        json={
            "parent_email": "chat-parent@demo.com",
            "parent_full_name": "Chat Parent",
            "child": {"first_name": "Chat", "last_name": "Kid"},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201
    child_id = fam.json()["childId"]
    parent_user_id = fam.json()["parentUserId"]

    # Set password for parent
    pwd = client.post(
        f"/api/v1/admin/users/{parent_user_id}/set-password",
        headers=admin_headers,
        json={"password": "demo123"},
    )
    assert pwd.status_code == 200

    # Get seed therapist
    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    assert therapists.status_code == 200
    therapist_id = therapists.json()[0]["id"]
    therapist_email = therapists.json()[0]["email"]

    # Set password for therapist to ensure we can log in
    pwd = client.post(
        f"/api/v1/admin/users/{therapist_id}/set-password",
        headers=admin_headers,
        json={"password": "demo123"},
    )
    assert pwd.status_code == 200

    # 2. Allot case to therapist
    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Shadow support",
            "product_module": "shadow_support",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201
    case_id = allot.json()["case"]["id"]

    # Activate allotment so the therapist is active
    activate = client.post(
        f"/api/v1/admin/cases/{case_id}/activate-allotment",
        headers=admin_headers,
    )
    assert activate.status_code == 200

    parent_headers = _login("chat-parent@demo.com")
    therapist_headers = _login(therapist_email)

    # 3. Parent fetches chats - should be empty but return therapist
    get_res = client.get(f"/api/v1/parent/chats/{case_id}/messages", headers=parent_headers)
    assert get_res.status_code == 200
    assert len(get_res.json()["messages"]) == 0
    assert get_res.json()["active_therapist"]["id"] == therapist_id

    # 4. Parent sends message
    send_res = client.post(
        f"/api/v1/parent/chats/{case_id}/messages?therapist_id={therapist_id}",
        headers=parent_headers,
        json={"body": "Hello from parent!"}
    )
    assert send_res.status_code == 200
    assert send_res.json()["body"] == "Hello from parent!"
    assert send_res.json()["sender_id"] == parent_user_id
    assert send_res.json()["recipient_id"] == therapist_id
    assert not send_res.json()["is_read"]

    # 5. Therapist lists tabs - should show case with unread count = 1
    tabs_res = client.get("/api/v1/therapist/chats", headers=therapist_headers)
    assert tabs_res.status_code == 200
    matching_tab = next(t for t in tabs_res.json() if t["case_id"] == case_id)
    assert matching_tab["unread_count"] == 1
    assert matching_tab["parent_name"] == "Chat Parent"

    # 6. Therapist reads messages - should mark as read
    msgs_res = client.get(f"/api/v1/therapist/chats/{case_id}/messages", headers=therapist_headers)
    assert msgs_res.status_code == 200
    assert len(msgs_res.json()["messages"]) == 1
    assert msgs_res.json()["messages"][0]["is_read"]  # Marked as read on fetch

    # Verify tab unread count is now 0
    tabs_res = client.get("/api/v1/therapist/chats", headers=therapist_headers)
    matching_tab = next(t for t in tabs_res.json() if t["case_id"] == case_id)
    assert matching_tab["unread_count"] == 0

    # 7. Therapist replies
    reply_res = client.post(
        f"/api/v1/therapist/chats/{case_id}/messages",
        headers=therapist_headers,
        json={"body": "Hello from therapist!"}
    )
    assert reply_res.status_code == 200
    assert reply_res.json()["body"] == "Hello from therapist!"
    assert reply_res.json()["sender_id"] == therapist_id
    assert reply_res.json()["recipient_id"] == parent_user_id

    # 8. Parent uploads photo <= 10MB
    photo_data = b"fake_photo_bytes_under_10mb"
    photo_file = io.BytesIO(photo_data)
    upload_res = client.post(
        f"/api/v1/parent/chats/{case_id}/upload?therapist_id={therapist_id}",
        headers=parent_headers,
        files={"file": ("test.png", photo_file, "image/png")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["attachment_name"] == "test.png"
    msg_id = upload_res.json()["id"]

    # Download attachment securely
    dl_res = client.get(f"/api/v1/parent/chats/messages/attachments/{msg_id}", headers=therapist_headers)
    assert dl_res.status_code == 200
    assert dl_res.content == photo_data

    # 9. Verify 10MB size limit is enforced
    huge_data = b"x" * (10 * 1024 * 1024 + 10)  # > 10MB
    huge_file = io.BytesIO(huge_data)
    upload_fail = client.post(
        f"/api/v1/parent/chats/{case_id}/upload?therapist_id={therapist_id}",
        headers=parent_headers,
        files={"file": ("huge.png", huge_file, "image/png")}
    )
    assert upload_fail.status_code == 400
    assert "exceeds" in upload_fail.json()["detail"]

    # 10. Verify 90-day retention pruning
    # Manually backdate a message in DB
    db = SessionLocal()
    try:
        old_msg = ParentTherapistMessage(
            case_id=case_id,
            sender_id=parent_user_id,
            recipient_id=therapist_id,
            body="This is an ancient message from 95 days ago",
            created_at=datetime.now(timezone.utc) - timedelta(days=95)
        )
        db.add(old_msg)
        db.commit()

        # Verify old message is present in DB
        db_check = db.scalar(select(ParentTherapistMessage).where(ParentTherapistMessage.body.contains("ancient")))
        assert db_check is not None

        # Fetching messages triggers pruning
        client.get(f"/api/v1/parent/chats/{case_id}/messages?therapist_id={therapist_id}", headers=parent_headers)

        # Verify old message is deleted from DB
        db.expire_all()
        db_check2 = db.scalar(select(ParentTherapistMessage).where(ParentTherapistMessage.body.contains("ancient")))
        assert db_check2 is None
    finally:
        db.close()


def test_multiple_therapist_chats():
    admin_headers = _login("superadmin@demo.com")

    # 1. Create a parent/child family
    fam = client.post(
        "/api/v1/admin/families",
        headers=admin_headers,
        json={
            "parent_email": "multi-parent@demo.com",
            "parent_full_name": "Multi Parent",
            "child": {"first_name": "Multi", "last_name": "Kid"},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201
    child_id = fam.json()["childId"]
    parent_user_id = fam.json()["parentUserId"]

    # Set password for parent
    client.post(
        f"/api/v1/admin/users/{parent_user_id}/set-password",
        headers=admin_headers,
        json={"password": "demo123"},
    )

    # Get active therapists
    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    assert therapists.status_code == 200
    therapist_list = therapists.json()
    
    if len(therapist_list) < 2:
        create_res = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "email": "therapist-two@demo.com",
                "password": "demo123",
                "full_name": "Second Therapist",
                "role_names": ["THERAPIST"],
                "module_assignments": ["homecare", "shadow_support"],
            },
        )
        assert create_res.status_code == 201
        
        therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
        assert therapists.status_code == 200
        therapist_list = therapists.json()

    t1_id = therapist_list[0]["id"]
    t1_email = therapist_list[0]["email"]
    t2_id = therapist_list[1]["id"]
    t2_email = therapist_list[1]["email"]

    # Ensure passwords are set
    for tid in [t1_id, t2_id]:
        client.post(
            f"/api/v1/admin/users/{tid}/set-password",
            headers=admin_headers,
            json={"password": "demo123"},
        )

    # Allot case service 1 to Therapist 1
    allot1 = client.post(
        "/api/v1/admin/cases/allot",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Shadow support",
            "product_module": "shadow_support",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": t1_id,
        },
    )
    assert allot1.status_code == 201
    case_id = allot1.json()["case"]["id"]

    # Activate allotment 1
    activate1 = client.post(
        f"/api/v1/admin/cases/{case_id}/activate-allotment",
        headers=admin_headers,
    )
    assert activate1.status_code == 200

    # Manually create and insert a second CaseAssignment for Therapist 2 in the database
    db = SessionLocal()
    try:
        from app.models.assignment import CaseAssignment, CaseAssignmentStatus
        from datetime import date
        
        # Get case_service_id from the first assignment
        first_assign = db.scalar(
            select(CaseAssignment).where(CaseAssignment.case_id == case_id)
        )
        assert first_assign is not None
        
        assign2 = CaseAssignment(
            case_id=case_id,
            case_service_id=first_assign.case_service_id,
            therapist_user_id=t2_id,
            assigned_by_user_id=first_assign.assigned_by_user_id,
            start_date=date.today(),
            status=CaseAssignmentStatus.ACTIVE
        )
        db.add(assign2)
        db.commit()
    finally:
        db.close()

    parent_headers = _login("multi-parent@demo.com")
    t1_headers = _login(t1_email)
    t2_headers = _login(t2_email)

    # 1. Parent fetches chat messages - should return both active therapists
    get_res = client.get(f"/api/v1/parent/chats/{case_id}/messages", headers=parent_headers)
    assert get_res.status_code == 200
    active_therapists = get_res.json()["active_therapists"]
    assert len(active_therapists) >= 2
    assert any(t["id"] == t1_id for t in active_therapists)
    assert any(t["id"] == t2_id for t in active_therapists)

    # 2. Parent sends message to Therapist 1
    send1 = client.post(
        f"/api/v1/parent/chats/{case_id}/messages?therapist_id={t1_id}",
        headers=parent_headers,
        json={"body": "Hello Therapist 1"}
    )
    assert send1.status_code == 200
    assert send1.json()["recipient_id"] == t1_id

    # Parent sends message to Therapist 2
    send2 = client.post(
        f"/api/v1/parent/chats/{case_id}/messages?therapist_id={t2_id}",
        headers=parent_headers,
        json={"body": "Hello Therapist 2"}
    )
    assert send2.status_code == 200
    assert send2.json()["recipient_id"] == t2_id

    # 3. Verify messages are isolated in parent GET responses
    res_t1 = client.get(f"/api/v1/parent/chats/{case_id}/messages?therapist_id={t1_id}", headers=parent_headers)
    assert len(res_t1.json()["messages"]) == 1
    assert res_t1.json()["messages"][0]["body"] == "Hello Therapist 1"

    res_t2 = client.get(f"/api/v1/parent/chats/{case_id}/messages?therapist_id={t2_id}", headers=parent_headers)
    assert len(res_t2.json()["messages"]) == 1
    assert res_t2.json()["messages"][0]["body"] == "Hello Therapist 2"

    # 4. Verify therapist 1 only sees thread with therapist 1
    msgs_t1 = client.get(f"/api/v1/therapist/chats/{case_id}/messages", headers=t1_headers)
    assert len(msgs_t1.json()["messages"]) == 1
    assert msgs_t1.json()["messages"][0]["body"] == "Hello Therapist 1"

    # Verify therapist 2 only sees thread with therapist 2
    msgs_t2 = client.get(f"/api/v1/therapist/chats/{case_id}/messages", headers=t2_headers)
    assert len(msgs_t2.json()["messages"]) == 1
    assert msgs_t2.json()["messages"][0]["body"] == "Hello Therapist 2"
