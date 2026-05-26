from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None


class EmailProvider(Protocol):
    name: str

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body_text: str,
        body_html: str | None,
        from_header: str,
        envelope_from: str,
    ) -> SendResult: ...
