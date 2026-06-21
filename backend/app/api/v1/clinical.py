from __future__ import annotations

from fastapi import APIRouter

from app.core.clinical_domains import CLINICAL_DOMAINS, OBSERVATION_KEY_TO_DOMAIN

router = APIRouter(prefix="/clinical", tags=["clinical"])


@router.get("/domains")
def list_clinical_domains():
    return {"domains": CLINICAL_DOMAINS, "observation_key_map": OBSERVATION_KEY_TO_DOMAIN}
