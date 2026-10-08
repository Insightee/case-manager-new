"""Therapist profile vault — required document slots and labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VaultDocumentSlot:
    key: str
    label: str
    help_text: Optional[str] = None
    allow_multiple: bool = False


MEDICAL_CERT_HELP = (
    "Upload a medical certificate covering physical and mental fitness, or book a check-up "
    "and submit the report when ready. You can use providers such as Healthians, Orange Health, or 1MG."
)

FIXED_VAULT_SLOTS: tuple[VaultDocumentSlot, ...] = (
    VaultDocumentSlot("offer_letter", "Signed Offer Letter"),
    VaultDocumentSlot("consultant_agreement", "Consultant Agreement"),
    VaultDocumentSlot("pan_card", "PAN Card"),
    VaultDocumentSlot("aadhaar_card", "Aadhaar Card"),
    VaultDocumentSlot("address_proof", "Address Proof"),
    VaultDocumentSlot("degree_certificate", "Degree Certificate"),
    VaultDocumentSlot("mark_card", "Mark Card"),
    VaultDocumentSlot("passport_photo", "Passport Photo"),
    VaultDocumentSlot("medical_certificate", "Medical Certificate", help_text=MEDICAL_CERT_HELP),
    VaultDocumentSlot("passbook_first_page", "Passbook — first page"),
)

OTHER_CERTIFICATION_SLOT = VaultDocumentSlot(
    "other_certification",
    "Additional certification",
    help_text="Share any extra certifications you would like us to keep on file.",
    allow_multiple=True,
)

ALL_SLOT_KEYS = frozenset(s.key for s in FIXED_VAULT_SLOTS) | {OTHER_CERTIFICATION_SLOT.key}


def slot_for_key(key: str) -> Optional[VaultDocumentSlot]:
    for s in FIXED_VAULT_SLOTS:
        if s.key == key:
            return s
    if key == OTHER_CERTIFICATION_SLOT.key:
        return OTHER_CERTIFICATION_SLOT
    return None
