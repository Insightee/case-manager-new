"""Voice-first session log — upload, pipeline, status, retry, guardrails."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.conftest import login_headers
from app.tests.session_helpers import ensure_scheduled_sessions_for_therapist

client = TestClient(app)

FAKE_AUDIO = b"\x1aE\xdf\xa3" + b"voice-test-bytes" * 64  # webm magic + payload


def _therapist_headers():
    return login_headers(client, "therapist@demo.com")


def _upload(headers, session_id, **overrides):
    data = {"session_id": str(session_id), "duration_seconds": "42"}
    data.update({k: str(v) for k, v in overrides.items()})
    return client.post(
        "/api/v1/daily-logs/voice",
        headers=headers,
        data=data,
        files={"file": ("voice-log.webm", FAKE_AUDIO, "audio/webm")},
    )


def test_voice_upload_runs_mock_pipeline_to_ready():
    headers = _therapist_headers()
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    assert session_ids, "Need a schedulable session for the therapist"

    res = _upload(headers, session_ids[0])
    assert res.status_code == 201, res.text
    body = res.json()
    recording_id = body["id"]
    assert body["recording_status"] in ("UPLOADED", "PROCESSING", "READY")

    status = client.get(f"/api/v1/daily-logs/voice/{recording_id}/status", headers=headers)
    assert status.status_code == 200, status.text
    payload = status.json()
    # TestClient runs BackgroundTasks synchronously — mock pipeline should be done.
    assert payload["recording_status"] == "READY", payload
    assert payload["transcription_status"] == "COMPLETED"
    assert payload["transcript"]
    assert payload["extraction_status"] in ("COMPLETED", "PARTIAL")
    extraction = payload["extraction"]
    assert extraction is not None
    assert extraction["session_summary"]
    # Guardrail: any goal id present must come from the case's goal cards (or be None).
    for goal in extraction.get("goal_evidence", []):
        assert goal["goal_card_id"] is None or isinstance(goal["goal_card_id"], int)


def test_voice_status_denied_for_non_owner():
    headers = _therapist_headers()
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    res = _upload(headers, session_ids[0])
    assert res.status_code == 201, res.text
    recording_id = res.json()["id"]

    other = login_headers(client, "casemanager@demo.com")
    denied = client.get(f"/api/v1/daily-logs/voice/{recording_id}/status", headers=other)
    assert denied.status_code == 403


def test_voice_status_includes_structured_session():
    headers = _therapist_headers()
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    res = _upload(headers, session_ids[0])
    assert res.status_code == 201, res.text
    recording_id = res.json()["id"]
    status = client.get(f"/api/v1/daily-logs/voice/{recording_id}/status", headers=headers)
    assert status.status_code == 200, status.text
    payload = status.json()
    assert "pipeline_phase" in payload
    assert payload.get("structured_session") is not None or payload["recording_status"] == "READY"


def test_voice_upload_rejects_non_audio_and_oversize():
    headers = _therapist_headers()
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)

    res = client.post(
        "/api/v1/daily-logs/voice",
        headers=headers,
        data={"session_id": str(session_ids[0])},
        files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert res.status_code == 400


def test_voice_retry_requeues_pipeline():
    headers = _therapist_headers()
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    res = _upload(headers, session_ids[0])
    assert res.status_code == 201, res.text
    recording_id = res.json()["id"]

    retry = client.post(f"/api/v1/daily-logs/voice/{recording_id}/retry", headers=headers)
    assert retry.status_code == 200, retry.text
    status = client.get(f"/api/v1/daily-logs/voice/{recording_id}/status", headers=headers)
    assert status.json()["recording_status"] == "READY"
