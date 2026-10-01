from __future__ import annotations

from types import SimpleNamespace

from app.services.therapist_profile_quality import (
    evaluate_profile_quality,
    is_ten_digit_phone,
    word_count,
)


FORTY_ONE = " ".join(["support"] * 41)


def test_word_count_and_phone():
    assert word_count(FORTY_ONE) == 41
    assert word_count("short bio") == 2
    assert is_ten_digit_phone("9876543210")
    assert is_ten_digit_phone("+91 98765 43210")
    assert not is_ten_digit_phone("12345")


def test_score_and_auto_pass_floors():
    user = SimpleNamespace(
        email="t@demo.com",
        phone="9876543210",
        avatar_path="avatars/x.png",
        home_address_line1="12 MG Road",
        home_city="Bengaluru",
        home_pincode="560001",
        full_name="Neha",
        avatar_url=None,
        home_address=None,
    )
    profile = SimpleNamespace(
        display_name="Neha",
        short_bio=FORTY_ONE,
        services_offered=["homecare"],
        professional_qualification_entries=[{"kind": "degree", "title": "M.Sc.", "year": 2019}],
        professional_certificates=[],
        pending_submission=None,
    )
    quality = evaluate_profile_quality(user, profile)
    assert quality["score"] == 100
    assert quality["auto_pass"] is True
    assert quality["can_submit"] is True


def test_auto_pass_false_without_degree_even_if_score_high():
    user = SimpleNamespace(
        email="t@demo.com",
        phone="9876543210",
        avatar_path="avatars/x.png",
        home_address_line1="12 MG Road",
        home_city="Bengaluru",
        home_pincode="560001",
        full_name="Neha",
        avatar_url=None,
        home_address=None,
    )
    profile = SimpleNamespace(
        display_name="Neha",
        short_bio=FORTY_ONE,
        services_offered=["homecare"],
        professional_qualification_entries=[],
        professional_certificates=[],
        pending_submission=None,
    )
    quality = evaluate_profile_quality(user, profile)
    assert quality["score"] == 85
    assert quality["auto_pass"] is False


def test_cannot_submit_below_50():
    user = SimpleNamespace(
        email="t@demo.com",
        phone=None,
        avatar_path=None,
        home_address_line1=None,
        home_city=None,
        home_pincode=None,
        full_name="Neha",
        avatar_url=None,
        home_address=None,
    )
    quality = evaluate_profile_quality(
        user,
        None,
        listing={"display_name": "Neha", "services_offered": ["homecare"], "short_bio": "Hi"},
    )
    assert quality["score"] < 50
    assert quality["can_submit"] is False
    assert quality["reminders"]
