"""Canonical finance_confidence is the single backend policy source."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import billing_composer_service, finance_confidence, finance_control_tower_service as tower


def test_money_value_clamp_shared_between_helper_and_tower_export(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    kwargs = dict(
        value=100.0,
        confidence="RECONCILED",
        confidence_reason="should be replaced",
        record_count=1,
        source_period="2026-07",
    )
    a = finance_confidence.money_value(**kwargs)
    b = tower.money_value(**kwargs)
    assert a["confidence"] == b["confidence"] == "PARTIAL"
    assert a["confidenceReason"] == b["confidenceReason"]
    assert "cutover" in a["confidenceReason"].lower()
    assert a["value"] == b["value"] == 100.0


def test_preview_confidence_matches_composer_path(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    via_helper = finance_confidence.preview_confidence(material_missing=True, has_suggested=False)
    # Composer imports the same function — identity, not a fork.
    assert billing_composer_service.preview_confidence is finance_confidence.preview_confidence
    via_composer = billing_composer_service.preview_confidence(
        material_missing=True, has_suggested=False
    )
    assert via_helper == via_composer
    assert via_helper["confidence"] == "INCOMPLETE"

    pre = finance_confidence.preview_confidence(material_missing=False, has_suggested=True)
    assert pre["confidence"] == "PARTIAL"
    assert pre["confidence"] != "RECONCILED"


def test_lowest_confidence_shared(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    assert finance_confidence.lowest_confidence("PARTIAL", "ESTIMATED") == "ESTIMATED"
    assert tower.lowest_confidence("PARTIAL", "ESTIMATED") == "ESTIMATED"
    assert tower.lowest_confidence is finance_confidence.lowest_confidence


def test_no_inline_confidence_decision_trees_in_tower_or_composer():
    """Guard: policy bodies live only in finance_confidence.py."""
    root = Path(__file__).resolve().parents[1] / "services"
    helper = (root / "finance_confidence.py").read_text(encoding="utf-8")
    tower_src = (root / "finance_control_tower_service.py").read_text(encoding="utf-8")
    composer_src = (root / "billing_composer_service.py").read_text(encoding="utf-8")

    assert "def money_value(" in helper
    assert "def preview_confidence(" in helper
    assert "def lowest_confidence(" in helper

    # Tower must not redefine money_value / lowest_confidence (re-export only).
    tower_tree = ast.parse(tower_src)
    defined = {
        n.name
        for n in tower_tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "money_value" not in defined
    assert "lowest_confidence" not in defined
    assert "count_card" not in defined
    assert "_preview_confidence" not in defined

    composer_tree = ast.parse(composer_src)
    composer_defined = {
        n.name
        for n in composer_tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_preview_confidence" not in composer_defined
    assert "preview_confidence" in composer_src  # imported / called
