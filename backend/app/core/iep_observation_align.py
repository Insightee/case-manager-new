"""IEP ↔ Observation alignment — shared domain and environment keys."""

from __future__ import annotations

from app.report_engine_constants import OBSERVATION_REPORT_SECTIONS

# Observation report domain narrative sections → IEP present-level tabs (same keys).
IEP_DOMAIN_TABS: list[dict[str, str]] = [
    {"id": "communication", "label": "Communication"},
    {"id": "regulation_sensory", "label": "Regulation & Sensory"},
    {"id": "participation", "label": "Participation"},
    {"id": "learning_access", "label": "Learning Access"},
    {"id": "peer_interaction", "label": "Social / Peer Interaction"},
]

IEP_DOMAIN_SECTION_KEYS = {t["id"] for t in IEP_DOMAIN_TABS}

IEP_LEARNING_ENVIRONMENTS: list[dict[str, str]] = [
    {"id": "home", "label": "Home"},
    {"id": "school", "label": "School"},
    {"id": "physical", "label": "Physical"},
    {"id": "intellectual", "label": "Intellectual"},
    {"id": "social", "label": "Social"},
    {"id": "creative", "label": "Creative"},
    {"id": "emotional", "label": "Emotional"},
]

IEP_ENVIRONMENT_IDS = {e["id"] for e in IEP_LEARNING_ENVIRONMENTS}

OBSERVATION_DOMAIN_SECTIONS = [
    s for s in OBSERVATION_REPORT_SECTIONS
    if s["key"] in IEP_DOMAIN_SECTION_KEYS
]
