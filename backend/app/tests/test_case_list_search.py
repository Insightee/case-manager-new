"""Case list search by child name, case code, and therapist name."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_case_list_search_by_child_name_and_shadow_module():
    headers = _login("superadmin@demo.com")

    all_res = client.get("/api/v1/cases?page_size=100", headers=headers)
    assert all_res.status_code == 200, all_res.text
    all_items = all_res.json()["items"]
    assert all_items, "expected seeded cases"

    shadow = next((c for c in all_items if c.get("product_module") == "shadow_support"), None)
    if not shadow:
        # Fall back: search by SS token if shadow is beyond first page
        ss = client.get("/api/v1/cases?search=SS&page_size=50", headers=headers)
        assert ss.status_code == 200, ss.text
        shadow = next((c for c in ss.json()["items"] if c.get("product_module") == "shadow_support"), None)
    assert shadow, "expected at least one shadow_support case in seed data"

    child_token = (shadow.get("child_name") or "").split()[0]
    assert child_token

    by_child = client.get(f"/api/v1/cases?search={child_token}&page_size=50", headers=headers)
    assert by_child.status_code == 200, by_child.text
    child_ids = {c["id"] for c in by_child.json()["items"]}
    assert shadow["id"] in child_ids

    by_code = client.get(f"/api/v1/cases?search={shadow['case_code']}&page_size=20", headers=headers)
    assert by_code.status_code == 200, by_code.text
    code_ids = {c["id"] for c in by_code.json()["items"]}
    assert shadow["id"] in code_ids

    by_module = client.get("/api/v1/cases?product_module=shadow_support&page_size=50", headers=headers)
    assert by_module.status_code == 200, by_module.text
    assert all(c["product_module"] == "shadow_support" for c in by_module.json()["items"])
    assert any(c["id"] == shadow["id"] for c in by_module.json()["items"])

    by_shadow_word = client.get("/api/v1/cases?search=shadow&page_size=50", headers=headers)
    assert by_shadow_word.status_code == 200, by_shadow_word.text
    assert any(c["id"] == shadow["id"] for c in by_shadow_word.json()["items"])


def test_case_list_search_by_therapist_name():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/cases?page_size=50", headers=headers)
    assert res.status_code == 200, res.text
    with_therapist = next((c for c in res.json()["items"] if c.get("therapist_name")), None)
    if not with_therapist:
        # Broader search if first page has unassigned cases
        res = client.get("/api/v1/cases?search=a&page_size=100", headers=headers)
        with_therapist = next((c for c in res.json()["items"] if c.get("therapist_name")), None)
    assert with_therapist, "expected a case with an active therapist"

    token = with_therapist["therapist_name"].split()[0]
    search = client.get(f"/api/v1/cases?search={token}&page_size=50", headers=headers)
    assert search.status_code == 200, search.text
    ids = {c["id"] for c in search.json()["items"]}
    assert with_therapist["id"] in ids
    assert any(c.get("therapist_name") for c in search.json()["items"])
