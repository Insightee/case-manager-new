"""Staff department validation."""

import pytest

from app.core.departments import (
    normalize_staff_department,
    staff_department_label,
    validate_staff_department,
)


def test_normalize_staff_department_accepts_ids():
    assert normalize_staff_department("MENTORS") == "MENTORS"
    assert normalize_staff_department("onboarding mentors") == "ONBOARDING_MENTORS"


def test_validate_staff_department_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown department"):
        validate_staff_department("Sales")


def test_validate_staff_department_allows_empty():
    assert validate_staff_department(None) is None
    assert validate_staff_department("") is None


def test_staff_department_label():
    assert staff_department_label("CASE_MANAGERS") == "Case Managers"
    assert staff_department_label(None) is None
